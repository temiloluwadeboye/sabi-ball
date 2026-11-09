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
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:)\]])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    return text.strip()


def remove_junk(soup):
    """Delete every element matching JUNK_SELECTORS from the page, in place. Return nothing.

    Hint: soup.select(selector) finds them; element.decompose() deletes one.
    """
    for selector in JUNK_SELECTORS:
        for element in soup.select(selector):
            element.decompose()


def infobox_to_lines(table):
    """Turn the infobox table into lines like "Champions: Leicester City 1st Premier League title".

    Each row (tr) that has both a <th> (the label) and a <td> (the value) becomes one
    "label: value" line. Skip rows missing either one (the title row, the image row).
    Run both parts through clean_text. Use cell.get_text(" ") so words in different
    tags do not get glued together.
    """
    lines = []
    for tr in table.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if th and td:
            lines.append(clean_text(th.get_text(" ")) + ": " + clean_text(td.get_text(" "))) 
    return lines    


def header_row_count(table):
    """Return how many rows at the top of the table are header rows.

    A header row is a <tr> where EVERY cell is a <th>. Count from the top and stop at the first
    row that has a <td>. Most tables have 1 header row; some (like "Monthly awards") have 2.
    """
    n = 0
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if all(cell.name == "th" for cell in cells):
            n += 1
        else:
            break
    return n


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
    def span(cell, name):
        # "2" -> 2; Wikipedia sometimes writes "2;" or leaves it out, so read the leading digits
        match = re.match(r"\d+", str(cell.get(name, "1")))
        return int(match.group()) if match else 1

    grid = []
    carry = {}   # {(row, column): text} for cells reaching down from a row above
    for r, tr in enumerate(table.find_all("tr")):
        row, c = [], 0
        for cell in tr.find_all(["th", "td"]):
            # Fill in cells carried down from above before placing this one
            while (r, c) in carry:
                row.append(carry.pop((r, c)))
                c += 1
            text = clean_text(cell.get_text(" "))
            rs, cs = span(cell, "rowspan"), span(cell, "colspan")
            for dc in range(cs):                 # colspan: the text fills cs columns
                row.append(text)
                for dr in range(1, rs):          # rowspan: and reaches down into the next rows
                    carry[(r + dr, c + dc)] = text
            c += cs
        # A merged cell in the last column(s) has no cell after it to trigger the fill above
        while (r, c) in carry:
            row.append(carry.pop((r, c)))
            c += 1
        grid.append(row)
    return grid


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
    width = max((len(r) for r in grid), default=0)

    # Column names: stack each column's header texts, without repeats from merged header cells
    names = []
    for c in range(width):
        parts = []
        for header_row in grid[:n_header_rows]:
            if c < len(header_row) and header_row[c] and header_row[c] not in parts:
                parts.append(header_row[c])
        names.append(" ".join(parts) or f"Column {c + 1}")

    # One sentence per data row: "label: name: value; name: value."
    sentences = []
    for row in grid[n_header_rows:]:
        pieces = [f"{names[i]}: {value}" for i, value in enumerate(row) if value and value != names[i]]
        if pieces:
            sentences.append(f"{label}: " + "; ".join(pieces) + ".")
    return sentences


def is_results_matrix(grid):
    """Return True for the big "Home \\ Away" results grid (every team against every team).

    It is 400+ cells of scores with abbreviated team names, which makes poor search text, so we
    skip it. You can spot it because its first cell contains "Home" and "Away".
    """
    first = grid[0][0] if grid and grid[0] else ""
    return "Home" in first and "Away" in first


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
    soup = BeautifulSoup(page["html"], "html.parser")
    remove_junk(soup)
    root = soup.find("div", class_="mw-parser-output")

    sections = {}             # {section name: [pieces of text]}, kept in page order
    h2 = name = "Overview"    # text before the first heading belongs to "Overview"
    for child in root.find_all(recursive=False):
        classes = child.get("class", [])

        if child.name == "div" and "mw-heading" in classes:
            h = child.find(["h2", "h3", "h4", "h5", "h6"])
            if h is None:
                continue
            heading = clean_text(h.get_text(" "))
            if h.name == "h2":
                if heading in STOP_SECTIONS:   # References, External links...: nothing useful after
                    break
                h2 = name = heading
            else:
                name = f"{h2} > {heading}"      # a sub-heading lives under its h2

        elif child.name in ("p", "ul", "ol", "dl"):
            sections.setdefault(name, []).append(clean_text(child.get_text(" ")))

        elif child.name == "table" and "infobox" in classes:
            sections.setdefault(name, []).extend(infobox_to_lines(child))

        elif child.name == "table" and "wikitable" in classes:
            grid = table_to_grid(child)
            if not is_results_matrix(grid):
                sections.setdefault(name, []).extend(grid_to_sentences(grid, header_row_count(child), name))

    out = []
    for section, pieces in sections.items():
        text = "\n".join(p for p in pieces if p)
        if text:
            out.append({"title": page["title"], "url": page["url"], "section": section, "text": text})
    return out


def main():
    """Clean every page in RAW_DIR and write all sections to OUT_FILE, one JSON object per line.

    - make OUT_FILE's folder if needed
    - for each raw .json file: load it, page_to_sections, write each section with
      json.dumps(section, ensure_ascii=False) + "\n"
    - print how many pages and sections you wrote, and the 5 pages with the most text
      (a quick check that tables really turned into sentences)
    """
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    words_per_page = {}
    n_sections = 0
    with open(OUT_FILE, "w", encoding="utf-8") as file:
        for raw_file in sorted(RAW_DIR.glob("*.json")):
            content = json.loads(raw_file.read_text(encoding="utf-8"))
            sections = page_to_sections(content)
            for section in sections:   # one JSON object per line (JSONL)
                file.write(json.dumps(section, ensure_ascii=False) + "\n")
            n_sections += len(sections)
            words_per_page[content["title"]] = sum(len(s["text"].split()) for s in sections)

    print(f"{len(words_per_page)} pages, {n_sections} sections, {sum(words_per_page.values()):,} words -> {OUT_FILE}")
    biggest = sorted(words_per_page.items(), key=lambda kv: kv[1], reverse=True)[:5]
    print("Most text:", ", ".join(f"{title} ({words:,})" for title, words in biggest))


if __name__ == "__main__":
    main()
