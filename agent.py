"""
agent.py — LangGraph ReAct Agent + MCP Tool Integration
========================================================
Uses create_react_agent (LangGraph prebuilt) for reliable multi-step
reasoning. Fixes the Groq tool-validation error by building a fresh
agent per request (cheap) while keeping the MCP client as a singleton
(avoids slow server cold-starts on every query).
"""

import asyncio
import json
import os
import sys
from typing import AsyncIterator

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_groq import ChatGroq  # <-- Groq Library Commented Out
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

# ── Windows encoding fix ──
os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

# ── Constants ──
MCP_CONFIG_PATH = "mcp_config.json"
LLM_MODEL       = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are an intelligent AI assistant with access to multiple real-world tools via MCP servers.

## Available Tools
- **DuckDuckGo Search** — Search the web for current information
- **Playwright** — Browse and interact with any web page
- **Airbnb** — Search rental listings by location and budget
- **Filesystem** — Read, write, and manage local files

CRITICAL TOOL USE INSTRUCTIONS:
1. When calling a tool, you MUST use the exact tool name as provided in the schema (e.g. `duckduckgo_web_search`).
2. DO NOT put arguments or JSON directly inside the tool name field! The tool name must just be the string name.
3. Put the arguments separately in the designated JSON arguments field.
4. If one tool fails, try an alternative or explain the limitation.

Failure to format tool calls properly will cause the system to crash."""


# ─────────────────────────────────────────────
# CONFIG LOADER
# ─────────────────────────────────────────────
def load_mcp_config() -> dict:
    """Read mcp_config.json from the script's directory (or CWD fallback)."""
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, MCP_CONFIG_PATH)
    if not os.path.exists(config_path):
        config_path = MCP_CONFIG_PATH          # fallback to CWD
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# SINGLETON MCP CLIENT
# MultiServerMCPClient is kept alive between requests so the npx
# server processes don't restart on every query (big latency win).
# Tools are fetched fresh per request to avoid stale binding.
# ─────────────────────────────────────────────
_mcp_client: MultiServerMCPClient | None = None
_client_lock = asyncio.Lock()


async def _get_client() -> MultiServerMCPClient:
    """Return the shared MultiServerMCPClient, initialising it once."""
    global _mcp_client
    if _mcp_client is not None:
        return _mcp_client
    async with _client_lock:
        if _mcp_client is not None:
            return _mcp_client
        config = load_mcp_config()
        print(f"[MCP] Creating client for: {list(config.keys())}")
        _mcp_client = MultiServerMCPClient(config)
    return _mcp_client


# ─────────────────────────────────────────────
# GROQ TOOL-CALL SANITIZER (COMMENTED OUT)
# ─────────────────────────────────────────────
# def _sanitize_groq_messages(messages: list) -> list:
#     for m in messages:
#         if isinstance(m, AIMessage):
#             for tc_list in [getattr(m, "tool_calls", []), getattr(m, "invalid_tool_calls", [])]:
#                 for tc in (tc_list or []):
#                     name = tc.get("name", "")
#                     if "{" in name or " " in name: tc["name"] = name.replace("{", " ").split(" ")[0].strip()
#         if isinstance(m, ToolMessage) and m.name:
#             if "{" in m.name or " " in m.name: m.name = m.name.replace("{", " ").split(" ")[0].strip()
#     return messages
#
# class CleanChatGroq(ChatGroq):
#     async def ainvoke(self, input, *args, **kwargs):
#         if isinstance(input, list): input = _sanitize_groq_messages(input)
#         elif hasattr(input, "messages"): input.messages = _sanitize_groq_messages(input.messages)
#         return await super().ainvoke(input, *args, **kwargs)
#     async def astream(self, input, *args, **kwargs):
#         if isinstance(input, list): input = _sanitize_groq_messages(input)
#         elif hasattr(input, "messages"): input.messages = _sanitize_groq_messages(input.messages)
#         async for chunk in super().astream(input, *args, **kwargs): yield chunk
#
# # llm = CleanChatGroq(model="llama-3.3-70b-versatile", temperature=0, streaming=False)


