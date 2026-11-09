"""Tests for src/chunk.py.

Run: pytest tests/test_chunk.py
"""

import json

from src import chunk


def words(n, start=1):
    return " ".join(f"w{i}" for i in range(start, start + n))


# --- split_long_line --------------------------------------------------------

def test_split_long_line_short_line_unchanged():
    assert chunk.split_long_line("a b c", max_words=5, overlap=1) == ["a b c"]


def test_split_long_line_overlaps():
    pieces = chunk.split_long_line(words(10), max_words=4, overlap=1)
    assert pieces == ["w1 w2 w3 w4", "w4 w5 w6 w7", "w7 w8 w9 w10"]


def test_split_long_line_no_tiny_tail():
    # 300 words, max 250, overlap 40: two pieces, the second ending on the last word
    pieces = chunk.split_long_line(words(300), max_words=250, overlap=40)
    assert len(pieces) == 2
    assert pieces[0].split()[-1] == "w250"
    assert pieces[1].split()[0] == "w211" and pieces[1].split()[-1] == "w300"


# --- pack_lines ---------------------------------------------------------------

def test_pack_lines_groups_without_splitting_lines():
    text = "\n".join([words(3, 1), words(3, 4), words(3, 7)])   # three 3-word lines
    assert chunk.pack_lines(text, max_words=6) == [words(3, 1) + "\n" + words(3, 4), words(3, 7)]


def test_pack_lines_skips_empty_lines():
    assert chunk.pack_lines("a b\n\n\nc d", max_words=10) == ["a b\nc d"]


def test_pack_lines_splits_a_line_longer_than_max():
    out = chunk.pack_lines(words(10), max_words=4)
    assert all(len(c.split()) <= 4 for c in out)
    assert out[0].split()[0] == "w1" and out[-1].split()[-1] == "w10"


# --- chunk_id -----------------------------------------------------------------

def test_chunk_id():
    assert chunk.chunk_id("2015–16 Premier League", "League table", 0) == "2015-16-premier-league--league-table--0"
    assert chunk.chunk_id("FIFA Puskás Award", "Winners > 2010s", 3) == "fifa-pusk-s-award--winners-2010s--3"


# --- make_chunks ----------------------------------------------------------------

def test_make_chunks_adds_header_and_ids():
    section = {"title": "Arsenal F.C.", "url": "u", "section": "History",
               "text": "\n".join([words(3, 1), words(3, 4)])}
    out = chunk.make_chunks(section)
    assert len(out) == 1
    assert out[0]["id"] == "arsenal-f-c--history--0"
    assert out[0]["text"] == "Arsenal F.C. — History\n" + words(3, 1) + "\n" + words(3, 4)
    assert (out[0]["title"], out[0]["url"], out[0]["section"]) == ("Arsenal F.C.", "u", "History")


# --- main -------------------------------------------------------------------------

def test_main_writes_chunks(monkeypatch, tmp_path):
    src = tmp_path / "sections.jsonl"
    src.write_text(json.dumps({"title": "T", "url": "u", "section": "S", "text": "Puskás won."},
                              ensure_ascii=False) + "\n", encoding="utf-8")
    out = tmp_path / "chunks.jsonl"
    monkeypatch.setattr(chunk, "IN_FILE", src)
    monkeypatch.setattr(chunk, "OUT_FILE", out)
    chunk.main()
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"id": "t--s--0", "title": "T", "url": "u", "section": "S", "text": "T — S\nPuskás won."}]
