"""Embed: turn every chunk into a vector (a list of numbers that captures its meaning) with Cohere.

Run from the project root (after python -m src.chunk, with COHERE_API_KEY in .env):
    python -m src.embed

Input:  data/processed/chunks.jsonl
Output: data/processed/embeddings.npy   one row of 512 numbers per chunk, same order as chunks.jsonl
        data/processed/embed_batches/   one small file per batch, so a restart skips finished batches

Two texts about the same thing get vectors that point in nearly the same direction. Later, the
question is embedded the same way and we look for the chunks whose vectors point closest to it.
"""

import json
import os
import time
from pathlib import Path

import cohere
from cohere import TooManyRequestsError
import numpy as np
from dotenv import load_dotenv

CHUNKS_FILE = Path("data/processed/chunks.jsonl")
OUT_FILE = Path("data/processed/embeddings.npy")
BATCH_DIR = Path("data/processed/embed_batches")

MODEL = "embed-v4.0"
DIMENSIONS = 512       # smaller vectors: a ~24 MB file we can ship with the app, little quality loss
BATCH_SIZE = 96        # the most texts Cohere embeds in one call
PAUSE_SECONDS = 3.5    # trial keys are rate-limited; ~17 calls a minute stays well under it


def get_client():
    """A Cohere client using the key in .env (never print or log the key)."""
    load_dotenv(".env")
    return cohere.ClientV2(api_key=os.environ["COHERE_API_KEY"])


def load_chunks(path=CHUNKS_FILE):
    """Return the list of chunk dicts from a .jsonl file (one JSON object per line)."""
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def batches(items, size=BATCH_SIZE):
    """Split a list into consecutive pieces of at most `size` items.

        batches([1, 2, 3, 4, 5], 2) -> [[1, 2], [3, 4], [5]]
    """
    return [items[start:start + size] for start in range(0, len(items), size)]


def embed_batch(co, texts, retries=5):
    """Embed one batch of texts as documents; return a float32 numpy array of shape (len(texts), DIMENSIONS).

    The call:
        response = co.embed(model=MODEL, texts=texts, input_type="search_document",
                            output_dimension=DIMENSIONS, embedding_types=["float"])
        vectors = response.embeddings.float_      # a list of lists of numbers

    input_type matters: chunks are "search_document"; questions will be "search_query".

    If Cohere says "slow down" (TooManyRequestsError), wait and try again,
    doubling the wait each time (10, 20, 40... seconds), like api_get in download.py.
    After `retries` failures, raise the error.
    """
    wait = 10
    for attempt in range(retries):
        try:
            response = co.embed(model=MODEL, texts=texts, input_type="search_document",
                                output_dimension=DIMENSIONS, embedding_types=["float"])
            vectors = response.embeddings.float_      # a list of lists of numbers
            return np.array(vectors, dtype=np.float32)
        except TooManyRequestsError:
            if attempt == retries - 1:   # that was the last try: give up and show the error
                raise
            print(f"Rate limited, waiting {wait}s (try {attempt + 1}/{retries})")
            time.sleep(wait)
            wait *= 2


def normalise(vectors):
    """Scale each row to length 1, so a plain dot product between two rows is their cosine similarity.

    Length of a row = np.linalg.norm(vectors, axis=1, keepdims=True). Divide by it.
    (keepdims=True keeps the shape (n, 1), so the division applies row by row.)
    """
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def main():
    """Embed every chunk, one batch at a time, then save all vectors in one file.

    - load the chunks and split their texts into batches
    - for batch number i, the batch file is BATCH_DIR / f"{i:05d}.npy"
      - if it already exists, skip it (a restart continues where it stopped)
      - otherwise embed_batch, np.save it, print progress, and time.sleep(PAUSE_SECONDS)
    - finally load every batch file in order, stack them (np.vstack), normalise,
      and save as float16 (half the size) to OUT_FILE
    - check the number of rows equals the number of chunks before saving
    """
    co = get_client()
    chunks = load_chunks(CHUNKS_FILE)
    groups = batches([c["text"] for c in chunks], BATCH_SIZE)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    for i, texts in enumerate(groups):
        path = BATCH_DIR / f"{i:05d}.npy"
        if path.exists():                  # done on an earlier run
            continue
        np.save(path, embed_batch(co, texts))
        print(f"batch {i + 1}/{len(groups)} embedded")
        time.sleep(PAUSE_SECONDS)          # stay under the trial key's rate limit

    vectors = np.vstack([np.load(BATCH_DIR / f"{i:05d}.npy") for i in range(len(groups))])
    if len(vectors) != len(chunks):
        raise ValueError(f"{len(vectors)} vectors for {len(chunks)} chunks: delete {BATCH_DIR} and rerun")
    np.save(OUT_FILE, normalise(vectors).astype(np.float16))
    print(f"{len(vectors):,} vectors of {vectors.shape[1]} numbers -> {OUT_FILE}")


if __name__ == "__main__":
    main()
