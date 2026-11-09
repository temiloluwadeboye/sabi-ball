"""Evaluate: does the search find the right page? 35 questions with known answer pages.

Run from the project root (after python -m src.embed):
    python -m src.evaluate

Input:  eval/questions.jsonl   one line per question: {"question": ..., "level": ..., "relevant": [page titles]}
                               a chunk counts as a hit if its page title is in "relevant"
                               level "easy" (20): the question names the page ("Who won the 2023-24 Bundesliga?")
                               level "hard" (15): reworded, no page name ("Which final is known as the Miracle of Istanbul?")
Output: a table printed to the screen, and eval/results.json

For every question we look at where the FIRST right chunk lands in the ranked list, twice:
  - vector only: the 30 chunks from top_k, in vector-similarity order
  - reranked:    the same 30 chunks, reordered by Cohere's reranker
Then two scores for each:
  - hit@5: the share of questions with a right chunk in the top 5 (0 to 1, higher is better)
  - MRR (mean reciprocal rank): the average of 1/rank. First place = 1, second = 0.5,
    third = 0.33 ... not found = 0. It rewards putting the right chunk near the very top.
The chat model only ever sees the top 5, so hit@5 says how often it gets a fair chance to answer.
"""

import json
import time
from pathlib import Path

from cohere import TooManyRequestsError

from src.ask import RETRIEVE_K, embed_query, load_index, rerank, top_k
from src.embed import get_client

QUESTIONS_FILE = Path("eval/questions.jsonl")
RESULTS_FILE = Path("eval/results.json")
K = 5                  # the cut-off for hit@k: the chat model sees the top 5
PAUSE_SECONDS = 7      # trial keys allow about 10 rerank calls a minute


def load_questions(path=QUESTIONS_FILE):
    """Return the list of question dicts from a .jsonl file."""
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def with_retry(call, retries=5):
    """Run call() and return its result; if Cohere says "slow down", wait 10, 20, 40... seconds and try again."""
    wait = 10
    for attempt in range(retries):
        try:
            return call()
        except TooManyRequestsError:
            if attempt == retries - 1:
                raise
            print(f"Rate limited, waiting {wait}s")
            time.sleep(wait)
            wait *= 2


def first_hit_rank(ranked_chunks, relevant):
    """Return the position (1 = first) of the first chunk whose "title" is in relevant, or None if there is none.

        first_hit_rank([{"title": "A"}, {"title": "B"}], ["B"]) -> 2
        first_hit_rank([{"title": "A"}], ["Z"])                  -> None

    Tip: enumerate(ranked_chunks, start=1) gives you (1, first chunk), (2, second chunk), ...
    """
    for rank, chunk in enumerate(ranked_chunks, start=1):
        if chunk["title"] in relevant:
            return rank          # stop at the first right chunk
    return None                  # no right chunk anywhere in the list


def score(ranks, k=K):
    """Turn a list of ranks (numbers or None) into {"hit@k": ..., "mrr": ...}, both between 0 and 1.

        score([1, 3, None, 8], k=5) -> {"hit@k": 0.5, "mrr": (1 + 1/3 + 0 + 1/8) / 4}

    - hit@k: how many ranks are not None AND at most k, divided by len(ranks)
    - mrr:   the average of 1/rank, counting None as 0
    Round both to 3 decimal places with round(x, 3).
    """
    hits = sum(1 for r in ranks if r is not None and r <= k)       # found inside the top k
    mrr = sum(1 / r for r in ranks if r is not None) / len(ranks)   # None adds 0 but still counts in len
    return {"hit@k": round(hits / len(ranks), 3), "mrr": round(mrr, 3)}


def rank_question(co, question, relevant, chunks, vectors):
    """Return (vector_rank, rerank_rank) for one question.

    - candidates = the RETRIEVE_K chunks from top_k, as in ask.py
      (wrap the Cohere call in with_retry:  query = with_retry(lambda: embed_query(co, question)))
    - vector_rank = first_hit_rank(candidates, relevant)
    - reordered = rerank(co, question, candidates, top_n=len(candidates))  (also inside with_retry)
      top_n=len(candidates) keeps all 30, just in a new order, so a hit at rank 12 still counts for MRR
    - rerank_rank = first_hit_rank(reordered, relevant)
    """
    query = with_retry(lambda: embed_query(co, question))
    candidates = [chunks[i] for i in top_k(vectors, query, RETRIEVE_K)]               # vector order
    reordered = with_retry(lambda: rerank(co, question, candidates, top_n=len(candidates)))  # same 30, new order
    return first_hit_rank(candidates, relevant), first_hit_rank(reordered, relevant)


def main():
    """Rank every question, print a table and the two scores, save everything to RESULTS_FILE."""
    co = get_client()
    chunks, vectors = load_index()
    questions = load_questions()

    rows = []
    for n, q in enumerate(questions, start=1):
        vector_rank, rerank_rank = rank_question(co, q["question"], q["relevant"], chunks, vectors)
        rows.append({"question": q["question"], "level": q["level"],
                     "vector_rank": vector_rank, "rerank_rank": rerank_rank})
        print(f"{n:2d}. {q['level']:<4}  vector {str(vector_rank):>4}  rerank {str(rerank_rank):>4}  {q['question']}")
        time.sleep(PAUSE_SECONDS)

    # score each group on its own: "easy" questions name the page, "hard" ones are reworded
    results = {"questions": rows}
    print(f"\n                     hit@{K}   MRR")
    for level in ("easy", "hard", "all"):
        group = [r for r in rows if level in ("all", r["level"])]
        results[level] = {
            "count": len(group),
            "vector": score([r["vector_rank"] for r in group]),
            "rerank": score([r["rerank_rank"] for r in group]),
        }
        for name in ("vector", "rerank"):
            s = results[level][name]
            print(f"{level:<4} ({len(group):2d})  {name:<6}  {s['hit@k']:.2f}   {s['mrr']:.2f}")

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved -> {RESULTS_FILE}")


if __name__ == "__main__":
    main()
