"""Ingest PDF documents from ./docs into a local Chroma vector store using LangChain abstractions.

Usage:
    python ingest.py            # incrementally sync new, updated, or deleted PDFs
    python ingest.py --reset    # wipe vector store and re-index from scratch
"""

import argparse
import sys

from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_core.indexing import index
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_OVERLAP, CHUNK_SIZE, DOCS_DIR
from gemini import MissingKey
from rag import get_record_manager, get_vectorstore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="wipe vector store and re-index")
    args = parser.parse_args()

    if not DOCS_DIR.exists():
        print(f"Directory {DOCS_DIR} does not exist.")
        return 1

    # 1. Standard LangChain Directory Loader for PDFs
    print(f"Loading PDFs from {DOCS_DIR}...")
    loader = PyPDFDirectoryLoader(str(DOCS_DIR))
    raw_documents = loader.load()

    if not raw_documents:
        print("No PDF documents found to index.")
        return 1

    # 2. Standard LangChain Text Splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    docs = text_splitter.split_documents(raw_documents)
    print(f"Split {len(raw_documents)} pages into {len(docs)} chunks.")

    try:
        vectorstore = get_vectorstore(reset=args.reset)
        record_manager = get_record_manager()
    except MissingKey as exc:
        print(exc)
        return 1

    # 3. Native LangChain Indexing API
    # Handles deduplication, content hashing, batching, and orphan cleanup automatically.
    print("Indexing documents into vector store...")
    cleanup_mode = "full" if args.reset else "incremental"
    
    result = index(
        docs,
        record_manager,
        vectorstore,
        cleanup=cleanup_mode,
        source_id_key="source",
        force_update=args.reset,
    )

    print(
        f"\nIndexing Complete:\n"
        f"  Added:   {result['num_added']}\n"
        f"  Updated: {result['num_updated']}\n"
        f"  Skipped: {result['num_skipped']}\n"
        f"  Deleted: {result['num_deleted']}"
    )
    return 0 


if __name__ == "__main__":
    sys.exit(main())

