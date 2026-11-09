"""Tests for the text helpers in app/app.py (the page itself is checked by running it).

Run: pytest tests/test_app.py
"""

from app.app import sources_html, sources_label

SOURCES = [
    {"id": "a", "title": "2015–16 Premier League", "section": "Overview", "url": "https://w/a", "score": 0.974},
    {"id": "b", "title": "Leicester City F.C.", "section": "History", "url": "https://w/b", "score": 0.5},
]


def test_sources_html_lists_each_source_with_link_and_score():
    out = sources_html(SOURCES)
    assert out.startswith('<ol class="sources">') and out.endswith("</ol>")
    assert out.count("<li>") == 2
    assert '<a href="https://w/a" target="_blank" rel="noopener">2015–16 Premier League</a>' in out
    assert '<span class="sec">History</span>' in out
    assert ">0.97</span>" in out and ">0.50</span>" in out


def test_sources_html_escapes_text_from_wikipedia():
    src = [{"title": "Brighton & Hove <Albion>", "section": 'Say "hi"', "score": 0.1,
            "url": 'https://en.wikipedia.org/wiki/X"onmouseover="alert(1)'}]
    out = sources_html(src)
    assert "Brighton &amp; Hove &lt;Albion&gt;" in out
    assert '"onmouseover' not in out            # the quote can't break out of the href


def test_sources_html_keeps_brackets_in_urls():
    src = [{"title": "T", "section": "S", "score": 0.8,
            "url": "https://en.wikipedia.org/wiki/1959_South_American_Championship_(Ecuador)"}]
    assert 'href="https://en.wikipedia.org/wiki/1959_South_American_Championship_(Ecuador)"' in sources_html(src)


def test_sources_label():
    assert sources_label(SOURCES) == "Sources · 2 Wikipedia sections"
    assert sources_label(SOURCES[:1]) == "Sources · 1 Wikipedia section"
