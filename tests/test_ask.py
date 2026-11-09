"""Tests for src/ask.py. Cohere is faked: no API calls, no key needed.

Run: pytest tests/test_ask.py
"""

import json
from types import SimpleNamespace

import numpy as np

from src import ask
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
    def __init__(self):
        self.calls = {}

    def embed(self, **kwargs):
        self.calls["embed"] = kwargs
        return SimpleNamespace(embeddings=SimpleNamespace(float_=[[3.0, 4.0] + [0.0] * (DIMENSIONS - 2)]))

    def rerank(self, **kwargs):
        self.calls["rerank"] = kwargs
        # pretend the reranker likes the last document best, then the first
        n = len(kwargs["documents"])
        results = [SimpleNamespace(index=n - 1, relevance_score=0.9), SimpleNamespace(index=0, relevance_score=0.4)]
        return SimpleNamespace(results=results[: kwargs["top_n"]])

    def chat(self, **kwargs):
        self.calls["chat"] = kwargs
        first_id = kwargs["documents"][0]["id"]
        message = SimpleNamespace(
            content=[SimpleNamespace(text="Leicester City won it.")],
            citations=[SimpleNamespace(text="Leicester City", sources=[SimpleNamespace(id=first_id)])],
        )
        return SimpleNamespace(message=message)


def test_load_index(tmp_path):
    chunks_file = tmp_path / "chunks.jsonl"
    chunks_file.write_text("".join(json.dumps(c) + "\n" for c in CHUNKS), encoding="utf-8")
    emb_file = tmp_path / "emb.npy"
    np.save(emb_file, np.stack([unit(1), unit(0, 1), unit(1, 1)]).astype(np.float16))
    chunks, vectors = ask.load_index(chunks_file, emb_file)
    assert [c["id"] for c in chunks] == ["a", "b", "c"]
    assert vectors.dtype == np.float32 and vectors.shape == (3, DIMENSIONS)


def test_embed_query_uses_search_query_and_normalises():
    co = FakeClient()
    q = ask.embed_query(co, "who won?")
    assert co.calls["embed"]["input_type"] == "search_query"
    assert co.calls["embed"]["texts"] == ["who won?"]
    assert q.shape == (DIMENSIONS,) and q.dtype == np.float32
    assert np.isclose(np.linalg.norm(q), 1.0) and np.isclose(q[0], 0.6)


def test_top_k_orders_by_similarity():
    vectors = np.stack([unit(1, 0), unit(0, 1), unit(1, 1)])
    assert list(ask.top_k(vectors, unit(1, 0.1), k=2)) == [0, 2]
    assert len(ask.top_k(vectors, unit(1, 0.1), k=10)) == 3


def test_rerank_returns_best_chunks_with_scores():
    best = ask.rerank(FakeClient(), "q", CHUNKS, top_n=2)
    assert [c["id"] for c in best] == ["c", "a"]
    assert best[0]["score"] == 0.9
    assert "score" not in CHUNKS[2]   # the original chunks are not changed


def test_answer_returns_text_and_citations():
    co = FakeClient()
    result = ask.answer(co, "who won?", CHUNKS[1:2])
    assert result["text"] == "Leicester City won it."
    assert result["citations"] == [{"text": "Leicester City", "ids": ["b"]}]
    docs = co.calls["chat"]["documents"]
    assert docs[0]["id"] == "b" and docs[0]["data"]["text"] == "Champions: Leicester City"
    assert co.calls["chat"]["messages"][0]["role"] == "system"


def test_answer_handles_no_citations():
    co = FakeClient()
    co.chat = lambda **kw: SimpleNamespace(message=SimpleNamespace(
        content=[SimpleNamespace(text="I could not find it in the sources.")], citations=None))
    assert ask.answer(co, "q", CHUNKS)["citations"] == []


def test_ask_runs_the_whole_pipeline():
    vectors = np.stack([unit(1, 0), unit(0, 1), unit(1, 1)])
    result = ask.ask("who won?", co=FakeClient(), chunks=CHUNKS, vectors=vectors)
    assert result["answer"] == "Leicester City won it."
    assert [s["title"] for s in result["sources"]][0] in {c["title"] for c in CHUNKS}
    assert {"title", "section", "url", "score"} <= set(result["sources"][0])
