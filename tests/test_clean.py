"""Tests for src/clean.py, using small hand-made HTML snippets shaped like real Wikipedia pages.

Run: pytest tests/test_clean.py
"""

import json

from bs4 import BeautifulSoup

from src import clean


def table(html):
    return BeautifulSoup(html, "html.parser").find("table")


# --- clean_text ------------------------------------------------------------

def test_clean_text_collapses_whitespace():
    assert clean.clean_text("  Leicester\n\n  City  won ") == "Leicester City won"


def test_clean_text_fixes_spaces_around_punctuation():
    assert clean.clean_text("Leicester City , managed by Ranieri .") == "Leicester City, managed by Ranieri."
    assert clean.clean_text("London ( Holloway )") == "London (Holloway)"


# --- remove_junk -----------------------------------------------------------

def test_remove_junk_drops_references_and_edit_links():
    soup = BeautifulSoup(
        '<div><h2>Summary<span class="mw-editsection">[edit]</span></h2>'
        '<p>Kane scored 25<sup class="reference">[1]</sup> goals.</p>'
        '<style>.x{}</style><div class="navbox">Seasons...</div></div>',
        "html.parser",
    )
    clean.remove_junk(soup)
    text = soup.get_text()
    assert "Kane scored 25 goals." in text
    assert "[1]" not in text and "[edit]" not in text
    assert "Seasons" not in text and ".x{}" not in text


# --- infobox_to_lines ------------------------------------------------------

def test_infobox_to_lines():
    box = table(
        '<table class="infobox">'
        '<tr><th colspan="2">Premier League</th></tr>'
        '<tr><th>Champions</th><td>Leicester City<br>1st title</td></tr>'
        '<tr><th>Top goalscorer</th><td>Harry Kane (25 goals)</td></tr>'
        "</table>"
    )
    assert clean.infobox_to_lines(box) == [
        "Champions: Leicester City 1st title",
        "Top goalscorer: Harry Kane (25 goals)",
    ]


# --- header_row_count ------------------------------------------------------

def test_header_row_count_one_and_two():
    one = table("<table><tr><th>Pos</th><th>Team</th></tr><tr><td>1</td><td>Leicester</td></tr></table>")
    two = table(
        "<table><tr><th colspan='2'>Manager of the Month</th></tr>"
        "<tr><th>Manager</th><th>Club</th></tr>"
        "<tr><td>Pellegrini</td><td>Man City</td></tr></table>"
    )
    row_header = table("<table><tr><th>Award</th><th>Winner</th></tr><tr><th>Golden Boot</th><td>Kane</td></tr></table>")
    assert clean.header_row_count(one) == 1
    assert clean.header_row_count(two) == 2
    assert clean.header_row_count(row_header) == 1  # a <th> at the start of a data row is not a header row


# --- table_to_grid ---------------------------------------------------------

def test_table_to_grid_fills_rowspan():
    t = table(
        "<table><tr><th>Rank</th><th>Player</th><th>Goals</th></tr>"
        "<tr><td>1</td><td>Kane</td><td>25</td></tr>"
        "<tr><td rowspan='2'>2</td><td>Agüero</td><td rowspan='2'>24</td></tr>"
        "<tr><td>Vardy</td></tr></table>"
    )
    assert clean.table_to_grid(t) == [
        ["Rank", "Player", "Goals"],
        ["1", "Kane", "25"],
        ["2", "Agüero", "24"],
        ["2", "Vardy", "24"],
    ]


def test_table_to_grid_fills_colspan():
    t = table("<table><tr><th colspan='2'>Manager of the Month</th></tr><tr><td>Ranieri</td><td>Leicester</td></tr></table>")
    assert clean.table_to_grid(t) == [
        ["Manager of the Month", "Manager of the Month"],
        ["Ranieri", "Leicester"],
    ]


# --- grid_to_sentences -----------------------------------------------------

def test_grid_to_sentences_one_header_row():
    grid = [["Pos", "Team", "Pts"], ["1", "Leicester City", "81"], ["2", "Arsenal", ""]]
    assert clean.grid_to_sentences(grid, 1, "League table") == [
        "League table: Pos: 1; Team: Leicester City; Pts: 81.",
        "League table: Pos: 2; Team: Arsenal.",
    ]


def test_grid_to_sentences_two_header_rows():
    grid = [
        ["Month", "Manager of the Month", "Manager of the Month"],
        ["Month", "Manager", "Club"],
        ["August", "Pellegrini", "Manchester City"],
    ]
    assert clean.grid_to_sentences(grid, 2, "Monthly awards") == [
        "Monthly awards: Month: August; Manager of the Month Manager: Pellegrini; "
        "Manager of the Month Club: Manchester City."
    ]


def test_grid_to_sentences_no_header():
    assert clean.grid_to_sentences([["Kane", "25"]], 0, "Scorers") == ["Scorers: Column 1: Kane; Column 2: 25."]


# --- is_results_matrix -----------------------------------------------------

def test_is_results_matrix():
    assert clean.is_results_matrix([["Home \\ Away", "ARS", "AVL"], ["Arsenal", "—", "4–0"]])
    assert not clean.is_results_matrix([["Pos", "Team"], ["1", "Leicester"]])


# --- page_to_sections ------------------------------------------------------

PAGE_HTML = """
<div class="mw-parser-output">
  <table class="infobox"><tr><th>Champions</th><td>Leicester City</td></tr></table>
  <p>The 2015–16 Premier League was the 24th season<sup class="reference">[1]</sup>.</p>
  <div class="mw-heading mw-heading2"><h2>League table</h2><span class="mw-editsection">edit</span></div>
  <table class="wikitable"><tr><th>Pos</th><th>Team</th></tr><tr><td>1</td><td>Leicester City</td></tr></table>
  <div class="mw-heading mw-heading2"><h2>Season statistics</h2></div>
  <div class="mw-heading mw-heading3"><h3>Scoring</h3></div>
  <ul><li>Kane scored 25.</li></ul>
  <div class="mw-heading mw-heading2"><h2>Results</h2></div>
  <table class="wikitable"><tr><th>Home \\ Away</th><th>ARS</th></tr><tr><th>Arsenal</th><td>—</td></tr></table>
  <div class="mw-heading mw-heading2"><h2>References</h2></div>
  <p>Should not appear.</p>
</div>
"""


def test_page_to_sections():
    page = {"title": "2015–16 Premier League", "url": "https://en.wikipedia.org/wiki/2015–16_Premier_League",
            "html": PAGE_HTML}
    sections = clean.page_to_sections(page)
    assert [s["section"] for s in sections] == ["Overview", "League table", "Season statistics > Scoring"]
    assert sections[0]["text"] == "Champions: Leicester City\nThe 2015–16 Premier League was the 24th season."
    assert sections[1]["text"] == "League table: Pos: 1; Team: Leicester City."
    assert sections[2]["text"] == "Kane scored 25."
    assert all(s["title"] == page["title"] and s["url"] == page["url"] for s in sections)
    assert "Should not appear" not in json.dumps(sections)


# --- main ------------------------------------------------------------------

def test_main_writes_jsonl(monkeypatch, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    page = {"title": "T", "url": "u", "revid": 1, "retrieved": "2026-11-01",
            "html": '<div class="mw-parser-output"><p>Puskás won.</p></div>'}
    (raw / "t.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "processed" / "sections.jsonl"
    monkeypatch.setattr(clean, "RAW_DIR", raw)
    monkeypatch.setattr(clean, "OUT_FILE", out)

    clean.main()

    lines = out.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [{"title": "T", "url": "u", "section": "Overview", "text": "Puskás won."}]
