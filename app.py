"""Streamlit UI for the technical support chatbot."""

import streamlit as st

from config import CHAT_MODEL, TOP_K
from gemini import MissingKey
from rag import answer_stream, drop_index_cache, get_collection, retrieve, backend_status, visible_sources

st.set_page_config(page_title="Technical Support Assistant", page_icon="🛠️")
st.title("🛠️ Technical Support Assistant")


@st.cache_resource
def load_backend():
    """Built once per server process, not on every rerun."""
    return backend_status()


try:
    collection = load_backend()
except MissingKey as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:
    st.error(f"Could not start the backend: {exc}")
    st.stop()

doc_count = collection["count"]

with st.sidebar:
    st.subheader("Knowledge base")
    st.metric("Available records", doc_count)
    st.caption(collection["source"])
    st.caption(f"Model: `{CHAT_MODEL}` · top-{TOP_K} retrieval")
    st.markdown(
        "Local MySQL mode fetches fresh product data for every question."
    )
    if st.button("Reload index", type="primary"):
        drop_index_cache()
        load_backend.clear()
        st.rerun()
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()

if doc_count == 0:
    st.warning(
        "No available records were found in the selected backend."
    )

if "messages" not in st.session_state:
    st.session_state.messages = []


def show_sources(sources: list[dict]) -> None:
    with st.expander("Sources"):
        for s in sources:
            st.markdown(f"**[{s['n']}] {s['source']}** — match {s['score']:.0%}")
            st.caption(s["preview"])


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            show_sources(message["sources"])

if prompt := st.chat_input("Ask a technical question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Only plain role/content pairs go to the model, and not the live turn.
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ]

        rendered: list[dict] = []
        try:
            with st.spinner("Searching the docs..."):
                sources = retrieve(prompt, history=history)
            rendered = [
                {
                    "n": s.n,
                    "source": s.source,
                    "score": s.similarity,
                    "preview": s.text[:300] + ("..." if len(s.text) > 300 else ""),
                }
                for s in visible_sources(sources)
            ]
            response = st.write_stream(answer_stream(prompt, sources, history))
        except Exception as exc:
            response = f"Sorry — the request failed: {exc}"
            st.error(response)

        if rendered:
            show_sources(rendered)

    st.session_state.messages.append(
        {"role": "assistant", "content": response, "sources": rendered}
    )
