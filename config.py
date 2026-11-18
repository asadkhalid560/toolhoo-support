"""Shared settings for the LangChain + Gemini support chatbot."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "docs"
CHROMA_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "support_docs"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# Free-tier daily quotas are per-model, and the newest models get the smallest
# allowance — gemini-3.5-flash grants only 20 requests/day. An older Flash-Lite
# is far more generous and is plenty for extracting answers from context.
# If this ever returns NOT_FOUND, Google has retired the model for new users.
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3.1-flash-lite")

# gemini-embedding-001 (not -2): v1 embeds each item of a list separately and
# supports task_type. v2 collapses a list into ONE aggregated vector, which
# would silently corrupt batch ingestion.
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")

# The model supports 128-3072 dimensions. 768 is plenty for a doc-sized corpus
# and keeps the store small; cosine distance makes the scale irrelevant.
#Ek chunk ka meaning 768 numbers ki list (vector) mein convert hoga.
EMBED_DIM = 768

# Chunking, measured in characters. ~1200 chars is roughly 300 tokens, which
# keeps each chunk to a single idea while staying cheap to embed.
#Har chunk mein maximum 1200 characters honge.
CHUNK_SIZE = 1200
#Do consecutive chunks ke beech 200 characters ka common/repeated text hoga.
CHUNK_OVERLAP = 200

# How many chunks to feed the model per question.
TOP_K = 5

# Spreadsheet rows are indexed one record per chunk, not packed together, so a
# question about one product retrieves that product. Records are allowed to be
# larger than CHUNK_SIZE because a row is a coherent unit worth keeping whole.
RECORD_MAX = 3000

# Columns whose values are file paths or URLs. A customer never asks about
# "yg-1-gold-p/3.jpg", and the model cannot show an image in a text answer, so
# these only dilute the embedding and burn quota. Matched case-insensitively
# against the header. Empty this set to index every column.
DROP_HEADERS = {
    "product image(250 x 250)(main images with white background)",
    "product banner(761 x 225)",
    "image 1", "image 2", "image 3", "image 4", "image 5",
    "image 6", "image 7", "image 8", "image 9",
    "catalog", "size chart", "cutting data", "manual", "video url",
    "seo title", "seo description",
    # "Features" is ~2000 characters of near-identical marketing boilerplate on
    # every product. It is what pushes each record over RECORD_MAX and doubles
    # the chunk count, while adding almost nothing a customer asks about — the
    # concrete facts are in Detail, Specification, and the attribute columns.
    # Delete this line to index it again.
    "features",
}

# Import templates often park dropdown vocabularies in extra columns — those
# read as data but describe the template, not the row. Map a filename to the
# 1-based, inclusive column range that holds real data. Files not listed here
# use every column.
SPREADSHEET_COLUMNS = {
    # Cols 2-87 are the product fields. Col 1 is an unlabelled Product Group
    # picklist; cols 88-116 are dropdown option lists (COLOR, HSS, sizes...).
    "template_products_import.xlsx": (2, 87),
}

SYSTEM_PROMPT = """You are a technical support assistant. Answer customer questions \
using ONLY the documentation excerpts provided in the CONTEXT block.

Rules:
- If the context does not contain the answer, say so plainly and suggest what the \
customer could ask instead or point them to human support. Never invent product \
behaviour, version numbers, endpoints, or config keys.
- Cite the sources you used with their bracketed numbers, e.g. [1], [2].
- Be concise and concrete. Prefer numbered steps for procedures and fenced code \
blocks for commands, config, or code.
- Keep the customer's own terminology where possible."""


DATA_SOURCE = os.getenv("DATA_SOURCE", "mysql_api")
TOOLHOO_API_URL = os.getenv("TOOLHOO_API_URL", "http://127.0.0.1:8001/api/chatbot")
