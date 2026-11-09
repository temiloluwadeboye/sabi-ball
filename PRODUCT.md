# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Streamlit (`app/app.py`), styled through Streamlit's theme, custom CSS and custom HTML blocks. Chosen on Claude's recommendation when the user asked for one: it keeps the app in Python, and it can be deployed free on Streamlit Community Cloud as a live link for job applications. A custom web front end was considered and set aside for now.

## Users

Primary: recruiters and hiring managers judging the author's work for data science / ML / AI internship and new-grad roles. They open a link from a CV or application and spend a minute or two; they need to see what the app does, that it works, and how (sources, evaluation) almost at once.

Secondary: football fans who want a quick answer to a factual football question, with sources to check it.

## Product Purpose

A question-answering assistant for European and international football, built on Wikipedia text. It answers only from retrieved passages and shows which source supports which words, so every answer can be checked. Success: a visitor asks a question, gets a short correct answer, and can click through to the Wikipedia section behind it.

## Positioning

Retrieval-augmented generation over a fixed, inspectable corpus: 1,201 Wikipedia articles split into 23,582 passages, searched by Cohere embeddings, reordered by a reranker, answered by a chat model told to use only those passages and to say when the answer is not there. The sources behind each answer sit in a dropdown under it.

## Operating Context

One question at a time; an answer takes a few seconds (embed, search, rerank, chat). Visitors arrive from a CV, a job application or GitHub. Example questions are offered for visitors who don't know what to ask.

## Capabilities and Constraints

- Coverage: the big five European leagues (season pages and current clubs), UEFA Champions League and Europa League (seasons and finals), FIFA World Cup, AFCON, Euros, Copa América, UEFA Nations League, football at the Olympics, Ballon d'Or and related awards.
- Knowledge as of November 2026; seasons still in progress may be out of date.
- Answer output: short answer text, numbered citations after cited phrases, up to 5 sources each with page title, section, link and a relevance score (0 to 1).
- Runs on a Cohere trial key: rate-limited, so heavy use can slow down.
- Text is Wikipedia, CC BY-SA 4.0: attribution must stay visible.

## Brand Commitments

- Name: **Sabi Ball**, Nigerian Pidgin for "to know ball" (to know football well). Shown in caps in the header ("SABI BALL").

## Evidence on Hand

- Retrieval evaluation (`eval/results.json`): 35 questions (20 that name the page, 15 reworded that don't). Right page in the top 5 for all 35; reranking raised mean reciprocal rank from 0.95 to 1.00 overall and from 0.92 to 1.00 on the reworded questions. Small test set; a hit means the right page, not a verified answer.
- No user testimonials, usage numbers or deployment yet: do not invent them.

## Product Principles

1. Every answer is checkable: sources are never hidden.
2. Honest about limits: say when the sources don't hold the answer, and show the knowledge date.
3. Show the mechanism, don't claim it: the page should make the retrieval visible to a technical reviewer.
4. Fast to understand: a first-time visitor knows what to do within seconds.

## Accessibility & Inclusion

Must work well on phones as well as desktop.
