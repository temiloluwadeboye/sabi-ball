"""Download: save every corpus page from Wikipedia, one JSON file per page.

Run from the project root:
    python -m src.download

Output: data/raw/<page>.json, each holding {title, url, revid, retrieved, html}.
Safe to stop and restart: pages already saved are skipped.

We keep the full HTML (not Wikipedia's plain-text version) because the plain-text
version drops tables, and tables hold league standings, top scorers and award winners.
"""

import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path

import requests

from src.sources import CATEGORIES, EXTRA_PAGES, OLYMPIC_YEARS

API_URL = "https://en.wikipedia.org/w/api.php"
RAW_DIR = Path("data/raw")

# Wikipedia asks every script to say who it is. Without this, requests get blocked.
HEADERS = {"User-Agent": "football-rag/0.1 (portfolio project; github.com/temiloluwadeboye)"}

# Wikipedia's rule: one request at a time, and back off when told "429 Too Many Requests".
PAUSE_SECONDS = 1.0

# If the internet drops, keep waiting for it to come back for this long before giving up.
OFFLINE_LIMIT_MINUTES = 30


def api_get(params, retries=5):
    """Send one request to the Wikipedia API and return the JSON reply as a dict.

    Always add format="json" and formatversion=2 to `params` (formatversion 2 gives simpler JSON).
    Wait PAUSE_SECONDS before every request.
    If the reply is 429, wait longer each time (for example 5, 10, 20, 40 seconds) and try again.
    After `retries` failed tries, raise an error.

    Hint: requests.get(API_URL, params=..., headers=HEADERS, timeout=30), then response.status_code
    and response.json(). Your fetch_page in edmonton-311-analysis/src/extract.py has the same retry shape.
    """
    # Copy the caller's question and add the two settings every request needs.
    params = {**params, "format": "json", "formatversion": 2}

    wait = 5  # seconds to wait after a "slow down" reply; doubles each time
    attempt = 0
    offline_minutes = 0
    while attempt < retries:
        time.sleep(PAUSE_SECONDS)  # be polite: never send requests back-to-back
        try:
            response = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
        except (requests.ConnectionError, requests.Timeout):
            # The internet dropped (Wi-Fi blip, PC waking up). Wait a minute and try again,
            # for up to OFFLINE_LIMIT_MINUTES, without using up the "slow down" retries.
            offline_minutes += 1
            if offline_minutes > OFFLINE_LIMIT_MINUTES:
                raise
            print(f"No connection, waiting 60s ({offline_minutes}/{OFFLINE_LIMIT_MINUTES} min)")
            time.sleep(60)
            continue

        attempt += 1
        if response.status_code == 429:  # Wikipedia says "too many requests"
            print(f"Rate limited, waiting {wait}s (try {attempt}/{retries})")
            time.sleep(wait)
            wait *= 2
            continue  # go round the loop and ask again

        response.raise_for_status()  # any other error (404, 500...) stops here with a clear message
        return response.json()  # success: the reply as a Python dict

    raise RuntimeError(f"Still rate limited after {retries} tries")


def list_category(category):
    """Return the titles of all articles in one Wikipedia category, e.g. "Premier League seasons".

    Ask with: action="query", list="categorymembers", cmtitle="Category:" + category,
              cmtype="page", cmlimit=500
    The titles are in reply["query"]["categorymembers"], each item a dict with a "title".

    A category can have more than 500 pages. Then the reply also has a "continue" key, e.g.
        {"continue": {"cmcontinue": "page|ABC|123", "continue": "-||"}, "query": {...}}
    Add everything inside reply["continue"] to your params and ask again, until there is no "continue".
    """
    params = {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + category,
              "cmtype": "page", "cmlimit": 500}
    titles = []
    while True:
        reply = api_get(params)
        titles += [item["title"] for item in reply["query"]["categorymembers"]]
        if "continue" in reply:
            params = {**params, **reply["continue"]}  # ask again from the bookmark
        else:
            return titles


