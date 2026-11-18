"""LangChain wrappers for Gemini chat and embeddings."""

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from config import CHAT_MODEL, EMBED_DIM, EMBED_MODEL, GEMINI_API_KEY

# The free tier has a low requests-per-minute ceiling, so ingest in modest batches.
EMBED_BATCH = 32
MAX_RETRIES = 8


class MissingKey(RuntimeError):
    pass


def require_key() -> str:
    if not GEMINI_API_KEY:
        raise MissingKey(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add a key "
            "from https://aistudio.google.com/apikey"
        )
    return GEMINI_API_KEY


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Document embed uses RETRIEVAL_DOCUMENT; queries use RETRIEVAL_QUERY."""
    return GoogleGenerativeAIEmbeddings(
        model=EMBED_MODEL,
        google_api_key=require_key(),
        output_dimensionality=EMBED_DIM,
    )


def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=CHAT_MODEL,
        google_api_key=require_key(),
        temperature=0.2,  # Support answers should be repeatable, not creative.
        max_retries=MAX_RETRIES,
    )
