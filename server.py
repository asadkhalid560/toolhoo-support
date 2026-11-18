"""HTTP API + embeddable chat widget.

Run:
    python -m uvicorn server:app --reload --port 8000

Then add one line to any page on your site:
    <script src="http://localhost:8000/widget.js" defer></script>
"""

import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from config import CHAT_MODEL
from gemini import MissingKey
from rag import HISTORY_TURNS, answer_stream, get_collection, retrieve, backend_status

BASE_DIR = Path(__file__).parent
STATIC = BASE_DIR / "static"

app = FastAPI(title="Support Chatbot API")

# The widget runs on your website's origin, not this one, so the browser needs
# permission to call across. Set ALLOWED_ORIGINS in .env to your real domains —
# "*" is convenient locally and a liability in production, because every request
# spends API quota.
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

_state: dict = {}


def backend():
    """Vector store collection, built once and reused."""
    if "collection" not in _state:
        _state["collection"] = backend_status()
    return _state["collection"]


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/health")
def health():
    try:
        collection = backend()
        return {"ok": True, "records": collection["count"], "source": collection["source"], "model": CHAT_MODEL}
    except MissingKey as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Stream an answer as server-sent events."""

    def events():
        try:
            backend()
            sources = retrieve(req.message, history=[m.model_dump() for m in req.history[-HISTORY_TURNS * 2:]])
            yield sse({
                "type": "sources",
                "items": [
                    {
                        "n": s.n,
                        "source": s.source,
                        "score": round(s.similarity, 3),
                        "preview": s.text[:240],
                    }
                    for s in sources
                ],
            })

            history = [
                {"role": m.role, "content": m.content}
                for m in req.history[-HISTORY_TURNS * 2 :]
            ]
            for delta in answer_stream(req.message, sources, history):
                yield sse({"type": "delta", "text": delta})
            yield sse({"type": "done"})
        except Exception as exc:
            # Surface a readable reason rather than a dead stream.
            yield sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/widget.js")
def widget_js():
    # Served from this origin so one script tag is all a page needs.
    return FileResponse(STATIC / "widget.js", media_type="application/javascript")


@app.get("/")
def demo():
    return FileResponse(STATIC / "demo.html")
