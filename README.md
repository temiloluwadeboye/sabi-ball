# Football Knowledge Assistant (RAG)

Ask questions about European and international football and get answers with sources.
Built on Wikipedia text and Cohere (embed, rerank, chat), checked with a 20-question retrieval test.

**Knowledge as of November 2026.** Answers about seasons still being played may be out of date.

## What it covers

- **Leagues:** Premier League, La Liga, Serie A, Bundesliga, Ligue 1 (every season page plus current clubs)
- **Club competitions:** UEFA Champions League, UEFA Europa League (seasons and finals)
- **International:** FIFA World Cup, AFCON, Euros, Copa América, UEFA Nations League, football at the Olympics
- **Awards:** Ballon d'Or, Kopa Trophy, FIFA Puskás Award

About 1,300 articles and about 2.2 million words.

## How it works (plan)

| Step | Script | What it does | Status |
|---|---|---|---|
| 1 | `src/download.py` | Download each Wikipedia page once (HTML) through the official API | in progress |
| 2 | `src/clean.py` | Turn HTML into plain text **and turn tables into sentences** (league tables, winners lists) | |
| 3 | `src/chunk.py` | Split text into ~300-word chunks, each tagged with its page and section | |
| 4 | `src/embed.py` | Embed chunks with Cohere and save the index | |
| 5 | `src/ask.py` | Question → find top chunks → Cohere rerank → Cohere chat answer with citations | |
| 6 | `src/evaluate.py` | 20 hand-written questions with known answers: is the right page in the top 5? | |
| 7 | `app/app.py` | Streamlit app | |

## Run it

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m src.download     # step 1: about 1,300 pages, safe to stop and restart
pytest
```

## Data and licence

Text comes from [English Wikipedia](https://en.wikipedia.org) under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
The downloaded text is **not** stored in this repo; run `python -m src.download` to rebuild it.
Every answer links back to the Wikipedia page it came from.
