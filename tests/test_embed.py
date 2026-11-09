"""Tests for src/embed.py. Cohere is faked: no API calls, no key needed.

Run: pytest tests/test_embed.py
"""

import json
from types import SimpleNamespace

from cohere import TooManyRequestsError
import numpy as np
import pytest

from src import embed


@pytest.fixture(autouse=True)
def no_sleeping(monkeypatch):
    monkeypatch.setattr(embed.time, "sleep", lambda seconds: None)


class FakeClient:
    """Pretends to be cohere.ClientV2: every text becomes a vector of [len(text), 0, 0, ...]."""

    def __init__(self, fail_first=0):
        self.calls = []
        self.fail_first = fail_first

    def embed(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_first:
            self.fail_first -= 1
            raise TooManyRequestsError(body="slow down")
        dims = kwargs["output_dimension"]
        vectors = [[float(len(t))] + [0.0] * (dims - 1) for t in kwargs["texts"]]
        return SimpleNamespace(embeddings=SimpleNamespace(float_=vectors))


def test_load_chunks(tmp_path):
    f = tmp_path / "c.jsonl"
    f.write_text('{"id": "a", "text": "x"}\n{"id": "b", "text": "Puskás"}\n', encoding="utf-8")
    assert embed.load_chunks(f) == [{"id": "a", "text": "x"}, {"id": "b", "text": "Puskás"}]


def test_batches():
    assert embed.batches([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert embed.batches([], 3) == []


def test_embed_batch_shape_and_settings():
    co = FakeClient()
    out = embed.embed_batch(co, ["ab", "abcd"])
    assert out.shape == (2, embed.DIMENSIONS)
    assert out.dtype == np.float32
    assert out[1, 0] == 4.0
    call = co.calls[0]
    assert call["input_type"] == "search_document"
    assert call["model"] == embed.MODEL
    assert call["embedding_types"] == ["float"]


def test_embed_batch_retries_when_rate_limited():
    co = FakeClient(fail_first=2)
    out = embed.embed_batch(co, ["abc"])
    assert out.shape == (1, embed.DIMENSIONS)
    assert len(co.calls) == 3


def test_embed_batch_gives_up():
    with pytest.raises(TooManyRequestsError):
        embed.embed_batch(FakeClient(fail_first=99), ["abc"], retries=3)


def test_normalise_rows_have_length_one():
    v = np.array([[3.0, 4.0], [0.0, 2.0]], dtype=np.float32)
    out = embed.normalise(v)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0)
    assert np.allclose(out[0], [0.6, 0.8])


def test_main_embeds_saves_and_resumes(monkeypatch, tmp_path):
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text("".join(json.dumps({"id": str(i), "text": "x" * (i + 1)}) + "\n" for i in range(5)),
                      encoding="utf-8")
    monkeypatch.setattr(embed, "CHUNKS_FILE", chunks)
    monkeypatch.setattr(embed, "OUT_FILE", tmp_path / "emb.npy")
    monkeypatch.setattr(embed, "BATCH_DIR", tmp_path / "batches")
    monkeypatch.setattr(embed, "BATCH_SIZE", 2)
    co = FakeClient()
    monkeypatch.setattr(embed, "get_client", lambda: co)

    embed.main()
    out = np.load(tmp_path / "emb.npy")
    assert out.shape == (5, embed.DIMENSIONS)
    assert out.dtype == np.float16
    assert np.allclose(np.linalg.norm(out.astype(np.float32), axis=1), 1.0, atol=1e-2)
    assert len(co.calls) == 3                       # 5 chunks in batches of 2

    embed.main()                                    # second run: every batch is already saved
    assert len(co.calls) == 3
