"""Clean: turn each downloaded Wikipedia page (HTML) into plain-text sections.

Run from the project root (after python -m src.download):
    python -m src.clean

Input:  data/raw/*.json        (one page each: title, url, revid, retrieved, html)
Output: data/processed/sections.jsonl
        one line per section: {"title", "url", "section", "text"}

Three kinds of content become text:
- paragraphs and bullet lists, kept as they are
- the infobox (the summary box at the top right), as lines like "Champions: Leicester City"
- tables, one sentence per row, like
  "League table: Pos: 1; Team: Leicester City (C); Pld: 38; W: 23; ... Pts: 81."
  Without this step, the plain text would lose league tables, top scorers and award winners.
"""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

RAW_DIR = Path("data/raw")
OUT_FILE = Path("data/processed/sections.jsonl")

# Bits of the page that are not content: reference markers like [45], "edit" links,
# navigation boxes at the bottom, the CSS inside <style>, and similar.
JUNK_SELECTORS = [
    "sup.reference",
    "span.mw-editsection",
    "style",
    "link",
    "meta",
    "div.navbox",
    "div.navbox-styles",
    "div.shortdescription",
    "div.hatnote",
    "div.reflist",
    "span.sortkey",
    ".noprint",
]

# Stop reading a page when one of these sections starts: everything after is not content.
STOP_SECTIONS = {"References", "Notes", "External links", "See also", "Further reading",
                 "Sources", "Bibliography", "Footnotes", "Citations"}


def clean_text(text):
    r"""Tidy one piece of text from the page.

    - collapse every run of whitespace (spaces, tabs, newlines, non-breaking spaces) into one space
    - remove a space BEFORE , . ; : ) ]      "Leicester City , managed"  -> "Leicester City, managed"
    - remove a space AFTER ( [               "London ( Holloway )"       -> "London (Holloway)"
    - strip spaces at the start and end

    Hint: three re.sub calls, then .strip(). r"\s+" matches any run of whitespace,
    and r"\s+([,.;:)\]])" with the replacement r"\1" keeps the punctuation but drops the space.
    """
    # TODO
    raise NotImplementedError


def remove_junk(soup):
    """Delete every element matching JUNK_SELECTORS from the page, in place. Return nothing.

    Hint: soup.select(selector) finds them; element.decompose() deletes one.
    """
    # TODO
    raise NotImplementedError


def infobox_to_lines(table):
    """Turn the infobox table into lines like "Champions: Leicester City 1st Premier League title".

    Each row (tr) that has both a <th> (the label) and a <td> (the value) becomes one
    "label: value" line. Skip rows missing either one (the title row, the image row).
    Run both parts through clean_text. Use cell.get_text(" ") so words in different
    tags do not get glued together.
    """
    # TODO
    raise NotImplementedError


def header_row_count(table):
    """Return how many rows at the top of the table are header rows.

    A header row is a <tr> where EVERY cell is a <th>. Count from the top and stop at the first
    row that has a <td>. Most tables have 1 header row; some (like "Monthly awards") have 2.
    """
    # TODO
    raise NotImplementedError


def table_to_grid(table):
    """Turn an HTML table into a list of rows, each a list of cell texts, with merged cells filled in.

    In HTML, a cell with rowspan="2" covers two rows, and the row below has one cell FEWER.
    Example (two players tied for 2nd):
        <tr><td rowspan="2">2</td><td>Agüero</td></tr>
        <tr><td>Lukaku</td></tr>
    must become  [["2", "Agüero"], ["2", "Lukaku"]]   (not [["2", "Agüero"], ["Lukaku"]])

    colspan="2" means the cell covers two columns: put its text in both.

    One way to do it:
    - keep a dict `carry` of {(row_number, column_number): text} for cells coming down from above
    - for each row, keep a column counter `c` starting at 0
    - before placing each cell, while (row, c) is in carry: append that carried text and move c on
    - place the cell's text colspan times; for each extra row it covers, add it to carry
    - after the last cell, empty any carry left for this row (a merged cell in the last column)

    rowspan/colspan come as strings ("2"), so turn them into ints; treat a missing one as 1.
    Run every cell through clean_text(cell.get_text(" ")).
    """
    # TODO
    raise NotImplementedError


def grid_to_sentences(grid, n_header_rows, label):
    """Turn a table grid into one sentence per data row.

    Column names come from the header rows. With 2 header rows, join the two names for each
    column ("Manager of the Month" + "Club" -> "Manager of the Month Club"), but don't repeat a
    name that is the same in both rows (a merged header cell shows up twice).

    Each data row becomes:
        f"{label}: {name1}: {value1}; {name2}: {value2}; ..."  ending with "."
    Skip a cell whose value is empty, or the same as its column name.
    If there are no header rows, use "Column 1", "Column 2", ... as the names.
    """
    # TODO
    raise NotImplementedError


def is_results_matrix(grid):
    """Return True for the big "Home \\ Away" results grid (every team against every team).

    It is 400+ cells of scores with abbreviated team names, which makes poor search text, so we
    skip it. You can spot it because its first cell contains "Home" and "Away".
    """
    # TODO
    raise NotImplementedError


def page_to_sections(page):
    """Turn one downloaded page into a list of sections: [{"title", "url", "section", "text"}, ...].

    1. soup = BeautifulSoup(page["html"], "html.parser"); remove_junk(soup)
    2. The content is the direct children of soup.find("div", class_="mw-parser-output").
       Walk through them in order, keeping the current section name (start with "Overview"):
       - div with class "mw-heading": a new heading. Its <h2>...<h6> text is the name
           (if it has no heading tag at all, ignore it).
           h2 starts a new section ("Season statistics"); h3-h6 is a sub-part, so name the
           section "Season statistics > Scoring". If the h2 name is in STOP_SECTIONS, stop walking.
       - p, ul, ol, dl: add clean_text(child.get_text(" ")) to the current section
       - table with class "infobox": add infobox_to_lines(...)
       - table with class "wikitable": make the grid, skip it if is_results_matrix,
         otherwise add grid_to_sentences(grid, header_row_count(table), current section name)
       - anything else: ignore it
    3. Join each section's pieces with "\n" and leave out sections whose text is empty.
    Keep sections in page order.
    """
    # TODO
    raise NotImplementedError


def main():
    """Clean every page in RAW_DIR and write all sections to OUT_FILE, one JSON object per line.

    - make OUT_FILE's folder if needed
    - for each raw .json file: load it, page_to_sections, write each section with
      json.dumps(section, ensure_ascii=False) + "\n"
    - print how many pages and sections you wrote, and the 5 pages with the most text
      (a quick check that tables really turned into sentences)
    """
    # TODO
    raise NotImplementedError


if __name__ == "__main__":
    main()
