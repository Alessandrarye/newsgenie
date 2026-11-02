"""NewsGenie Streamlit front end.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import time
import uuid

import streamlit as st

from newsgenie.config import CATEGORIES, load_settings
from newsgenie.graph import ask, build_graph
from newsgenie.responder import GREETING_TEXT

st.set_page_config(page_title="NewsGenie", page_icon="📰", layout="wide")

settings = load_settings()


@st.cache_resource(show_spinner=False)
def get_graph():
    # One compiled graph per server process. Each browser session gets its own
    # thread_id, so conversations never mix even though the graph is shared.
    return build_graph(settings)


graph = get_graph()

# ------------------------------------------------------------------ session state
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.chat = [{"role": "assistant", "content": GREETING_TEXT}]

# ------------------------------------------------------------------ sidebar
pending: tuple[str, str | None] | None = None

with st.sidebar:
    st.title("📰 NewsGenie")
    st.caption("Curated news and quick answers in one place.")

    st.subheader("News categories")
    cols = st.columns(2)
    for i, (label, cat) in enumerate(CATEGORIES.items()):
        if cols[i % 2].button(label, width="stretch", key=f"cat_{cat}"):
            pending = (f"Show me the latest {label.lower()} headlines", cat)

    st.subheader("Options")
    max_articles = st.slider("Articles per request", 3, 10, 6)
    show_reliability = st.toggle("Show reliability ratings", value=True)
    show_trace = st.toggle("Show workflow trace", value=True,
                           help="Shows which LangGraph nodes ran and which provider answered.")

    st.subheader("Service status")
    for name, ok in settings.status().items():
        st.markdown(f"{'✅' if ok else '⚠️'} {name}")
    if not settings.has_llm:
        st.info("No OpenAI key: NewsGenie uses rule-based routing and template answers.")
    if not (settings.has_newsapi or settings.has_gnews):
        st.info("No news API key: headlines come from DuckDuckGo News.")

    st.divider()
    st.caption(f"Session `{st.session_state.thread_id[:8]}` (conversation memory is kept per session)")
    if st.button("🔄 New conversation", width="stretch"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.chat = [{"role": "assistant", "content": GREETING_TEXT}]
        st.rerun()


# ------------------------------------------------------------------ rendering
def render(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("hidden"):
            with st.expander(f"🔎 {len(msg['hidden'])} article(s) hidden for low reliability"):
                for a in msg["hidden"]:
                    flags = ", ".join(a.get("flags") or []) or "low combined score"
                    st.markdown(f"- [{a['title']}]({a['url']}) ({a.get('source', '?')}, "
                                f"score {a.get('reliability', 0):.2f}: {flags})")
        if msg.get("trace") and show_trace:
            meta = " → ".join(msg["trace"])
            st.caption(f"⚙️ {meta} · {msg.get('elapsed', 0):.1f}s")
        if msg.get("errors") and show_trace:
            with st.expander("Fallback details"):
                for e in msg["errors"]:
                    st.markdown(f"- {e}")


st.header("Ask NewsGenie")
for m in st.session_state.chat:
    render(m)

prompt = st.chat_input("Ask a question or request news (e.g. 'latest news on Nvidia')")
if prompt:
    pending = (prompt, None)

if pending:
    text, category = pending
    user_msg = {"role": "user", "content": text}
    st.session_state.chat.append(user_msg)
    render(user_msg)

    with st.spinner("Working on it..."):
        start = time.perf_counter()
        try:
            result = ask(graph, text, st.session_state.thread_id, selected_category=category,
                         max_articles=max_articles, show_reliability=show_reliability)
            reply = {
                "role": "assistant",
                "content": result.get("response") or "Sorry, I came back empty-handed. Please try again.",
                "trace": result.get("trace", []),
                "errors": result.get("errors", []),
                "hidden": result.get("hidden_articles", []) if show_reliability else [],
            }
        except Exception as exc:  # last line of defense: never show a stack trace
            reply = {
                "role": "assistant",
                "content": "Something went wrong while processing that request. "
                           "Your conversation is still here; please try again.",
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
        reply["elapsed"] = time.perf_counter() - start

    st.session_state.chat.append(reply)
    render(reply)
