"""Simplified LangChain retrieval + answer generation pipeline."""

import json
from dataclasses import dataclass
from functools import lru_cache
from langchain_chroma import Chroma
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import CHROMA_DIR, COLLECTION_NAME, SYSTEM_PROMPT, TOP_K, DATA_SOURCE
from gemini import get_embeddings, get_llm

MIN_SIMILARITY = 0.25
HISTORY_TURNS = 6

ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT + "\n\nCONTEXT:\n{context}"),
        MessagesPlaceholder("chat_history"),
        ("human", "{question}"),
    ]
)


@dataclass
class Source:
    n: int
    source: str
    chunk: int
    similarity: float
    text: str


# --------------------------------------------------------------------------
# Vector Store & Retrieval
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _cached_vectorstore() -> Chroma:
    """Connect to the persistent Chroma database."""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )






def get_vectorstore(reset: bool = False) -> Chroma:
    store = _cached_vectorstore()
    if reset:
        store.reset_collection()
    return store


def get_collection():
    return get_vectorstore()._collection


def drop_index_cache() -> None:
    _cached_vectorstore.cache_clear()


def get_record_manager() -> 'SQLRecordManager':
    from langchain_classic.indexes import SQLRecordManager

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = (CHROMA_DIR / "record_manager.sqlite").resolve().as_posix()
    manager = SQLRecordManager(
        f"chroma/{COLLECTION_NAME}", db_url=f"sqlite:///{db_path}"
    )
    manager.create_schema()
    return manager


def backend_status() -> dict:
    if DATA_SOURCE == "mysql_api":
        from products import api_get
        return {"source": "Local MySQL / Laravel API", "count": api_get("catalog")["product_count"]}
    return {"source": "Documents", "count": get_collection().count()}


def retrieve(question: str, top_k: int = TOP_K, history: list[dict] | None = None) -> list[Source]:
    """Retrieve top-matching document chunks above the similarity threshold."""
    if DATA_SOURCE == "mysql_api":
        from products import search_products
        result = search_products(question, history, limit=top_k)
        return [Source(n=1, source="Local MySQL / Laravel API", chunk=0,
                       similarity=1.0, text=json.dumps(result, ensure_ascii=False))]
    store = get_vectorstore()
    collection = store._collection
    
    if collection.count() == 0:
        return []

    # Chroma cosine distance to similarity conversion: similarity = 1 - distance
    results = store.similarity_search_with_score(question, k=min(top_k, collection.count()))
    
    sources = []
    for doc, dist in results:
        similarity = 1.0 - float(dist)
        if similarity >= MIN_SIMILARITY:
            meta = doc.metadata or {}
            sources.append(
                Source(
                    n=len(sources) + 1,
                    source=meta.get("source", "unknown"),
                    chunk=int(meta.get("chunk", 0) or 0),
                    similarity=similarity,
                    text=doc.page_content,
                )
            )
    return sources


# --------------------------------------------------------------------------
# Context & Answer Generation
# --------------------------------------------------------------------------

def _format_history(history: list[dict]) -> list:
    """To iska matlab hai Gemini ko previous 6 conversation turns (maximum 12 messages) diye jayenge.."""
    messages = []
    for msg in history[-HISTORY_TURNS * 2:]:
        text = msg.get("content", "")
        if msg.get("role") == "assistant":
            messages.append(AIMessage(content=text))
        else:
            messages.append(HumanMessage(content=text))
    return messages


def answer(question: str, history: list[dict] | None = None) -> tuple[str, list[Source]]:
    # 1. Search relevant documents
    sources = retrieve(question, history=history)
    
    # 2. Convert retrieved documents into a text context
    if sources:
        context = "\n\n".join(f"[{s.n}] (from {s.source})\n{s.text}" for s in sources)
    else:
        context = "(no matching documentation was found)"
    # 3. Connect prompt template with Gemini model

    chain = ANSWER_PROMPT | get_llm()

    # 4. Execute the chain using inputs
    #Lekin RAG mein prompt template useful hai, kyunki aapko retrieved context, question aur conversation history ko structured format mein provide karna hota hai.
    response = chain.invoke(
        {
            "context": context,
            "question": question,
            "chat_history": _format_history(history or []),
        }
    )

    # 5. Return generated answer and retrieved sources    
    return _response_text(response.content), sources


def _response_text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(
        block if isinstance(block, str) else block.get("text", "")
        for block in content
        if isinstance(block, str) or isinstance(block, dict)
    )


def answer_stream(question: str, sources: list[Source], history: list[dict] | None = None):
    context = "\n\n".join(
        f"[{s.n}] (from {s.source})\n{s.text}" for s in sources
    ) or "(no matching documentation was found)"
    chain = ANSWER_PROMPT | get_llm()
    for chunk in chain.stream({
        "context": context,
        "question": question,
        "chat_history": _format_history(history or []),
    }):
        text = _response_text(chunk.content)
        if text:
            yield text

# --------------------------------------------------------------------------
# Terminal CLI
# --------------------------------------------------------------------------

if __name__ == "__main__":
    chat_history: list[dict] = []
    print("Support bot ready. Press Ctrl+C to exit.\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
            
        if not user_input:
            continue
            
        bot_reply, used_sources = answer(user_input, chat_history)
        print(f"\nBot: {bot_reply}")
        
        if used_sources:
            print("Sources: " + ", ".join(f"[{s.n}] {s.source}" for s in used_sources))
        print()
        
        chat_history.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": bot_reply},
        ])

