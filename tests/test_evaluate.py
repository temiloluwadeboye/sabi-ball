"""Tests for src/evaluate.py. Cohere is faked: no API calls, no key needed.

Run: pytest tests/test_evaluate.py
"""

import json
from types import SimpleNamespace

import numpy as np

from src import evaluate
from src.embed import DIMENSIONS


def unit(*values):
    v = np.zeros(DIMENSIONS, dtype=np.float32)
    v[: len(values)] = values
    return v / np.linalg.norm(v)


CHUNKS = [
    {"id": "a", "title": "Arsenal F.C.", "section": "History", "url": "ua", "text": "Arsenal history"},
    {"id": "b", "title": "2015–16 Premier League", "section": "Overview", "url": "ub", "text": "Champions: Leicester City"},
    {"id": "c", "title": "Ballon d'Or", "section": "Winners", "url": "uc", "text": "Messi won eight"},
]


class FakeClient:
    """Question vector points at chunk "a"; the reranker reverses whatever order it is given."""

    def __init__(self):
        self.calls = {}

    def embed(self, **kwargs):
        return SimpleNamespace(embeddings=SimpleNamespace(float_=[[1.0, 0.1] + [0.0] * (DIMENSIONS - 2)]))

    def rerank(self, **kwargs):
        self.calls["rerank"] = kwargs
        n = len(kwargs["documents"])
        results = [SimpleNamespace(index=i, relevance_score=1 - i / 10) for i in reversed(range(n))]
        return SimpleNamespace(results=results[: kwargs["top_n"]])


def test_load_questions(tmp_path):
    f = tmp_path / "q.jsonl"
    f.write_text('{"question": "q1", "relevant": ["A"]}\n\n{"question": "q2", "relevant": ["B", "C"]}\n',
                 encoding="utf-8")
    assert [q["question"] for q in evaluate.load_questions(f)] == ["q1", "q2"]


def test_questions_file_is_valid():
    questions = evaluate.load_questions()
    assert len(questions) == 35
    assert all(q["question"] and q["relevant"] for q in questions)
    assert [q["level"] for q in questions].count("hard") == 15
    assert {q["level"] for q in questions} == {"easy", "hard"}


def test_first_hit_rank():
    ranked = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
    assert evaluate.first_hit_rank(ranked, ["A"]) == 1
    assert evaluate.first_hit_rank(ranked, ["C", "B"]) == 2     # the FIRST hit counts
    assert evaluate.first_hit_rank(ranked, ["Z"]) is None
    assert evaluate.first_hit_rank([], ["A"]) is None


def test_score():
    assert evaluate.score([1, 3, None, 8], k=5) == {"hit@k": 0.5, "mrr": round((1 + 1 / 3 + 0 + 1 / 8) / 4, 3)}
    assert evaluate.score([None, None]) == {"hit@k": 0.0, "mrr": 0.0}
    assert evaluate.score([5, 6], k=5)["hit@k"] == 0.5          # rank 5 is inside the top 5, rank 6 is not


def test_rank_question():
    co = FakeClient()
    vectors = np.stack([unit(1, 0), unit(0, 1), unit(1, 1)])
    # vector order: a, c, b  ->  reranker reverses it: b, c, a
    vector_rank, rerank_rank = evaluate.rank_question(co, "who won?", ["2015–16 Premier League"], CHUNKS, vectors)
    assert (vector_rank, rerank_rank) == (3, 1)
    assert co.calls["rerank"]["top_n"] == 3                      # keeps every candidate, only reorders


def test_with_retry_waits_then_succeeds(monkeypatch):
    from cohere import TooManyRequestsError
    monkeypatch.setattr(evaluate.time, "sleep", lambda s: None)
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise TooManyRequestsError(body="slow down")
        return "ok"

    assert evaluate.with_retry(flaky) == "ok" and len(attempts) == 3
