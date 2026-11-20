"""Chroma-backed knowledge base for store policies and buying know-how.

The index is built from ./knowledge on first use and kept in sync afterwards:
chunk ids are content hashes, so unchanged text is never re-embedded, edited
text is replaced and removed text is deleted. That also means a fresh deploy
(where the local Chroma folder starts empty) rebuilds itself automatically.
"""

import hashlib
import threading
from dataclasses import dataclass
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    KNOWLEDGE_COLLECTION,
    KNOWLEDGE_DB,
    KNOWLEDGE_DIR,
    KNOWLEDGE_MAX_CHUNKS,
    KNOWLEDGE_MIN_SIMILARITY,
    KNOWLEDGE_SCORE_BAND,
)
from gemini import get_embeddings

_lock = threading.Lock()
_synced = False


@dataclass
class Chunk:
    source: str
    chunk: int
    similarity: float
    text: str


@lru_cache(maxsize=1)
def _store() -> Chroma:
    return Chroma(
        collection_name=KNOWLEDGE_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(KNOWLEDGE_DB),
        collection_metadata={"hnsw:space": "cosine"},
    )


def _load_chunks() -> tuple[list[Document], list[str]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n## ", "\n\n", "\n", ". ", " ", ""],
    )
    docs: list[Document] = []
    ids: list[str] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8-sig").strip()
        if not text:
            continue
        for i, piece in enumerate(splitter.split_text(text)):
            docs.append(Document(page_content=piece, metadata={"source": path.name, "chunk": i}))
            ids.append(hashlib.sha1(f"{path.name}\n{piece}".encode("utf-8")).hexdigest())
    return docs, ids


def sync() -> dict:
    """Bring the Chroma collection in line with ./knowledge. Safe to call repeatedly."""
    global _synced
    with _lock:
        store = _store()
        docs, ids = _load_chunks()
        existing = set(store.get()["ids"])
        wanted = set(ids)

        stale = list(existing - wanted)
        if stale:
            store.delete(ids=stale)

        new = [(d, i) for d, i in zip(docs, ids) if i not in existing]
        if new:
            store.add_documents([d for d, _ in new], ids=[i for _, i in new])
        _synced = True
        return {"added": len(new), "deleted": len(stale), "total": len(wanted)}


def search(question: str, k: int = KNOWLEDGE_MAX_CHUNKS) -> list[Chunk]:
    """Best chunks for a question: above the floor and close to the top score."""
    if not _synced:
        sync()
    store = _store()
    if store._collection.count() == 0:
        return []
    results = store.similarity_search_with_score(question, k=k)
    best = max((1.0 - float(d) for _, d in results), default=0.0)
    chunks = []
    for doc, dist in results:
        similarity = 1.0 - float(dist)
        if similarity >= KNOWLEDGE_MIN_SIMILARITY and similarity >= best - KNOWLEDGE_SCORE_BAND:
            meta = doc.metadata or {}
            chunks.append(Chunk(
                source=meta.get("source", "unknown"),
                chunk=int(meta.get("chunk", 0) or 0),
                similarity=similarity,
                text=doc.page_content,
            ))
    return chunks


if __name__ == "__main__":
    import sys

    print(sync())
    for q in sys.argv[1:]:
        print(f"\nQ: {q}")
        for c in search(q):
            print(f"  {c.similarity:.2f}  {c.source}#{c.chunk}  {c.text[:70]!r}")
