"""
app.py — Streamlit UI
======================
Connects to the FastAPI backend (main.py) on port 8000.

Fixes:
  ✅ User message shows immediately (pending_query pattern)
  ✅ Real-time tool call cards during processing
  ✅ Token-by-token streaming of the final answer
  ✅ Clean dark glassmorphism design

Run:
    streamlit run app.py
"""

import json
import requests
import streamlit as st

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI Assistant | MCP Powered",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --bg-primary:   #0a0a0f;
    --bg-secondary: #11111a;
    --bg-glass:     rgba(255,255,255,0.04);
    --border:       rgba(255,255,255,0.08);
    --accent:       #7c5cfc;
    --accent-glow:  rgba(124,92,252,0.35);
    --accent2:      #00d4ff;
    --text-primary: #f0f0ff;
    --text-muted:   #7878a0;
    --success:      #00e5a0;
}
html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Inter', sans-serif !important;
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse at 20% 10%, rgba(124,92,252,0.12) 0%, transparent 55%),
        radial-gradient(ellipse at 80% 80%, rgba(0,212,255,0.08) 0%, transparent 55%),
        var(--bg-primary) !important;
}
[data-testid="stHeader"]  { background: transparent !important; }
[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text-primary) !important; }
#MainMenu, footer { visibility: hidden; }
[data-testid="stHeaderActionElements"] { display: none; }