def _make_agent(tools: list):
    # Google Gemini handles MCP tools and complex JSON arguments flawlessly, 
    # requiring no prompt-hacking or sanitization logic.
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


# ─────────────────────────────────────────────
# PUBLIC: non-streaming run
# ─────────────────────────────────────────────
async def run_agent(query: str) -> str:
    """Run the agent and return the final text answer."""
    try:
        client = await _get_client()
        tools  = await client.get_tools()

        if not tools:
            return (
                "❌ No MCP tools loaded. "
                "Ensure Node.js is installed and mcp_config.json is correct."
            )

        print(f"[Agent] {len(tools)} tools: {[t.name for t in tools]}")
        agent  = _make_agent(tools)
        result = await agent.ainvoke({"messages": [HumanMessage(content=query)]})

        # Return last AI message that has text content (not a tool_call)
        for msg in reversed(result["messages"]):
            content    = getattr(msg, "content", None)
            tool_calls = getattr(msg, "tool_calls", None)
            if content and not tool_calls:
                return content

        last = result["messages"][-1]
        return getattr(last, "content", None) or "No response generated."

    except Exception as e:
        global _mcp_client
        _mcp_client = None          # reset so next call reinitialises cleanly
        return f"❌ Agent error: {str(e)}"


# ─────────────────────────────────────────────
# PUBLIC: streaming run
# Yields structured dicts consumed by the FastAPI SSE endpoint.
# ─────────────────────────────────────────────
async def stream_agent(query: str) -> AsyncIterator[dict]:
    """
    Async generator yielding structured event dicts:
      {"type": "tool_start", "tool": str, "input": str}
      {"type": "tool_end",   "tool": str}
      {"type": "token",      "content": str}   ← word-by-word replay of final answer
      {"type": "error",      "content": str}
    The FastAPI wrapper always appends {"type": "done"} after this generator ends.

    Strategy:
      Phase 1 — run the agent with astream_events (streaming=False LLM):
        • emit tool_start / tool_end events in real-time
        • capture final answer text from on_chat_model_end
      Phase 2 — replay the captured answer word-by-word:
        • gives smooth streaming appearance without Groq tool-call validation errors
    """
    try:
        client = await _get_client()
        tools  = await client.get_tools()

        if not tools:
            yield {"type": "error", "content": "No MCP tools available. Check Node.js is installed."}
            return

        print(f"[Stream] {len(tools)} tools loaded: {[t.name for t in tools]}")
        agent = _make_agent(tools)

        # ── Gemini supports true native streaming ──
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=query)]},
            version="v2",
        ):
            kind = event["event"]

            if kind == "on_tool_start":
                yield {
                    "type":  "tool_start",
                    "tool":  event.get("name", "tool"),
                    "input": str(event.get("data", {}).get("input", ""))[:200],
                }

            elif kind == "on_tool_end":
                yield {
                    "type": "tool_end",
                    "tool": event.get("name", "tool"),
                }

            # Stream real natively-generated tokens immediately
            elif kind == "on_chat_model_stream":
                chunk            = event.get("data", {}).get("chunk")
                content          = getattr(chunk, "content", "") if chunk else ""
                tool_call_chunks = getattr(chunk, "tool_call_chunks", []) if chunk else []
                # Only yield text; ignore fragments of tool_calls JSON
                if content and not tool_call_chunks:
                    if isinstance(content, list):
                        # Some Gemini responses pack text in structured blocks
                        for block in content:
                            if isinstance(block, dict) and "text" in block:
                                yield {"type": "token", "content": block["text"]}
                    else:
                        yield {"type": "token", "content": content}

    except Exception as e:
        global _mcp_client
        _mcp_client = None          # reset singleton so next call reinitialises
        yield {"type": "error", "content": f"Agent error: {str(e)}"}


# ─────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────
async def shutdown_agent():
    """Reset the singleton MCP client on app shutdown."""
    global _mcp_client
    _mcp_client = None
    print("[Shutdown] Agent reset.")
