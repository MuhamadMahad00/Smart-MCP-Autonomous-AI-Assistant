"""
main.py — FastAPI Backend
==========================
Endpoints:
  POST /chat         → { "query": "..." }  → { "response": "..." }
  POST /chat/stream  → SSE stream of agent events (tool_start/end, tokens)
  GET  /health       → { "status": "ok" }

Run:
    uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager

os.environ["PYTHONUTF8"] = "1"

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import run_agent, shutdown_agent, stream_agent


# ─────────────────────────────────────────────
# LIFESPAN
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await shutdown_agent()


# ─────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────
app = FastAPI(
    title="MCP AI Assistant",
    description=(
        "Multi-step AI assistant powered by LangGraph + 4 MCP Servers: "
        "DuckDuckGo, Playwright, Airbnb, Filesystem."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Non-streaming chat — returns the full answer in one response."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        response = await asyncio.wait_for(run_agent(request.query), timeout=300)
        return ChatResponse(response=response)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    SSE streaming endpoint.
    Each event is a JSON-encoded line prefixed with 'data: '.
    Event types: tool_start | tool_end | token | error | done
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    async def generate():
        try:
            async for event in stream_agent(request.query):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            # Always send 'done' so the client knows the stream ended
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",      # disable nginx buffering
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "MCP AI Assistant"}