/* ── Chat bubbles ── */
.user-bubble {
    display:flex; justify-content:flex-end;
    margin:12px 0; animation:slideInRight 0.3s ease;
}
.user-bubble .bubble-inner {
    background: linear-gradient(135deg,#7c5cfc,#5a3fd4);
    color:#fff; padding:14px 20px;
    border-radius:20px 20px 4px 20px;
    max-width:72%; font-size:0.95rem; line-height:1.65;
    box-shadow:0 4px 24px rgba(124,92,252,0.35);
}
.ai-bubble {
    display:flex; justify-content:flex-start;
    margin:12px 0; animation:slideInLeft 0.3s ease;
}
.ai-bubble .bubble-inner {
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border);
    color: var(--text-primary); padding:14px 20px;
    border-radius:20px 20px 20px 4px;
    max-width:78%; font-size:0.95rem; line-height:1.75;
    backdrop-filter: blur(12px);
}
.avatar {
    width:34px; height:34px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font-size:1rem; flex-shrink:0;
}
.avatar-user { background:var(--accent); margin-left:10px; }
.avatar-ai   { background:linear-gradient(135deg,#00d4ff,#004e8a); margin-right:10px; }

/* ── Tool call card ── */
.tool-card {
    display:flex; align-items:center; gap:14px;
    background: rgba(124,92,252,0.08);
    border: 1px solid rgba(124,92,252,0.22);
    border-radius:12px; padding:12px 16px;
    margin:6px 0; animation:slideInLeft 0.25s ease;
}
.tool-card-icon { font-size:1.3rem; flex-shrink:0; }
.tool-card-info { flex:1; min-width:0; }
.tool-card-name {
    font-size:0.84rem; font-weight:600;
    color:#b8a0fc; margin-bottom:2px;
}
.tool-card-input {
    font-size:0.78rem; color:#7878a0;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.tool-card-badge {
    font-size:0.75rem; font-weight:600;
    padding:3px 10px; border-radius:20px; flex-shrink:0;
}
.badge-running {
    background:rgba(0,212,255,0.12);
    border:1px solid rgba(0,212,255,0.3);
    color:#00d4ff;
    animation:blink 1.4s infinite;
}
.badge-done {
    background:rgba(0,229,160,0.12);
    border:1px solid rgba(0,229,160,0.3);
    color:#00e5a0;
}

/* ── Streaming response bubble ── */
.stream-bubble {
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border);
    color: var(--text-primary);
    padding:14px 20px;
    border-radius:20px 20px 20px 4px;
    max-width:78%; font-size:0.95rem; line-height:1.75;
    backdrop-filter:blur(12px);
    margin:4px 0;
}

/* ── Thinking animation ── */
.thinking-row {
    display:flex; align-items:center; gap:10px;
    margin:12px 0; color:var(--text-muted); font-size:0.88rem;
}
.dot-pulse { display:flex; gap:4px; }
.dot-pulse span {
    width:7px; height:7px; border-radius:50%;
    background:var(--accent); animation:pulse 1.2s infinite ease-in-out;
}
.dot-pulse span:nth-child(2){animation-delay:0.2s;}
.dot-pulse span:nth-child(3){animation-delay:0.4s;}

/* ── Hero ── */
.hero { text-align:center; padding:48px 0 20px; }
.hero-icon {
    font-size:3.5rem; filter:drop-shadow(0 0 24px var(--accent));
    margin-bottom:12px; display:block;
}
.hero h1 {
    font-size:2.4rem; font-weight:700;
    background:linear-gradient(90deg,#fff 30%,var(--accent2));
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    margin:0 0 8px;
}
.hero p { color:var(--text-muted); font-size:1rem; max-width:520px; margin:0 auto; line-height:1.6; }
.chip-row { display:flex; gap:10px; flex-wrap:wrap; justify-content:center; margin-top:22px; }
.chip {
    background:var(--bg-glass); border:1px solid var(--border);
    border-radius:50px; padding:6px 14px; font-size:0.8rem;
    color:var(--text-muted); backdrop-filter:blur(8px);
    display:flex; align-items:center; gap:6px;
}

/* ── Sidebar cards ── */
.sidebar-card {
    background:var(--bg-glass); border:1px solid var(--border);
    border-radius:14px; padding:14px 16px; margin-bottom:12px;
    backdrop-filter:blur(8px);
}
.sidebar-card h4 {
    font-size:0.78rem; font-weight:600; letter-spacing:0.08em;
    text-transform:uppercase; color:var(--accent2); margin:0 0 10px;
}
.tool-item {
    display:flex; align-items:center; gap:10px;
    padding:8px 0; border-bottom:1px solid var(--border); font-size:0.84rem;
}
.tool-item:last-child { border-bottom:none; }
.tool-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.status-badge {
    display:inline-flex; align-items:center; gap:6px;
    background:rgba(0,229,160,0.12); border:1px solid rgba(0,229,160,0.3);
    border-radius:50px; padding:4px 12px; font-size:0.78rem; color:var(--success);
}
.status-dot {
    width:7px; height:7px; border-radius:50%;
    background:var(--success); animation:blink 1.4s infinite;
}

/* ── Buttons ── */
.stButton > button {
    background:linear-gradient(135deg,var(--accent),#5a3fd4) !important;
    border:none !important; border-radius:12px !important;
    color:#fff !important; font-family:'Inter',sans-serif !important;
    font-weight:600 !important; padding:10px 22px !important;
    transition:all 0.2s ease !important;
    box-shadow:0 4px 20px rgba(124,92,252,0.35) !important;
}
.stButton > button:hover { transform:translateY(-2px) !important; }
.stTextInput input {
    background:rgba(255,255,255,0.05) !important;
    border:1px solid var(--border) !important;
    border-radius:14px !important; color:var(--text-primary) !important;
}

/* ── Animations ── */
@keyframes slideInRight { from{opacity:0;transform:translateX(20px)} to{opacity:1;transform:translateX(0)} }
@keyframes slideInLeft  { from{opacity:0;transform:translateX(-20px)} to{opacity:1;transform:translateX(0)} }
@keyframes pulse { 0%,100%{opacity:0.3;transform:scale(0.8)} 50%{opacity:1;transform:scale(1.2)} }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "messages"      not in st.session_state: st.session_state.messages      = []
if "api_url"       not in st.session_state: st.session_state.api_url       = "http://127.0.0.1:8000"
if "pending_query" not in st.session_state: st.session_state.pending_query = None


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def get_tool_display(tool_name: str) -> tuple[str, str]:
    """Return (icon, readable_label) for any MCP tool name."""
    n = tool_name.lower()
    if "duck" in n or ("search" in n and "airbnb" not in n):
        return "🔍", "DuckDuckGo Search"
    if "playwright" in n or "navigate" in n or "browser" in n or "click" in n or "screenshot" in n:
        return "🎭", "Playwright Browser"
    if "airbnb" in n:
        return "🏠", "Airbnb Listings"
    if "write" in n or "create" in n:
        return "✍️", "Filesystem — Write"
    if "read" in n:
        return "📖", "Filesystem — Read"
    if "list" in n or "director" in n:
        return "📁", "Filesystem — List"
    if "file" in n:
        return "📁", "Filesystem"
    return "🔧", tool_name


def build_tool_cards_html(tools_info: dict) -> str:
    """Render HTML for all active/completed tool call cards."""
    cards = []
    for name, info in tools_info.items():
        inp = info["input"]
        if len(inp) > 90:
            inp = inp[:90] + "…"
        badge = (
            '<span class="tool-card-badge badge-done">✅ Done</span>'
            if info["done"]
            else '<span class="tool-card-badge badge-running">⏳ Running</span>'
        )
        cards.append(f"""
        <div class="tool-card">
            <div class="tool-card-icon">{info["icon"]}</div>
            <div class="tool-card-info">
                <div class="tool-card-name">{info["label"]}</div>
                <div class="tool-card-input">{inp}</div>
            </div>
            {badge}
        </div>""")
    return "".join(cards)


def stream_from_backend(query: str, api_url: str):
    """
    Synchronous generator that POSTs to /chat/stream and yields
    parsed SSE event dicts. Streamlit can iterate this in-place,
    updating st.empty() placeholders in real-time.
    """
    try:
        with requests.post(
            f"{api_url}/chat/stream",
            json={"query": query},
            stream=True,
            timeout=300,
        ) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines(decode_unicode=True):
                if raw_line and raw_line.startswith("data: "):
                    try:
                        data = json.loads(raw_line[6:])
                        yield data
                        if data.get("type") in ("done", "error"):
                            return
                    except json.JSONDecodeError:
                        pass
    except requests.exceptions.ConnectionError:
        yield {"type": "error", "content":
               "Cannot connect to backend. Run: uvicorn main:app --reload --port 8000"}
    except requests.exceptions.Timeout:
        yield {"type": "error", "content": "Stream timed out."}
    except Exception as e:
        yield {"type": "error", "content": str(e)}


# ─────────────────────────────────────────────
# CHAT INPUT — captured first so it's always available
# ─────────────────────────────────────────────
prompt = st.chat_input("Ask me anything — search the web, browse sites, find rentals, manage files…")

# If user typed something, save it and trigger a rerun so the
# user message is shown BEFORE the backend call begins.
if prompt and not st.session_state.pending_query:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.pending_query = prompt
    st.rerun()


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:20px 0 10px;">
        <div style="font-size:2.4rem;filter:drop-shadow(0 0 16px #7c5cfc);">🤖</div>
        <div style="font-size:1.1rem;font-weight:700;margin-top:8px;color:#f0f0ff;">MCP AI Assistant</div>
        <div style="font-size:0.78rem;color:#7878a0;">Powered by LangGraph + Groq</div>
    </div>
    <hr style="border-color:rgba(255,255,255,0.08);">
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="sidebar-card">
        <h4>Backend Status</h4>
        <div class="status-badge"><div class="status-dot"></div>Connected — Uvicorn Running</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="sidebar-card">
        <h4>🔧 Active MCP Servers (4)</h4>
        <div class="tool-item"><div class="tool-dot" style="background:#00d4ff;"></div>🔍 DuckDuckGo — Web Search</div>
        <div class="tool-item"><div class="tool-dot" style="background:#7c5cfc;"></div>🎭 Playwright — Browser Automation</div>
        <div class="tool-item"><div class="tool-dot" style="background:#ff6b6b;"></div>🏠 Airbnb — Rental Listings</div>
        <div class="tool-item"><div class="tool-dot" style="background:#ffa94d;"></div>📁 Filesystem — File Read/Write</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="sidebar-card">
        <h4>🧠 LLM Engine</h4>
        <p style="font-size:0.84rem;color:#7878a0;margin:0;line-height:1.7;">
            Model: <strong style="color:#f0f0ff;">Gemini 2.5 Flash</strong><br>
            Provider: <strong style="color:#f0f0ff;">Google</strong><br>
            Framework: <strong style="color:#f0f0ff;">LangGraph ReAct</strong><br>
            Streaming: <strong style="color:#00e5a0;">Enabled ✓</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr style="border-color:rgba(255,255,255,0.08);">', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.8rem;color:#7878a0;margin-bottom:6px;">⚙️ Backend URL</p>', unsafe_allow_html=True)
    api_input = st.text_input("Backend URL", value=st.session_state.api_url, label_visibility="collapsed")
    st.session_state.api_url = api_input

    st.markdown('<div style="margin-top:16px;">', unsafe_allow_html=True)
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_query = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MAIN AREA — hero or chat history
# ─────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="hero">
        <span class="hero-icon">✨</span>
        <h1>AI Assistant</h1>
        <p>Your intelligent companion powered by 4 real-time MCP tools.<br>
           Search the web, browse pages, find rentals, manage files — just ask.</p>
        <div class="chip-row">
            <div class="chip">🔍 Web Search</div>
            <div class="chip">🎭 Browser Automation</div>
            <div class="chip">🏠 Airbnb Lookup</div>
            <div class="chip">📁 File Access</div>
        </div>
    </div>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:24px 0;">
    <p style="text-align:center;color:#7878a0;font-size:0.88rem;">✦ Quick Prompts to Get Started ✦</p>
    """, unsafe_allow_html=True)

    suggestions = [
        "🔍 Search latest news about AI agents",
        "🏠 Find cheap Airbnb listings in Lahore",
        "🌐 Open and summarize https://example.com",
        "📁 List files in the current directory",
        "🔍 Search AI jobs in Pakistan",
        "📝 Save a note to output.txt",
    ]
    cols = st.columns(2)
    for i, s in enumerate(suggestions):
        with cols[i % 2]:
            if st.button(s, use_container_width=True, key=f"sug_{i}"):
                st.session_state.messages.append({"role": "user", "content": s})
                st.session_state.pending_query = s
                st.rerun()
else:
    st.markdown('<div style="padding:20px 0 10px;">', unsafe_allow_html=True)
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="user-bubble">
                <div class="bubble-inner">{msg["content"]}</div>
                <div class="avatar avatar-user">👤</div>
            </div>""", unsafe_allow_html=True)
        else:
            content_html = msg["content"].replace("\n", "<br>")
            st.markdown(f"""
            <div class="ai-bubble">
                <div class="avatar avatar-ai">🤖</div>
                <div class="bubble-inner">{content_html}</div>
            </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# STREAMING PROCESSING — runs while pending_query is set
# Updates tool-call cards and response tokens in real-time.
# ─────────────────────────────────────────────
if st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None

    # Two live-update placeholders: one for tool cards, one for response tokens
    tool_status        = st.empty()
    response_container = st.empty()

    # Show "connecting" while MCP servers spin up
    tool_status.markdown("""
    <div class="thinking-row">
        <div class="avatar avatar-ai" style="width:28px;height:28px;font-size:0.85rem;">🤖</div>
        <span>Connecting to MCP servers…</span>
        <div class="dot-pulse"><span></span><span></span><span></span></div>
    </div>""", unsafe_allow_html=True)

    full_response  = ""
    tools_info     = {}       # { tool_name: {icon, label, input, done} }
    streaming_mode = False    # True once we start receiving answer tokens

    for event in stream_from_backend(query, st.session_state.api_url):
        etype = event.get("type")

        # ── Tool call started ──
        if etype == "tool_start":
            tool_name = event["tool"]
            icon, label = get_tool_display(tool_name)
            tools_info[tool_name] = {
                "icon":  icon,
                "label": label,
                "input": event.get("input", ""),
                "done":  False,
            }
            tool_status.markdown(build_tool_cards_html(tools_info), unsafe_allow_html=True)

        # ── Tool call finished ──
        elif etype == "tool_end":
            tool_name = event["tool"]
            if tool_name in tools_info:
                tools_info[tool_name]["done"] = True
            tool_status.markdown(build_tool_cards_html(tools_info), unsafe_allow_html=True)

        # ── Streaming answer token ──
        elif etype == "token":
            if not streaming_mode:
                streaming_mode = True
                tool_status.empty()    # hide tool cards, response is coming
            full_response += event["content"]
            response_container.markdown(
                f'<div class="ai-bubble"><div class="avatar avatar-ai">🤖</div>'
                f'<div class="stream-bubble">{full_response}▌</div></div>',
                unsafe_allow_html=True,
            )

        # ── Error ──
        elif etype == "error":
            full_response = f"❌ {event.get('content', 'Unknown error')}"
            break

        # ── Stream finished ──
        elif etype == "done":
            break

    # Clear live placeholders
    tool_status.empty()
    response_container.empty()

    # Save final response and re-render as a proper bubble
    if not full_response:
        full_response = "⚠️ No response received. The agent may not have found relevant results."

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.rerun()
