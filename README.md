# Sabi Ball ⚽

**Ask about the beautiful game.** A football question-answering app that answers from Wikipedia and shows the sources behind every answer.

**Try it live: [sabi-ball.streamlit.app](https://sabi-ball.streamlit.app)** (it may take a few seconds to wake up)

*Sabi ball* is Nigerian Pidgin for "to know ball": to really know football.

It is a retrieval-augmented generation (RAG) system: it searches 23,582 passages from 1,201 Wikipedia articles, picks the most relevant ones, and has a language model answer **only** from them. If the passages don't hold the answer, it says so instead of guessing.

**Knowledge as of November 2026.** Answers about seasons still being played may be out of date.

## What it covers

- **Leagues:** Premier League, La Liga, Serie A, Bundesliga, Ligue 1 (every season page plus current clubs)
- **Club competitions:** UEFA Champions League and Europa League (seasons and finals)
- **International:** FIFA World Cup, Euros, AFCON, Copa América, UEFA Nations League, football at the Olympics
- **Awards:** Ballon d'Or, Kopa Trophy, FIFA Puskás Award and others

## How it works

| Step | Script | What it does |
|---|---|---|
| 1 | `src/download.py` | Downloads each Wikipedia page once through the official API (resumable, polite rate limit) |
| 2 | `src/clean.py` | Turns the HTML into plain text, split by section. **Tables become text lines** ("League table: Pos: 1; Team: Leicester City (C); Pld: 38; ... Pts: 81."), so league tables and winners lists can be searched |
| 3 | `src/chunk.py` | Packs each section's lines into passages of up to 250 words (a very long line is split with a 40-word overlap). Each passage starts with its page and section title |
| 4 | `src/embed.py` | Turns every passage into a 512-number vector with Cohere `embed-v4.0` (resumable batches, retries on rate limits) |
| 5 | `src/ask.py` | Embeds the question → takes the 30 closest passages → Cohere `rerank-v3.5` keeps the best 5 → Cohere `command-a` answers from those 5 only |
| 6 | `src/evaluate.py` | Scores the search on 35 questions with known answer pages, with and without the reranker |
| 7 | `app/app.py` | The Streamlit app: question box, answer, and a Sources dropdown linking to each Wikipedia page |

## Results

Retrieval test on 35 questions (`eval/questions.jsonl`): 20 "easy" questions that name the page ("Who won the 2023-24 Bundesliga?") and 15 "hard" ones that don't ("Which final is known as the Miracle of Istanbul?").

| Questions | Search | hit@5 | MRR |
|---|---|---|---|
| Easy (20) | vector only | 1.00 | 0.97 |
| | + reranker | 1.00 | **1.00** |
| Hard (15) | vector only | 1.00 | 0.92 |
| | + reranker | 1.00 | **1.00** |
| All (35) | vector only | 1.00 | 0.95 |
| | + reranker | 1.00 | **1.00** |

- **hit@5:** share of questions where a passage from the right page is in the top 5 (what the answer model sees).
- **MRR (mean reciprocal rank):** 1 if the right page is ranked first, 0.5 if second, and so on, averaged.

The reranker moved the right page to first place on the 3 questions where vector search had it 2nd or 3rd. Limits worth knowing: 35 questions is a small test, and a hit means the right *page* was found, not that the answer was checked word for word. Full results: `eval/results.json`.

## Run it

You need Python 3.12 and a [Cohere API key](https://dashboard.cohere.com/api-keys) (the free trial key works, just slower).

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a file called `.env` in the project folder with one line: `COHERE_API_KEY=your-key`. It is git-ignored, so the key never gets committed.

Build the data (each step can be stopped and restarted):

```bash
python -m src.download     # about 1,200 pages
python -m src.clean
python -m src.chunk
python -m src.embed        # about 250 batches; slow on a trial key because of rate limits
```

Then:

```bash
python -m src.ask "Who won the 2015-16 Premier League?"   # one question in the terminal
python -m src.evaluate                                     # the 35-question test
streamlit run app/app.py                                   # the app, at http://localhost:8501
pytest                                                     # 59 tests, no API key needed
```

## Tests

Every step has tests (`tests/`) that run without network access or an API key: Cohere is replaced by a small fake client, so the tests check the logic (batching, retries, ranking, scoring, HTML escaping) rather than Cohere itself.

## Data and licence

Text comes from [English Wikipedia](https://en.wikipedia.org) under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Every source in the app links back to its Wikipedia page.

So the deployed app can run without rebuilding anything, the repo includes the finished index: `data/processed/chunks.jsonl` (the 23,582 passages, cut from Wikipedia text) and `data/processed/embeddings.npy` (their vectors). Those two files are shared under the same **CC BY-SA 4.0** licence as the Wikipedia text they come from. The raw downloads and intermediate files are not stored; the steps above rebuild them.

## Deploying

The app runs on [Streamlit Community Cloud](https://share.streamlit.io): main file `app/app.py`, Python 3.12, and one secret, `COHERE_API_KEY = "..."`, added in the app's **Settings → Secrets** (never in the repo).
