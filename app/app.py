"""Sabi Ball (Nigerian Pidgin for "to know ball"): type a football question, get an answer, with its sources one click away.

Run from the project root (after python -m src.embed):
    streamlit run app/app.py

It opens in the browser at http://localhost:8501.

The heavy lifting is all in src/ask.py. This file only does three things:
1. Load the Cohere client, the chunks and the vectors ONCE (not on every question).
2. Show the answer as plain text.
3. Keep the sources in a "Sources" dropdown under the answer, each linking to its Wikipedia page.

The look (a striped pitch header over a navy question panel on a white page) is plain HTML and CSS,
added with st.html. Streamlit gives each keyed container a CSS class "st-key-<key>", which is how
the CSS finds the panel.
"""

import html
import os
import sys
from pathlib import Path

# streamlit runs this file directly, so make "from src..." work by adding the project root to the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402
from streamlit.errors import StreamlitSecretNotFoundError  # noqa: E402

from src.ask import ask, load_index  # noqa: E402
from src.embed import get_client  # noqa: E402

EXAMPLES = [
    "Who won the 2015-16 Premier League?",
    "Which final is known as the Miracle of Istanbul?",
    "Which club is nicknamed the Old Lady?",
]

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Figtree:wght@400;500;600&display=swap');
:root{
  --g1:#1f6b3a; --g2:#257a43;
  --panel:#12294f; --field:#0a1a36; --line:#24406e;
  --chalk:#f4f6ef; --mute:#a3b3cf; --accent:#7fd99a; --page-mute:#5b6475;
  /* the football icon beside the name: a line drawing used as a mask, so it takes the chalk-white colour */
  --ball-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.6' stroke-linejoin='round' stroke-linecap='round'%3E%3Ccircle cx='12' cy='12' r='10.2'/%3E%3Cpath d='M12 8.2 15.61 10.83 14.23 15.07 9.77 15.07 8.39 10.83Z' fill='black'/%3E%3Cpath d='M12 8.2V4.7M15.61 10.83 18.94 9.74M14.23 15.07 16.29 17.91M9.77 15.07 7.71 17.91M8.39 10.83 5.06 9.74M12 4.7 9.3 2.3M12 4.7 14.7 2.3M18.94 9.74 21.9 11M18.94 9.74 19.6 6.2M16.29 17.91 15.4 21.6M16.29 17.91 19.9 17.3M7.71 17.91 8.6 21.6M7.71 17.91 4.1 17.3M5.06 9.74 2.1 11M5.06 9.74 4.4 6.2'/%3E%3C/svg%3E");
}
.stApp{background:#ffffff; font-family:"Figtree",system-ui,sans-serif}
.stApp input, .stApp button, .st-key-panel p, .st-key-panel li, .st-key-panel summary, .foot{
  font-family:"Figtree",system-ui,sans-serif}
::selection{background:#bfe8cc; color:#0b1f3f}
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"]{display:none}
[data-testid="stMainBlockContainer"]{padding:0 !important; max-width:none !important}

/* pitch header */
.pitch{position:relative; overflow:hidden; color:var(--chalk); padding:22px 0 132px;
  background:repeating-linear-gradient(90deg,var(--g1) 0 120px,var(--g2) 120px 240px)}
.pitch svg{position:absolute; inset:0; width:100%; height:100%}
.pitch .in{position:relative; max-width:980px; margin:0 auto; padding:0 24px}
.pitch .nav{display:flex; justify-content:space-between; align-items:center; gap:16px; font-size:14px}
.pitch .nav b{font:800 26px "Archivo"; font-stretch:75%; letter-spacing:.02em; text-transform:uppercase}
.pitch .nav > span{opacity:.88}
.pitch .nav b{display:inline-flex; align-items:center; gap:8px}
.pitch .nav .ball{display:block; width:20px; height:20px; flex:none; background:var(--chalk);
  -webkit-mask:var(--ball-icon) center/contain no-repeat; mask:var(--ball-icon) center/contain no-repeat}
.pitch h1{font:900 92px/.9 "Archivo"; font-stretch:62%; text-transform:uppercase; margin:62px 0 14px;
  padding:0; color:var(--chalk); letter-spacing:0}
.pitch p{max-width:600px; font-size:17px; line-height:1.6; opacity:.92; margin:0}

/* navy question panel, pulled up over the pitch */
.st-key-panel{position:relative; z-index:2; width:min(932px, calc(100% - 32px)) !important;
  margin:-86px auto 0 !important; padding:20px !important; background:var(--panel);
  border:1px solid var(--line); border-radius:18px; box-shadow:0 30px 60px -30px rgba(11,31,63,.4);
  color:var(--chalk)}
.st-key-panel p{color:var(--chalk)}
.st-key-panel [data-testid="stForm"]{border:0; padding:0}
.st-key-panel [data-testid="InputInstructions"]{display:none}
.st-key-panel [data-testid="stTextInputRootElement"]{height:56px; background:var(--field) !important;
  border:1.5px solid var(--line) !important; border-radius:12px}
.st-key-panel [data-testid="stTextInputRootElement"]:focus-within{border-color:var(--accent) !important}
.st-key-panel [data-testid="stTextInputRootElement"] *{background:transparent !important}
.st-key-panel input{color:var(--chalk) !important; font-size:17px; caret-color:var(--accent); padding-left:16px}
.st-key-panel input::placeholder{color:#8496b8; opacity:1}
.st-key-panel [data-testid="stBaseButton-primaryFormSubmit"]{height:56px; width:100%; border:0;
  border-radius:12px; background:var(--chalk); color:#0b1f3f; transition:background .15s ease-out}
.st-key-panel [data-testid="stBaseButton-primaryFormSubmit"] p{color:#0b1f3f; font:800 16px "Archivo";
  font-stretch:80%; letter-spacing:.04em; text-transform:uppercase}
.st-key-panel [data-testid="stBaseButton-primaryFormSubmit"]:hover{background:#ffffff}
.st-key-panel [data-testid="stBaseButton-primaryFormSubmit"]:focus-visible{outline:2px solid var(--accent);
  outline-offset:2px}

/* "Try:" example questions, set as underlined text links */
.st-key-examples{gap:6px 14px !important; align-items:baseline}
.st-key-examples > div{width:auto !important; flex:0 0 auto !important}
.st-key-examples .try{color:var(--mute); font-size:14px}
.st-key-examples [data-testid="stBaseButton-tertiary"]{min-height:0; padding:0; border-radius:0;
  border-bottom:1px solid #4a6390}
.st-key-examples [data-testid="stBaseButton-tertiary"] p{color:var(--chalk); font-size:14px}
.st-key-examples [data-testid="stBaseButton-tertiary"]:hover{border-color:var(--accent)}
.st-key-examples [data-testid="stBaseButton-tertiary"]:hover p{color:var(--accent)}

/* answer and sources */
.st-key-answer{border-top:1px solid var(--line); padding-top:20px; margin-top:6px}
.st-key-answer .label{font:800 13px "Archivo"; font-stretch:80%; letter-spacing:.08em;
  text-transform:uppercase; color:var(--accent)}
.st-key-answer [data-testid="stMarkdownContainer"] p, .st-key-answer [data-testid="stMarkdownContainer"] li{
  font-size:21px; line-height:1.5; max-width:46em}
.st-key-panel [data-testid="stExpander"] details{background:var(--field); border:1px solid var(--line);
  border-radius:12px}
.st-key-panel [data-testid="stExpander"] summary{color:var(--chalk); padding:12px 16px}
.st-key-panel [data-testid="stExpander"] summary:hover{color:var(--accent)}
.st-key-panel [data-testid="stExpander"] summary p{font-size:15px; font-weight:600}
.st-key-panel [data-testid="stExpander"] summary span{color:inherit}
.sources{list-style:none; margin:0; padding:0}
.sources li{display:grid; grid-template-columns:1fr auto; gap:12px; padding:10px 0;
  border-top:1px solid var(--line); font-size:15px}
.sources li:first-child{border-top:0}
.sources a{color:var(--chalk); text-decoration:underline; text-decoration-color:#4a6390;
  text-underline-offset:3px}
.sources a:hover{color:var(--accent); text-decoration-color:var(--accent)}
.sources .sec{display:block; color:var(--mute); font-size:13.5px}
.sources .score{color:var(--mute); font-variant-numeric:tabular-nums; font-size:14px}
.st-key-panel [data-testid="stSpinner"] p, .st-key-panel [data-testid="stSpinner"] i{color:var(--mute)}

.foot{max-width:932px; margin:22px auto 34px; padding:0 24px; color:var(--page-mute); font-size:13px}

@media (max-width:640px){
  .pitch h1{font-size:56px; margin-top:40px}
  .pitch{padding-bottom:110px}
  .pitch .nav > span{display:none}
  .st-key-answer [data-testid="stMarkdownContainer"] p{font-size:18px}
}
</style>
"""

PITCH = """
<header class="pitch">
  <svg viewBox="0 0 1440 520" preserveAspectRatio="xMidYMid slice" fill="none"
       stroke="rgba(244,246,239,.55)" stroke-width="3" aria-hidden="true">
    <line x1="1080" y1="0" x2="1080" y2="520"/><circle cx="1080" cy="260" r="150"/>
    <circle cx="1080" cy="260" r="5" fill="rgba(244,246,239,.7)"/>
  </svg>
  <div class="in">
    <div class="nav"><b>Sabi Ball <i class="ball" aria-hidden="true"></i></b><span>Wikipedia · as of November 2026</span></div>
    <h1>Ask about the<br>beautiful game.</h1>
    <p>Europe's top five leagues, the Champions League and Europa League, World Cups, Euros, AFCON,
       Copa América, the Nations League, Olympic football, the Ballon d'Or and the Puskás Award,
       answered from 1,200 Wikipedia articles.</p>
  </div>
</header>
"""

FOOTER = ('<p class="foot">Text from Wikipedia (CC BY-SA 4.0). Search by Cohere embed and rerank, '
          'answers by Cohere Command A. Answers can be wrong, so check the sources.</p>')


@st.cache_resource
def load_resources():
    """Return (co, chunks, vectors), loaded once and kept for every question and every visitor.

    @st.cache_resource is what makes it "once": Streamlit reruns this whole file on every click,
    but a cached function only really runs the first time and returns the saved result after that.
    """
    use_streamlit_secret()
    co = get_client()
    chunks, vectors = load_index()
    return co, chunks, vectors


def use_streamlit_secret():
    """When deployed on Streamlit Community Cloud, the key lives in the app's Secrets, not in .env.

    Copy it into the environment so get_client() finds it the same way it does locally.
    Locally there is no secrets file, and st.secrets raises an error, which we ignore.
    """
    if os.environ.get("COHERE_API_KEY"):
        return
    try:
        os.environ["COHERE_API_KEY"] = st.secrets["COHERE_API_KEY"]
    except (KeyError, FileNotFoundError, StreamlitSecretNotFoundError):
        pass


def sources_html(sources):
    """Return the sources as an HTML list: one item per source, linking to its Wikipedia page.

    Titles and sections come from Wikipedia, so they are escaped before going into HTML
    (a title with "<" or "&" must show as text, not break the page).
    """
    items = []
    for s in sources:
        url = html.escape(s["url"], quote=True)
        title = html.escape(s["title"])
        section = html.escape(s["section"])
        items.append(f'<li><span><a href="{url}" target="_blank" rel="noopener">{title}</a>'
                     f'<span class="sec">{section}</span></span>'
                     f'<span class="score" title="Relevance score from the reranker">{s["score"]:.2f}</span></li>')
    return '<ol class="sources">' + "".join(items) + "</ol>"


def sources_label(sources):
    """The dropdown's label, e.g. "Sources · 5 Wikipedia sections"."""
    n = len(sources)
    return f"Sources · {n} Wikipedia section{'' if n == 1 else 's'}"


# --- what happens on a click (Streamlit runs these before it reruns the page) ---

def submit_question():
    st.session_state["asked"] = st.session_state.get("question", "").strip()


def pick_example(example):
    st.session_state["question"] = example
    st.session_state["asked"] = example


def main():
    st.set_page_config(page_title="Sabi Ball · football answers with sources", page_icon="⚽", layout="wide")
    st.html(STYLE)
    st.html(PITCH)

    with st.container(key="panel"):
        question_panel()
    st.html(FOOTER)


def question_panel():
    """The navy panel: question box, example questions, then the answer and its sources."""
    co, chunks, vectors = load_resources()
    answers = st.session_state.setdefault("answers", {})   # question -> result, so reruns don't re-ask

    with st.form("ask_form", border=False):
        left, right = st.columns([6, 1], vertical_alignment="bottom")
        left.text_input("Your question", key="question", label_visibility="collapsed",
                        placeholder="Ask about any league, cup, final or award")
        right.form_submit_button("Ask", type="primary", on_click=submit_question,
                                 use_container_width=True)

    with st.container(key="examples", horizontal=True):
        st.html('<span class="try">Try:</span>')
        for n, example in enumerate(EXAMPLES):
            st.button(example, key=f"example_{n}", type="tertiary",
                      on_click=pick_example, args=(example,))

    asked = st.session_state.get("asked", "")
    if not asked:
        return

    if asked not in answers:
        with st.spinner("Searching 23,582 passages and writing an answer..."):
            try:
                answers[asked] = ask(asked, co=co, chunks=chunks, vectors=vectors)
            except Exception:
                st.error("Couldn't reach Cohere just now (it may be busy). "
                         "Wait a few seconds and press Ask again.")
                return
    result = answers[asked]

    with st.container(key="answer"):
        st.html('<div class="label">Answer</div>')
        st.markdown(result["answer"])
        if result["sources"]:
            with st.expander(sources_label(result["sources"])):
                st.html(sources_html(result["sources"]))


if __name__ == "__main__":
    main()