def olympic_titles():
    """Return the page titles for football at each Summer Olympics in OLYMPIC_YEARS.

    Every year has "Football at the {year} Summer Olympics".
    From 1996 on, also add the two tournament pages:
        "Football at the {year} Summer Olympics – Men's tournament"
        "Football at the {year} Summer Olympics – Women's tournament"
    Careful: the dash is an en dash (–), not a hyphen (-). Wikipedia treats them as different titles.
    """
    titles = []
    for year in OLYMPIC_YEARS:
        base = f"Football at the {year} Summer Olympics"
        titles.append(base)  # every Games has a main page
        if year >= 1996:     # from 1996 there are also separate men's and women's pages
            titles.append(base + " – Men's tournament")
            titles.append(base + " – Women's tournament")
    return titles


def collect_titles():
    """Return one list of every title to download, with no duplicates, in a stable order.

    Combine: every category in CATEGORIES (use list_category), then olympic_titles(), then EXTRA_PAGES.
    Some pages sit in two categories (a final is also in its season's category), so remove repeats
    but keep the first-seen order. Print how many titles each category gave you, so you can spot
    a category name that returned 0.
    """
    all_titles = []
    for category in CATEGORIES:
        titles = list_category(category)
        print(f"{category}: {len(titles)}")
        all_titles += titles
    all_titles += olympic_titles()
    all_titles += EXTRA_PAGES

    # Remove repeats but keep the first-seen order (a set alone would scramble it)
    seen = set()
    unique = []
    for title in all_titles:
        if title not in seen:
            seen.add(title)
            unique.append(title)
    return unique


def page_filename(title):
    """Turn a page title into a safe, unique file name ending in .json.

    "2015–16 Premier League" -> something like "2015-16_premier_league_1a2b3c4d.json"

    Rules:
    - only letters, digits, "-" and "_" (no spaces, slashes or quotes: Windows rejects some of them)
    - the same title always gives the same name (so restarting can find pages already saved)
    - two different titles never give the same name. "A.C. Milan" and "AC Milan" would both
      clean down to "ac_milan", so add the first 8 characters of a hash of the original title:
          hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]
    Hint: re.sub(r"[^a-z0-9]+", "_", ...) does most of the cleaning.
    """
    clean = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    short_hash = hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]
    return f"{clean}_{short_hash}.json"


def fetch_page(title):
    """Download one page's HTML. Return a dict, or None if the page does not exist.

    Ask with: action="parse", page=title, prop="text|revid", redirects=1
    A good reply looks like:
        {"parse": {"title": "Arsenal F.C.", "pageid": 2174, "revid": 123456, "text": "<div>...</div>"}}
    A missing page looks like:
        {"error": {"code": "missingtitle", "info": "The page you specified doesn't exist."}}

    Return:
        {"title": ..., "url": "https://en.wikipedia.org/wiki/" + title with spaces as "_",
         "revid": ..., "retrieved": today's date as "YYYY-MM-DD", "html": ...}
    Use the title from the reply, not the one you asked for: with redirects=1 they can differ.
    """
    params = {"action": "parse", "page": title, "prop": "text|revid", "redirects": 1}
    reply = api_get(params)
    if "error" in reply:  # e.g. "missingtitle": no page by that name
        return None

    page = {}
    page["title"] = reply["parse"]["title"]  # the real name after any redirect
    page["url"] = "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_")
    page["revid"] = reply["parse"]["revid"]
    page["retrieved"] = date.today().isoformat()
    page["html"] = reply["parse"]["text"]
    return page


def main():
    """Download every page in collect_titles() into RAW_DIR.

    - Make RAW_DIR if it does not exist.
    - Skip a title whose file (page_filename) is already there, so a restart continues where it stopped.
    - Save each page with json.dump(..., ensure_ascii=False) and encoding="utf-8" (names like Puskás).
    - Keep a list of titles that came back None and print them at the end.
    - Print progress every 50 pages, e.g. "150/1312 saved".
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    titles = collect_titles()
    print(f"{len(titles)} titles to download")

    missing = []
    for i, title in enumerate(titles, start=1):
        path = RAW_DIR / page_filename(title)
        if path.exists():  # saved on an earlier run
            continue

        page = fetch_page(title)
        if page is None:
            missing.append(title)
            continue

        with open(path, "w", encoding="utf-8") as f:
            json.dump(page, f, ensure_ascii=False)

        if i % 50 == 0:
            print(f"{i}/{len(titles)} saved")

    print(f"Done. {len(titles) - len(missing)} pages in {RAW_DIR}")
    if missing:
        print(f"{len(missing)} titles not found on Wikipedia:", missing)


if __name__ == "__main__":
    main()
