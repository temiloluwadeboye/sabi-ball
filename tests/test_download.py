"""Tests for src/download.py. None of them touch the internet: the Wikipedia API is faked.

Run: pytest
"""

import json
import re

import pytest

from src import download


class FakeResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def no_sleeping(monkeypatch):
    # Real pauses would make the tests slow.
    monkeypatch.setattr(download.time, "sleep", lambda seconds: None)


# --- api_get ---------------------------------------------------------------

def test_api_get_retries_after_429(monkeypatch):
    replies = [FakeResponse(429), FakeResponse(429), FakeResponse(200, {"ok": True})]
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: replies.pop(0))
    assert download.api_get({"action": "query"}) == {"ok": True}


def test_api_get_sends_json_format_and_user_agent(monkeypatch):
    seen = {}

    def fake_get(url, params=None, headers=None, **kwargs):
        seen["params"], seen["headers"] = params, headers
        return FakeResponse(200, {})

    monkeypatch.setattr(download.requests, "get", fake_get)
    download.api_get({"action": "query"})
    assert seen["params"]["format"] == "json"
    assert seen["params"]["formatversion"] == 2
    assert "User-Agent" in seen["headers"]


def test_api_get_waits_out_a_dropped_connection(monkeypatch):
    replies = [download.requests.ConnectionError("no internet"), FakeResponse(200, {"ok": True})]

    def fake_get(*args, **kwargs):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(download.requests, "get", fake_get)
    assert download.api_get({"action": "query"}) == {"ok": True}


def test_api_get_gives_up_eventually(monkeypatch):
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: FakeResponse(429))
    with pytest.raises(Exception):
        download.api_get({"action": "query"}, retries=3)


# --- list_category ---------------------------------------------------------

def test_list_category_follows_continue(monkeypatch):
    pages = [
        {"continue": {"cmcontinue": "page|B", "continue": "-||"},
         "query": {"categorymembers": [{"title": "A"}, {"title": "B"}]}},
        {"query": {"categorymembers": [{"title": "C"}]}},
    ]
    asked = []

    def fake_api_get(params):
        asked.append(dict(params))
        return pages[len(asked) - 1]

    monkeypatch.setattr(download, "api_get", fake_api_get)
    assert download.list_category("Premier League seasons") == ["A", "B", "C"]
    assert asked[0]["cmtitle"] == "Category:Premier League seasons"
    assert asked[1]["cmcontinue"] == "page|B"


# --- olympic_titles --------------------------------------------------------

def test_olympic_titles_split_from_1996():
    titles = download.olympic_titles()
    assert "Football at the 1908 Summer Olympics" in titles
    assert "Football at the 1908 Summer Olympics – Men's tournament" not in titles
    assert "Football at the 2020 Summer Olympics – Men's tournament" in titles
    assert "Football at the 2020 Summer Olympics – Women's tournament" in titles
    assert not any("1932" in t for t in titles)


# --- collect_titles --------------------------------------------------------

def test_collect_titles_removes_repeats_and_keeps_order(monkeypatch):
    by_category = {"Cat1": ["X", "Y"], "Cat2": ["Y", "Z"]}
    monkeypatch.setattr(download, "CATEGORIES", ["Cat1", "Cat2"])
    monkeypatch.setattr(download, "list_category", lambda c: by_category[c])
    monkeypatch.setattr(download, "olympic_titles", lambda: ["O"])
    monkeypatch.setattr(download, "EXTRA_PAGES", ["Z", "E"])
    assert download.collect_titles() == ["X", "Y", "Z", "O", "E"]


# --- page_filename ---------------------------------------------------------

def test_page_filename_is_safe():
    name = download.page_filename("2015–16 Premier League")
    assert name.endswith(".json")
    assert re.fullmatch(r"[A-Za-z0-9_\-]+\.json", name)


def test_page_filename_same_title_same_name():
    assert download.page_filename("FIFA Puskás Award") == download.page_filename("FIFA Puskás Award")


def test_page_filename_similar_titles_differ():
    assert download.page_filename("A.C. Milan") != download.page_filename("AC Milan")


# --- fetch_page ------------------------------------------------------------

def test_fetch_page_uses_reply_title(monkeypatch):
    reply = {"parse": {"title": "Arsenal F.C.", "pageid": 1, "revid": 99, "text": "<p>Gunners</p>"}}
    monkeypatch.setattr(download, "api_get", lambda params: reply)
    page = download.fetch_page("Arsenal")
    assert page["title"] == "Arsenal F.C."
    assert page["url"] == "https://en.wikipedia.org/wiki/Arsenal_F.C."
    assert page["revid"] == 99
    assert page["html"] == "<p>Gunners</p>"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", page["retrieved"])


def test_fetch_page_missing_returns_none(monkeypatch):
    reply = {"error": {"code": "missingtitle", "info": "The page you specified doesn't exist."}}
    monkeypatch.setattr(download, "api_get", lambda params: reply)
    assert download.fetch_page("Football at the 1932 Summer Olympics") is None


# --- main ------------------------------------------------------------------

def test_main_saves_pages_and_skips_existing(monkeypatch, tmp_path):
    monkeypatch.setattr(download, "RAW_DIR", tmp_path)
    monkeypatch.setattr(download, "collect_titles", lambda: ["Old", "New", "Gone"])
    (tmp_path / download.page_filename("Old")).write_text("{}", encoding="utf-8")

    fetched = []

    def fake_fetch(title):
        fetched.append(title)
        if title == "Gone":
            return None
        return {"title": title, "url": "u", "revid": 1, "retrieved": "2026-11-01", "html": "Puskás"}

    monkeypatch.setattr(download, "fetch_page", fake_fetch)
    download.main()

    assert fetched == ["New", "Gone"]  # "Old" was already on disk
    saved = json.loads((tmp_path / download.page_filename("New")).read_text(encoding="utf-8"))
    assert saved["html"] == "Puskás"
    assert not (tmp_path / download.page_filename("Gone")).exists()
