"""Ask: answer a football question from the Wikipedia chunks, with citations.

Run from the project root (after python -m src.embed):
    python -m src.ask "Who won the 2015-16 Premier League?"

Three steps, each one narrowing down:
1. Retrieve: embed the question and take the 30 chunks whose vectors are closest (fast, rough).
2. Rerank:   Cohere's reranker reads the question with each of those 30 chunks and keeps the
             best 5 (slower, much more accurate).
3. Answer:   Cohere's chat model writes the answer using ONLY those 5 chunks, and says which
             chunk supports which words (citations). If they don't hold the answer, it says so.
"""

import sys

import numpy as np

from src.embed import CHUNKS_FILE, DIMENSIONS, MODEL as EMBED_MODEL, OUT_FILE as EMBEDDINGS_FILE
from src.embed import get_client, load_chunks

RERANK_MODEL = "rerank-v3.5"
CHAT_MODEL = "command-a-03-2025"
RETRIEVE_K = 30   # how many chunks the vector search hands to the reranker
TOP_N = 5         # how many chunks the reranker hands to the chat model

SYSTEM_PROMPT = (
    "You answer questions about football using only the documents provided. "
    "If the documents do not contain the answer, say you could not find it in the sources. "
    "Keep answers short and factual."
)


def load_index(chunks_path=CHUNKS_FILE, embeddings_path=EMBEDDINGS_FILE):
    """Return (chunks, vectors): the chunk dicts and their vectors as a float32 array.

    Row i of the vectors belongs to chunk i. The file is saved as float16 to save space;
    turn it back into float32 with .astype(np.float32) so the maths stays accurate.
    """
    chunks = load_chunks(chunks_path)
    vectors = np.load(embeddings_path).astype(np.float32)
    assert vectors.shape == (len(chunks), DIMENSIONS)
    return chunks, vectors


def embed_query(co, question):
    """Embed the question; return one float32 vector of length DIMENSIONS, scaled to length 1.

    Same call as embed_batch in embed.py, with two differences:
      - texts=[question]  (a list of one)
      - input_type="search_query"  (a question looking for documents, not a document)
    Take the first (only) row, then divide it by np.linalg.norm(row).
    """
    response = co.embed(model=EMBED_MODEL, texts=[question], input_type="search_query",
                        output_dimension=DIMENSIONS, embedding_types=["float"])
    vector = np.array(response.embeddings.float_[0], dtype=np.float32)   # the one question's vector
    return vector / np.linalg.norm(vector)    # length 1, like the chunk vectors


def top_k(vectors, query, k=RETRIEVE_K):
    """Return the row numbers of the k chunks most similar to the query, most similar first.

    Every vector has length 1, so similarity is a dot product: scores = vectors @ query
    (one score per chunk). np.argsort(scores) sorts from LOWEST to highest, so reverse it
    with [::-1] and keep the first k.
    """
    return np.argsort(vectors @ query)[::-1][:k]


def rerank(co, question, candidates, top_n=TOP_N):
    """Return the top_n candidate chunks, best first, each with a "score" added.

    The call:
        response = co.rerank(model=RERANK_MODEL, query=question,
                             documents=[c["text"] for c in candidates], top_n=top_n)
    response.results is a list, best first; each result has .index (position in candidates)
    and .relevance_score (0 to 1). Return copies of the chunks: {**candidates[r.index], "score": ...}.
    """
    response = co.rerank(model=RERANK_MODEL, query=question,
                         documents=[c["text"] for c in candidates], top_n=top_n)
    return [{**candidates[r.index], "score": r.relevance_score} for r in response.results]


def answer(co, question, chunks):
    """Ask the chat model to answer from the chunks; return {"text": ..., "citations": [...]}.

    The call:
        response = co.chat(
            model=CHAT_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": question}],
            documents=[{"id": c["id"], "data": {"title": f"{c['title']} — {c['section']}", "text": c["text"]}}
                       for c in chunks],
        )
    The answer text is response.message.content[0].text.
    response.message.citations is a list (or None when nothing is cited); each citation has
    .text (the words in the answer) and .sources (each with an .id, the chunk id it came from).
    Return citations as a list of {"text": ..., "ids": [source ids]}.
    """
    response = co.chat(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},   # the rules
                  {"role": "user", "content": question}],          # the question
        documents=[{"id": c["id"], "data": {"title": f"{c['title']} — {c['section']}", "text": c["text"]}}
                   for c in chunks],                                # the only facts it may use
    )
    # each citation: which words of the answer came from which chunk ids (None means nothing was cited)
    citations = [{"text": c.text, "ids": [s.id for s in c.sources]}
                 for c in (response.message.citations or [])]
    return {"text": response.message.content[0].text, "citations": citations}


def ask(question, co=None, chunks=None, vectors=None):
    """The whole pipeline: retrieve, rerank, answer. Return {"answer", "citations", "sources"}.

    - co defaults to get_client(); chunks/vectors default to load_index()
      (passing them in lets the app load them once instead of on every question)
    - candidates = [chunks[i] for i in top_k(vectors, embed_query(co, question))]
    - best = rerank(co, question, candidates)
    - result = answer(co, question, best)
    - "sources" is the list of best chunks (title, section, url, score), so the app can link them
    """
    co = co or get_client()
    if chunks is None or vectors is None:
        chunks, vectors = load_index()
    candidates = [chunks[i] for i in top_k(vectors, embed_query(co, question))]
    best = rerank(co, question, candidates)
    result = answer(co, question, best)
    # only what the app needs to show and link each source; "id" lets it match citations to sources
    sources = [{k: c[k] for k in ("id", "title", "section", "url", "score")} for c in best]
    return {"answer": result["text"], "citations": result["citations"], "sources": sources}


def main():
    """python -m src.ask "your question": print the answer, then the sources it used."""
    question = " ".join(sys.argv[1:]) or "Who won the 2015-16 Premier League?"
    result = ask(question)
    print(result["answer"])
    print("\nSources:")
    for s in result["sources"]:
        print(f"  {s['score']:.2f}  {s['title']} — {s['section']}  {s['url']}")


if __name__ == "__main__":
    main()
