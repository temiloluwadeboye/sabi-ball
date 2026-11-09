"""Chunk: cut each section into pieces small enough to search and to hand to the chat model.

Run from the project root (after python -m src.clean):
    python -m src.chunk

Input:  data/processed/sections.jsonl   {"title", "url", "section", "text"} per line
Output: data/processed/chunks.jsonl     {"id", "title", "url", "section", "text"} per line

Why chunk? A whole page is too long to embed well and too long to quote as a source. A chunk of
about 250 words is long enough to hold one idea (a paragraph, or ten rows of a league table) and
short enough that its embedding is about one thing.

Each chunk's text starts with a one-line header naming its page and section, e.g.
    "2015–16 Premier League — League table"
so a chunk of bare table rows still says which season and which table it came from.
"""

import json
import re
from pathlib import Path

IN_FILE = Path("data/processed/sections.jsonl")
OUT_FILE = Path("data/processed/chunks.jsonl")
MAX_WORDS = 250    # target size of one chunk
OVERLAP = 40       # words repeated between pieces of one very long line, so no sentence is cut in two


def split_long_line(line, max_words=MAX_WORDS, overlap=OVERLAP):
    """Split one line that is longer than max_words into pieces of at most max_words words.

    Each new piece starts `overlap` words before the previous one ended, so an idea that
    straddles the cut still appears whole in one of the two pieces.
        "w1 ... w300" with max 250, overlap 40 -> ["w1 ... w250", "w211 ... w300"]
    A line of max_words words or fewer comes back unchanged, as a one-item list.

    Hint: words = line.split(); step = max_words - overlap; take words[start:start + max_words]
    for start in range(0, len(words), step), and stop once a piece reaches the last word.
    """
    words = line.split()
    if len(words) <= max_words:        # short enough already
        return [line]
    pieces = []
    step = max_words - overlap         # each piece starts `overlap` words before the last one ended
    for start in range(0, len(words), step):
        pieces.append(" ".join(words[start:start + max_words]))
        if start + max_words >= len(words):   # this piece reached the last word: stop
            break
    return pieces


def pack_lines(text, max_words=MAX_WORDS):
    """Group a section's lines into chunks of at most max_words words, never splitting a line.

    A section's text is lines joined with "\\n" (each line is a paragraph or one table row
    sentence). Add lines to the current chunk while it stays within max_words; when the next
    line would push it over, close the chunk (join its lines with "\\n") and start a new one.
    A line that is longer than max_words on its own goes through split_long_line first,
    and each of its pieces is treated as its own line. Pass it a smaller overlap when the
    chunks are small, so the overlap never swallows the whole piece:
        split_long_line(line, max_words, min(OVERLAP, max_words // 4))

    Returns a list of chunk texts (strings), in order. Empty lines are skipped.
    """
    chunks = []    # finished chunks
    current = []   # lines in the chunk being built
    size = 0       # words in the chunk being built
    for raw in text.split("\n"):
        if not raw.strip():
            continue
        for line in split_long_line(raw, max_words, min(OVERLAP, max_words // 4)):
            n = len(line.split())
            if current and size + n > max_words:   # this line won't fit: close the chunk
                chunks.append("\n".join(current))
                current, size = [], 0
            current.append(line)
            size += n
    if current:                                     # the last chunk is still open
        chunks.append("\n".join(current))
    return chunks


def chunk_id(title, section, n):
    """A short, stable id for chunk number n of a section, e.g. "2015-16-premier-league--league-table--0".

    Lowercase; every run of characters that are not a-z or 0-9 becomes "-"; trim "-" from the ends.
    Join the page part and the section part with "--", then add "--{n}".
    """
    def slug(s):
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

    return f"{slug(title)}--{slug(section)}--{n}"


def make_chunks(section):
    """Turn one section dict into a list of chunk dicts.

    For each text from pack_lines(section["text"]), make:
        {"id": chunk_id(title, section name, n),
         "title": ..., "url": ..., "section": ...,
         "text": f"{title} — {section name}\\n{chunk text}"}
    numbering n from 0 within the section.
    """
    title, name = section["title"], section["section"]
    chunks = []
    for n, text in enumerate(pack_lines(section["text"])):
        chunks.append({
            "id": chunk_id(title, name, n),
            "title": title,
            "url": section["url"],
            "section": name,
            # The header line tells search which page and section bare table rows belong to
            "text": f"{title} — {name}\n{text}",
        })
    return chunks


def main():
    """Read IN_FILE, write every chunk to OUT_FILE (one JSON object per line).

    Print how many chunks you wrote and their average length in words.
    """
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    n_chunks = 0
    n_words = 0
    with open(IN_FILE, encoding="utf-8") as sections, open(OUT_FILE, "w", encoding="utf-8") as out:
        for line in sections:
            for c in make_chunks(json.loads(line)):
                out.write(json.dumps(c, ensure_ascii=False) + "\n")
                n_chunks += 1
                n_words += len(c["text"].split())
    print(f"{n_chunks:,} chunks, {n_words // max(n_chunks, 1)} words on average -> {OUT_FILE}")


if __name__ == "__main__":
    main()
