"""
AT-DJ — Single-page DJ dashboard.
Sidebar : session history (top) + inline settings (bottom).
Main    : Agent Chat | Music Center | Agent Log
Bottom  : Library / Queue / Upload
"""
import sys
from pathlib import Path as _Path
# Ensure project root is on sys.path so 'atdj' is importable regardless of
# how Streamlit is launched (venv direct, uv run, IDE runner, etc.)
_project_root = str(_Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pandas as pd
import streamlit as st
import streamlit.components.v1 as st_components
import atdj.config as cfg
from atdj.config import CATALOG_PATH, CORTINAS_DIR
from atdj.playback.player import PlaybackQueue
from atdj.ui.audio_player import render_audio_player

# ── Constants ────────────────────────────────────────────────────────────────

STYLE_COLORS  = {"TANGO": "#1A5294", "VALS": "#7B2FA0", "MILONGA": "#C44040"}
CHAT_HEIGHT   = 380
_NP_OVERHEAD  = 190
EA_CHART_H    = max(80, CHAT_HEIGHT - _NP_OVERHEAD)
STYLE_ABBREV  = {"TANGO": "T", "VALS": "V", "MILONGA": "M"}

NOW_PLAYING = {
    "title": "El Retirado", "orchestra": "Carlos Di Sarli",
    "singer": "Roberto Rufino", "style": "TANGO", "year": 1942,
    "progress": 0.35, "track_num": "2 / 3", "source": "agent",
}
# Flat per-song playlist for the music center (replaces tanda-grouped structure)
PLAYLIST_STUB = []
TANDA_PALETTE = ["#8B1A1A", "#1A4E8B", "#1A6B2A", "#7B3F00", "#4A1A7B", "#1A6B6B"]
ENERGY_STUB = {}

CATALOG_COLS = ["title", "orchestra", "singer", "style", "year"]
CATALOG_FALLBACK = [
    {"title": "El Flete",             "orchestra": "Juan D'Arienzo",  "singer": "",                "style": "tango",   "year": 1935},
    {"title": "La Puñalada",          "orchestra": "Astor Piazzolla", "singer": "",                "style": "milonga", "year": 1954},
    {"title": "Corazón de Oro",       "orchestra": "Francisco Canaro","singer": "Roberto Maida",   "style": "vals",    "year": 1938},
    {"title": "A La Gran Muñeca",     "orchestra": "Juan D'Arienzo",  "singer": "Alberto Maure",   "style": "tango",   "year": 1940},
    {"title": "Bahía Blanca",         "orchestra": "Carlos Di Sarli", "singer": "",                "style": "tango",   "year": 1947},
    {"title": "Comme Il Faut",        "orchestra": "Osvaldo Fresedo", "singer": "Roberto Ray",     "style": "tango",   "year": 1933},
    {"title": "Milonga Sentimental",  "orchestra": "Aníbal Troilo",   "singer": "F. Fiorentino",   "style": "milonga", "year": 1944},
    {"title": "Organito de la Tarde", "orchestra": "Rodolfo Biagi",   "singer": "Jorge Amor",      "style": "vals",    "year": 1942},
]

PROVIDER_MODELS = {
    "Claude": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"],
    "Gemini": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    # 2026-05-01: Ollama option removed — `atdj/config.get_ui_llm()` only wires
    # Claude (ChatAnthropic) and Gemini (ChatGoogleGenerativeAI). Anything else
    # silently falls through to ChatGoogleGenerativeAI with the wrong API key.
}
KEY_LABELS = {
    "Claude": "Anthropic API Key",
    "Gemini": "Google API Key",
}
CHAT_STUB = "Got it — I'm still warming up. Connect me to the music pool for real responses. _(stub)_"

# ── Playback helpers ─────────────────────────────────────────────────────────
# These are new helpers specific to this UI page — no equivalent exists elsewhere.

def _renumber_tanda_ids(items: list[dict]) -> bool:
    """Re-assign tanda_id by cortina boundary. Heals stale state from before the
    2026-05-01 fix (where every PLAN restarted at tanda_id=0, so multiple stacked
    plans collided and `next_tanda` audio adjustments lumped 12+ tracks together).

    Treats every contiguous run of songs separated by cortinas as one tanda.
    Mutates items in place. Returns True iff any tanda_id was changed.
    """
    changed = False
    next_id = 0
    saw_song_in_current_tanda = False
    for it in items:
        if it.get("type") == "cortina":
            if saw_song_in_current_tanda:
                next_id += 1
                saw_song_in_current_tanda = False
            continue
        if it.get("type") == "song":
            if it.get("tanda_id") != next_id:
                it["tanda_id"] = next_id
                changed = True
            saw_song_in_current_tanda = True
    return changed


def _get_pq() -> PlaybackQueue:
    if "pq_data" not in st.session_state:
        pq = PlaybackQueue(list(PLAYLIST_STUB))
        st.session_state["pq_data"] = pq.to_session_state()
    pq = PlaybackQueue.from_session_state(st.session_state["pq_data"])
    # 2026-05-01: auto-heal colliding tanda_ids on every load. Cheap (one walk).
    # Persists the migration if anything changed so subsequent loads are no-ops.
    if _renumber_tanda_ids(pq.items):
        st.session_state["pq_data"] = pq.to_session_state()
    return pq


def _save_pq(pq: PlaybackQueue) -> None:
    st.session_state["pq_data"] = pq.to_session_state()
    st.session_state["playlist"] = pq.items


def _log(text: str, kind: str = "info") -> None:
    """Append a timestamped entry to the session log. Auto-prefixes with the
    👤 You category (so user actions are visually distinct from agent events)."""
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    if not text.startswith(("👤", "📋", "🎛")):
        text = f"👤 You — {text}"
    st.session_state.setdefault("agent_notifications", []).append(
        {"type": kind, "text": text, "timestamp": ts}
    )


# ── HTML helpers ─────────────────────────────────────────────────────────────

def _badge(text: str, bg: str = "#F5EAEA", color: str = "#8B1A1A") -> str:
    return (
        f'<span style="font-size:10px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.06em;background:{bg};color:{color};'
        f'border-radius:100px;padding:2px 8px">{text}</span>'
    )

def _source_badge(source: str) -> str:
    if source == "user":
        return _badge("👤 You", "#DCFCE7", "#16A34A")
    return _badge("💡 Agent", "#F5F0E8", "#8C6A30")

def _badge_sm(text: str, bg: str, color: str) -> str:
    """Compact badge for playlist rows — tight padding, no letter-spacing."""
    return (
        f'<span style="font-size:12px;background:{bg};color:{color};'
        f'border-radius:100px;padding:1px 5px;flex-shrink:0">{text}</span>'
    )

def _source_icon(source: str) -> str:
    """Icon-only source badge for compact playlist rows."""
    if source == "user":
        return _badge_sm("👤", "#DCFCE7", "#16A34A")
    return _badge_sm("💡", "#F5F0E8", "#8C6A30")

def _cortina_row(item: dict) -> str:
    return (
        f'<div style="display:flex;align-items:center;gap:8px;padding:6px 12px;'
        f'margin-bottom:5px;border:1px solid #E5E5E5;border-radius:6px;background:#F2F2F2">'
        f'<span style="font-size:10px;font-weight:700;letter-spacing:.06em;color:#777777">CORTINA</span>'
        f'<span style="font-size:12px;color:#555555;flex:1">{item["title"]}</span>'
        f'<span style="font-size:12px;color:#999999">{item["duration"]}</span>'
        f'</div>'
    )

def _tanda_card(item: dict, compact: bool = False) -> str:
    clr = STYLE_COLORS.get(item["style"], "#888")
    badge_html = _badge(item["style"], clr + "22", clr)
    src_html   = _source_badge(item.get("source", "agent"))
    singer_line = (
        f'<p style="font-size:12px;color:#888;margin:0 0 3px">Singer: {item["singer"]}</p>'
        if item.get("singer") else ""
    )
    if compact:
        return (
            f'<div style="background:#FFF;border:1px solid #EBEBEB;border-radius:8px;'
            f'padding:10px 14px;margin-bottom:5px">'
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">'
            f'{badge_html}{src_html}</div>'
            f'<p style="font-weight:700;font-size:13px;margin:0 0 1px">{item["orchestra"]}</p>'
            f'<p style="font-size:12px;color:#999;margin:0">{item["decade"]}</p>'
            f'</div>'
        )
    tracks_html = "".join(
        f'<li style="font-size:12px;color:#666;margin:1px 0">{t}</li>'
        for t in item.get("tracks", [])
    )
    return (
        f'<div style="background:#FFF;border:1px solid #EBEBEB;border-radius:8px;'
        f'padding:12px 16px;margin-bottom:5px">'
        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
        f'{badge_html}{src_html}</div>'
        f'<p style="font-weight:700;font-size:12px;margin:0 0 2px">{item["orchestra"]}</p>'
        f'<p style="font-size:12px;color:#999;margin:0 0 2px">{item["decade"]}</p>'
        f'{singer_line}'
        f'<ul style="margin:0;padding-left:14px">{tracks_html}</ul>'
        f'</div>'
    )

def _tanda_color(tanda_id: int) -> str:
    return TANDA_PALETTE[tanda_id % len(TANDA_PALETTE)]

def _hr():
    st.markdown(
        '<hr style="margin:2px 0 2px;border:none;border-top:1px solid #EEEEEE">',
        unsafe_allow_html=True,
    )

def _lbl(text: str):
    """Tiny uppercase section label (10px) — one of the 4 font sizes used site-wide."""
    st.markdown(
        f'<p style="font-size:10px;font-weight:700;color:#AAAAAA;letter-spacing:.08em;'
        f'text-transform:uppercase;margin:4px 0 8px">{text}</p>',
        unsafe_allow_html=True,
    )

def _render_energy_chart(playlist: list, current_index: int = 0):
    """Solid line = played · Dotted line = planned · Hover = song card.
    Cortinas appear as hollow squares (visual fallback at 50%); their underlying
    items keep `energy=None` — the 0.5 is render-only, never written back."""
    import altair as alt

    if not any(item.get("type") in ("song", "cortina") for item in playlist):
        st.markdown(
            '<div style="background:#F9F9F9;border:1px dashed #DEDEDE;border-radius:8px;'
            f'padding:16px;height:{EA_CHART_H}px;display:flex;flex-direction:column;'
            'justify-content:center;align-items:center;text-align:center">'
            '<p style="font-size:13px;color:#AAAAAA;margin:0 0 4px">No energy data yet</p>'
            '<p style="font-size:12px;color:#BBBBBB;margin:0">Plan a session to see the energy arc</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Pre-compute anchor y-values: any item (song OR cortina) that has a known
    # numeric energy. Cortinas don't yet, so in practice this collects songs from
    # the catalog. Used to interpolate the y-position of unknown-energy items so
    # their hollow square sits on the energy curve instead of pinned to 50%.
    # Render-only — never written back to the underlying playlist items.
    _anchor_e_at: dict[int, float] = {}
    for _i, _item in enumerate(playlist):
        _raw = _item.get("energy")
        if _raw is not None:
            try:
                _anchor_e_at[_i] = float(_raw)
            except (ValueError, TypeError):
                pass

    def _interp_y(idx: int) -> float:
        valid = sorted(_anchor_e_at.keys())
        prev_i = max((i for i in valid if i < idx), default=None)
        next_i = min((i for i in valid if i > idx), default=None)
        if prev_i is not None and next_i is not None:
            t = (idx - prev_i) / (next_i - prev_i)
            return _anchor_e_at[prev_i] + t * (_anchor_e_at[next_i] - _anchor_e_at[prev_i])
        if prev_i is not None:
            return _anchor_e_at[prev_i]
        if next_i is not None:
            return _anchor_e_at[next_i]
        return 0.5  # ultimate fallback: no anchors at all

    def _energy_for_render(idx: int, item: dict) -> tuple[float, bool]:
        """Return (display y-position in [0,1], has_real_energy).
        Items with no real energy get an interpolated y based on neighbouring
        anchors — visual smoothing only, the underlying `energy` stays None."""
        raw = item.get("energy")
        if raw is not None:
            try:
                return float(raw), True
            except (ValueError, TypeError):
                pass
        return _interp_y(idx), False

    playing_pos = current_index  # x-axis uses playlist index directly now (cortinas keep their slot)
    records = []
    for idx, item in enumerate(playlist):
        item_type = item.get("type")
        if item_type not in ("song", "cortina"):
            continue
        if item_type == "song":
            decade = f"{(int(item['year']) // 10) * 10}s" if item.get("year") else "—"
            energy_val, has_energy = _energy_for_render(idx, item)
            base_rec = {
                "pos":        idx,
                "type":       "song",
                "title":      item["title"],
                "orchestra":  item["orchestra"],
                "singer":     item.get("singer", "—") or "—",
                "style":      item["style"],
                "decade":     decade,
                "source":     "💡 Agent" if item.get("source") == "agent" else "👤 You",
                "energy":     energy_val,
                "has_energy": has_energy,
                "segment":    "played" if idx <= playing_pos else "planned",
            }
            records.append(base_rec)
            if idx == playing_pos:
                records.append({**base_rec, "segment": "planned"})
        else:  # cortina
            # Underlying item keeps energy=None — the y here is render-only,
            # interpolated between neighbouring songs so the square sits on the curve.
            energy_val, has_energy = _energy_for_render(idx, item)
            records.append({
                "pos":        idx,
                "type":       "cortina",
                "title":      item.get("title", "Cortina"),
                "orchestra":  "—",
                "singer":     "—",
                "style":      "CORTINA",
                "decade":     "—",
                "source":     "💡 Agent" if item.get("source") == "agent" else "👤 You",
                "energy":     energy_val,
                "has_energy": has_energy,
                "segment":    "played" if idx <= playing_pos else "planned",
            })

    df = pd.DataFrame(records)
    base = alt.Chart(df).encode(
        x=alt.X("pos:Q", axis=alt.Axis(title=None, labels=False, ticks=False, grid=False)),
        y=alt.Y("energy:Q",
                scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(title=None, format=".0%", tickCount=3,
                              gridColor="#F5F5F5", domainColor="#DDD")),
        tooltip=[
            alt.Tooltip("title:N",     title="Title"),
            alt.Tooltip("style:N",     title="Style"),
            alt.Tooltip("orchestra:N", title="Orchestra"),
            alt.Tooltip("singer:N",    title="Singer"),
            alt.Tooltip("decade:N",    title="Decade"),
            alt.Tooltip("source:N",    title="Source"),
        ],
    )
    # Lines connect songs only — cortinas are visual markers and shouldn't pull the energy curve through them
    played_line  = base.mark_line(color="#1A5294", strokeWidth=2.5).transform_filter(
        "datum.type == 'song' && datum.segment == 'played'"
    )
    planned_line = base.mark_line(color="#BBBBBB", strokeWidth=2,
                                  strokeDash=[5, 4]).transform_filter(
        "datum.type == 'song' && datum.segment == 'planned'"
    )
    # Known-energy songs: filled circle. Cortinas + unknown-energy songs: hollow square at 50%.
    dots_known = base.mark_circle(size=55, opacity=0.9).transform_filter(
        "datum.type == 'song' && datum.has_energy == true"
    ).encode(
        color=alt.condition(
            alt.datum.segment == "played",
            alt.value("#1A5294"),
            alt.value("#BBBBBB"),
        )
    )
    dots_unknown = base.mark_point(size=50, shape="square", filled=False,
                                   opacity=0.5, strokeWidth=1.5).transform_filter(
        "datum.has_energy == false"
    ).encode(
        color=alt.value("#BBBBBB")
    )
    dots = dots_known + dots_unknown
    st.altair_chart(
        (played_line + planned_line + dots)
        .properties(height=EA_CHART_H)
        .configure_view(strokeWidth=0)
        .interactive(),
        use_container_width=True,
    )

# ── Data helpers ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_catalog() -> pd.DataFrame:
    try:
        df = pd.read_csv(CATALOG_PATH)
        df = df[~df.get("style", pd.Series(dtype=str)).fillna("").eq("")]
        if "notes" in df.columns:
            df = df[~df["notes"].fillna("").str.contains("cortina", case=False)]
        cols = [c for c in CATALOG_COLS if c in df.columns]
        df = df[cols]
        if len(df) >= 4:
            return df.reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame(CATALOG_FALLBACK)[CATALOG_COLS]

@st.cache_data(show_spinner=False)
def _get_rag_catalog():
    """Load the labeled RAG catalog (with *_label columns required by the translator/selector)."""
    from atdj.rag.prompt_to_features import load_catalog
    from atdj.config import REDUCED_CATALOG_PATH
    return load_catalog(str(REDUCED_CATALOG_PATH))


@st.cache_resource(show_spinner=False)
def _get_rag_translator(provider: str):
    """Build the RAG translator once per (process, provider) and reuse it."""
    from atdj.rag.prompt_to_features import build_translator, load_catalog
    from atdj.config import REDUCED_CATALOG_PATH
    df = load_catalog(str(REDUCED_CATALOG_PATH))
    return build_translator(df, provider=provider)


# ── Settings helpers ─────────────────────────────────────────────────────────

def _init_settings():
    if st.session_state.get("settings_initialized"):
        return
    pm = {"claude": "Claude", "gemini": "Gemini"}
    st.session_state["s_provider"] = pm.get(cfg.LLM_PROVIDER, "Claude")
    st.session_state["s_model"]    = cfg.CLAUDE_MODEL
    st.session_state["s_api_key"]  = ""
    st.session_state["settings_initialized"] = True

# ── Sidebar ──────────────────────────────────────────────────────────────────

def _sidebar():
    with st.sidebar:
        st.markdown(
            """<style>
            /* Compact buttons in the sidebar */
            section[data-testid="stSidebar"] div[data-testid="stButton"] button {
                font-size: 12px !important;
                border-radius: 4px !important;
            }
            /* Vertically center sidebar horizontal rows (provider+model selectboxes) */
            section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
                align-items: center !important;
            }
            </style>""",
            unsafe_allow_html=True,
        )

        # ── Settings ──────────────────────────────────────────────────────────
        st.caption("⚙ Settings")
        _init_settings()

        # Provider + Model side by side
        pv_col, md_col = st.columns(2)
        # 2026-05-01: dropped the "Others" option — only Claude and Gemini are
        # wired in the backend (`atdj/config.get_ui_llm()`).
        provider_opts = list(PROVIDER_MODELS.keys())
        cur_provider  = st.session_state.get("s_provider", "Claude")
        with pv_col:
            sel_provider = st.selectbox(
                "Provider", provider_opts,
                index=provider_opts.index(cur_provider) if cur_provider in provider_opts else 0,
                key="sb_provider", label_visibility="collapsed",
            )
        provider = sel_provider
        if provider != cur_provider:
            # Provider changed — clear the key so user enters the correct one
            st.session_state["s_api_key"] = ""
            st.session_state["sb_api_key"] = ""
        st.session_state["s_provider"] = provider

        model_opts = PROVIDER_MODELS.get(provider, []) + ["Others"]
        cur_model  = st.session_state.get("s_model", model_opts[0] if model_opts else "")
        with md_col:
            sel_model = st.selectbox(
                "Model", model_opts,
                index=model_opts.index(cur_model) if cur_model in model_opts else len(model_opts) - 1,
                key="sb_model", label_visibility="collapsed",
            )
        model = sel_model if sel_model != "Others" else st.session_state.get("sb_model_custom", "")
        if sel_model == "Others":
            model = st.text_input("Model name", placeholder="e.g. gpt-4o",
                                  key="sb_model_custom", label_visibility="collapsed")
        st.session_state["s_model"] = model

        st.text_input(
            KEY_LABELS.get(provider, "API Key / Host"),
            value=st.session_state.get("s_api_key", ""),
            type="password", key="sb_api_key", label_visibility="collapsed",
            placeholder=KEY_LABELS.get(provider, "API Key / Host"),
        )
        st.session_state["s_api_key"] = st.session_state.get("sb_api_key", "")

        if provider == "Claude":
            from atdj.config import GEMINI_API_KEY
            if not GEMINI_API_KEY:
                st.info("💡 Add **GEMINI_API_KEY** to .env to enable AI cortina generation via Lyria. Otherwise pool music will be used as fallback.", icon="🎵")

        if st.button("Save Settings", type="primary", use_container_width=True, key="sb_save"):
            st.toast("Settings saved.", icon="✅")

# ── Left column: Agent Chat ──────────────────────────────────────────────────

def _section_chat():
    st.markdown('<div id="agent-col-marker"></div>', unsafe_allow_html=True)
    _lbl("Agent Chat")

    if "chat_msgs" not in st.session_state:
        st.session_state["chat_msgs"] = [
            {"role": "assistant", "content": "Hello! I'm your **A**rgentina **T**ango DJ — or just call me **@DJ**. How would you like to start this session?"},
        ]

    # Chat history — scrollable
    chat_container = st.container(height=CHAT_HEIGHT)
    with chat_container:
        for msg in st.session_state["chat_msgs"]:
            avatar = "👤" if msg["role"] == "user" else "💡"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # Unified input card (Claude-style)
    with st.container(border=True):
        st.markdown('<div id="chat-input-card"></div>', unsafe_allow_html=True)
        _input_key = f"chat_text_input_{st.session_state.get('input_counter', 0)}"
        text_col, _spacer, send_col = st.columns([11, 0.4, 1], vertical_alignment="bottom")
        with text_col:
            msg_text = st.text_area(
                "Message", placeholder="Message the agent…",
                label_visibility="collapsed", key=_input_key,
                height=87,
            )
        with send_col:
            st.markdown('<div id="send-btn-marker"></div>', unsafe_allow_html=True)
            send = st.button("➤", use_container_width=True, key="chat_send", help="Send")

    if send and msg_text.strip():
        # Stash + rerun so the input clears before the long agent call
        st.session_state["_pending_chat_msg"] = {"text": msg_text.strip()}
        st.session_state["input_counter"] = st.session_state.get("input_counter", 0) + 1
        st.session_state.pop(_input_key, None)
        st.rerun()

    _pending = st.session_state.pop("_pending_chat_msg", None)
    if _pending:
        msg_text = _pending["text"]
        st.session_state["chat_msgs"].append(
            {"role": "user", "content": msg_text.strip()}
        )

        # Show the new user message and a reply slot inside the chat container
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg_text.strip())
            with st.chat_message("assistant", avatar="💡"):
                _reply_slot = st.empty()
                _reply_slot.markdown("_Working on it..._")

        from langchain_core.messages import HumanMessage
        from atdj.config import get_ui_llm

        # 2026-05-01: when an audio-adjustment clarification or rejection is
        # open (pending_adjustment is set), the next chat message is OFTEN the
        # user's response to that question — short replies like "cancel" / "1"
        # / "2" / "Too loud" — and bypassing the classifier routes them to the
        # audio graph correctly. But if the user has clearly moved on to a new
        # intent ("plan a Demare tanda", "who is Pugliese", "search ..."), the
        # bypass would trap them in an audio-loop. So bypass only when the
        # message looks like a menu pick; otherwise clear the stale pending
        # state and let the classifier route fresh.
        def _looks_like_menu_pick(msg: str) -> bool:
            m = (msg or "").strip().lower()
            if not m or len(m) > 60:
                return False
            new_intent_signals = (
                "plan ", "play ", "search ", "find ", "add ", "remove ",
                "clear ", "skip ", "what is", "who is", "tell me", "show me",
                "how ", "why ", "when ",
            )
            if any(s in m for s in new_intent_signals):
                return False
            return True

        if st.session_state.get("pending_adjustment") and _looks_like_menu_pick(msg_text):
            is_planning, is_audio_adjust = False, True
        else:
            # If pending was set but user clearly moved on, drop the stale
            # clarification so the audio graph doesn't re-prompt next turn.
            st.session_state.pop("pending_adjustment", None)
            try:
                _llm = get_ui_llm()
                _classify = _llm.invoke([HumanMessage(content=f"""Classify into exactly one category:
PLAN: plan/find/suggest/change music tracks or playlist
ADJUST_AUDIO: audio quality changes (too quiet, too loud, too harsh, more bass, noisy, back to default, use original, reset audio, undo changes)
QUESTION: tango knowledge (history, orchestras, styles)
Message: "{msg_text.strip()}"
Reply with one word only: PLAN, ADJUST_AUDIO, or QUESTION""")])
                label = _classify.content.strip().upper()
                is_planning = "PLAN" in label
                is_audio_adjust = "ADJUST_AUDIO" in label
            except Exception as _ce:
                _reply_slot.markdown(f"_(Classifier error: {_ce}. Treating as Q&A.)_")
                is_planning, is_audio_adjust = False, False

        if is_planning:
            _reply_slot.markdown("_Planning your session..._")
            if True:
                from atdj.agent.graph import build_graph
                from atdj.schemas.session import PlanSession
                from datetime import datetime
                import uuid

                # Build the per-tanda plan FIRST so the graph can be told how many
                # tandas to run and what prompt to use for each one.
                user_prompt_lower = msg_text.strip().lower()
                is_full_session = any(w in user_prompt_lower for w in ["full", "session", "milonga night", "complete", "tonight"])
                if is_full_session:
                    session_plan = [
                        (msg_text.strip() + ", warm opening, low energy", "tango"),
                        ("vals from the 1940s, romantic and smooth", "vals"),
                        ("tango from the 1940s, moderate energy", "tango"),
                        ("milonga, fun and rhythmic", "milonga"),
                        ("tango from the 1940s, energetic", "tango"),
                        ("vals from the 1940s, elegant", "vals"),
                        ("tango from the 1940s, dramatic and intense", "tango"),
                        ("tango from the 1940s, gentle closing", "tango"),
                    ]
                else:
                    detected_style = "tango"
                    for s in ["vals", "milonga", "tango"]:
                        if s in user_prompt_lower:
                            detected_style = s
                            break
                    session_plan = [(msg_text.strip(), detected_style)]

                session = PlanSession(
                    id=str(uuid.uuid4()),
                    name=msg_text.strip()[:50],
                )
                graph = build_graph()
                initial_state = {
                    "messages": [], "session": session,
                    "current_tanda_index": 0, "upcoming_tandas": [], "pending_feedback": [],
                    "needs_cortina": False, "session_complete": False, "feedback_pending": False,
                    "candidate_tracks": [], "current_tanda_draft": None, "last_agent_action": None,
                    "qa_question": None, "qa_answer": None, "error_message": None, "retry_count": 0,
                    "agent_log": [], "activity_log": [],
                    "selected_cortinas": [],
                    "session_plan": session_plan,
                    "picked_tracks": [],
                }
                final_state = graph.invoke(initial_state)

                # Hand the per-node log entries off to the Session Log panel.
                for entry in final_state.get("activity_log", []):
                    st.session_state.setdefault("activity_log", []).append(entry)

                new_playlist = []
                picked_per_tanda = final_state.get("picked_tracks") or []
                # Load pq up front so the cortina-title resolver below can use it.
                pq = _get_pq()
                # Offset tanda_id by the max already in the playlist so each PLAN run
                # gets globally unique ids. Without this, every plan restarts at 0 and
                # `next_tanda` audio adjustments collapse all songs with the same
                # per-plan index across every plan into one giant target set.
                _existing_max_tid = max(
                    (p.get("tanda_id", -1) for p in pq.items if p.get("type") == "song"),
                    default=-1,
                )
                _tanda_id_offset = _existing_max_tid + 1
                for tanda_idx, tanda_tracks in enumerate(picked_per_tanda):
                    if not tanda_tracks:
                        continue
                    style_for_tanda = (
                        session_plan[tanda_idx][1] if tanda_idx < len(session_plan) else "tango"
                    )
                    for i, track in enumerate(tanda_tracks):
                        new_playlist.append({
                            "type": "song",
                            "title": track.get("title", "Unknown"),
                            "playing": tanda_idx == 0 and i == 0,
                            "style": str(track.get("style", style_for_tanda)).upper(),
                            "orchestra": track.get("orchestra", ""),
                            "singer": track.get("singer", "") if str(track.get("singer", "")) != "nan" else "",
                            "year": int(track.get("year", 0)) if track.get("year") and str(track.get("year")) != "nan" else 0,
                            "duration": str(int(track.get("duration_seconds", 0) // 60)) + ":" +
                                    str(int(track.get("duration_seconds", 0) % 60)).zfill(2),
                            "energy": track.get("energy"),
                            "source": "agent",
                            "tanda_id": _tanda_id_offset + tanda_idx,
                        })
                    if tanda_idx < len(picked_per_tanda) - 1:
                        # 2026-05-01: read the agent's actual cortina selection from
                        # state["selected_cortinas"] (one entry per cortina_selector
                        # call, in order). The selection algorithm in
                        # atdj/agent/nodes.py:cortina_selector currently returns the
                        # placeholder `default_cortina` because the song catalog CSV
                        # has no cortina rows — that gets a separate tune later.
                        # For now: take the agent's title, then run it through the
                        # PlaybackQueue resolver to get the file the player will
                        # actually serve. Use that file's stem as the displayed
                        # title so display == playback (no silent mismatch).
                        _agent_cortinas = final_state.get("selected_cortinas") or []
                        if tanda_idx < len(_agent_cortinas):
                            _cor = _agent_cortinas[tanda_idx]
                            _agent_title = _cor.get("title") or _cor.get("filename") or "Cortina"
                        else:
                            _agent_title = "Cortina"
                        _resolved_path = pq.resolve_file_path({"type": "cortina", "title": _agent_title})
                        _cortina_title = _Path(_resolved_path).stem if _resolved_path else _agent_title
                        new_playlist.append({
                            "type": "cortina", "title": _cortina_title,
                            "duration": "0:20", "source": "agent",
                        })

                if new_playlist and not is_full_session:
                    # Generate a closing cortina for single-tanda plans
                    from atdj.config import get_ui_api_key, get_ui_provider, GEMINI_API_KEY
                    from atdj.cortina.generator import _summarize_tanda
                    from atdj.cortina.pool import find_best_cortina
                    from datetime import datetime as _dt
                    _provider = get_ui_provider()
                    _api_key = (get_ui_api_key() if _provider == "Gemini" else "") or GEMINI_API_KEY
                    if picked_per_tanda:
                        if _api_key:
                            try:
                                from atdj.cortina.generator import generate_cortina
                                from atdj.config import ROOT_DIR
                                _cortina = generate_cortina(
                                    prev_tracks=picked_per_tanda[0],
                                    next_style=None,
                                    output_dir=ROOT_DIR / "data" / "cortinas" / "generated",
                                    api_key=_api_key,
                                )
                                new_playlist.append(_cortina)
                                st.session_state.setdefault("agent_notifications", []).append({
                                    "type": "info",
                                    "text": f"🎵 CORTINA — Generated via Lyria ({_cortina.get('title', 'Cortina')})",
                                    "timestamp": _dt.now().strftime("%H:%M:%S"),
                                })
                            except Exception as _e:
                                # Lyria failed — fall back to pool
                                _summary = _summarize_tanda(picked_per_tanda[0])
                                _cortina = find_best_cortina(_summary)
                                new_playlist.append(_cortina)
                                st.session_state.setdefault("agent_notifications", []).append({
                                    "type": "warning",
                                    "text": f"🎵 CORTINA — Lyria failed, using pool ({_cortina.get('title', 'Cortina')})",
                                    "timestamp": _dt.now().strftime("%H:%M:%S"),
                                })
                        else:
                            # No Gemini key — use pool directly
                            _summary = _summarize_tanda(picked_per_tanda[0])
                            _cortina = find_best_cortina(_summary)
                            new_playlist.append(_cortina)
                            st.session_state.setdefault("agent_notifications", []).append({
                                "type": "info",
                                "text": f"🎵 CORTINA — Selected from pool ({_cortina.get('title', 'Cortina')})",
                                "timestamp": _dt.now().strftime("%H:%M:%S"),
                            })

                if new_playlist:
                    # Append to the existing queue instead of overwriting it,
                    # so successive plans stack rather than replacing the previous tanda.
                    pq = _get_pq()
                    pq.items.extend(new_playlist)
                    _save_pq(pq)

                    # 2026-05-01: removed the auto-enhance-on-PLAN hook + Quality
                    # Enhance toggle. Audio enhancement now ONLY fires from the chat
                    # path (atdj/audio/adjustment_graph.py).

                songs = [t for t in new_playlist if t["type"] == "song"]
                if songs:
                    orchestras = list(dict.fromkeys([s["orchestra"] for s in songs if s.get("orchestra")]))
                    styles = list(dict.fromkeys([s["style"] for s in songs if s.get("style")]))
                    summary = (
                        f"✅ Done! I've planned **{len(songs)} tracks**.\n\n"
                        f"**Orchestras:** {', '.join(orchestras[:4])}\n\n"
                        f"**Styles:** {', '.join(styles)}\n\n"
                        f"Check the **Full Playlist** on the left!"
                    )
                else:
                    summary = "⚠️ Couldn't find enough tracks. Try a different prompt!"

            _reply_slot.markdown(summary)
            st.session_state["chat_msgs"].append({"role": "assistant", "content": summary})

        elif is_audio_adjust:
            from atdj.audio.adjustment_graph import build_adjustment_graph, AdjustmentState
            from atdj.config import PROCESSED_DIR

            pq = _get_pq()
            resolved_paths = {}
            for i, item in enumerate(pq.items):
                if item.get("type") == "song":
                    rp = pq.resolve_raw_path(item)
                    if rp:
                        resolved_paths[i] = rp

            pending = st.session_state.pop("pending_adjustment", None)
            if pending:
                initial = {
                    **pending,
                    "user_message": msg_text.strip(),
                    "needs_clarification": False,
                    "rejected": False,
                }
            else:
                initial = {
                    "user_message": msg_text.strip(),
                    "playlist": pq.items,
                    "current_index": pq.current_index,
                    "output_dir": str(PROCESSED_DIR),
                    "resolved_paths": resolved_paths,
                    "scope": None, "feature": None, "direction": None,
                    "magnitude": None, "target_name": None,
                    "needs_clarification": False,
                    "clarification_question": "",
                    "clarification_options": [],
                    "rejected": False,
                    "rejection_options": [],
                    "target_indices": [],
                    "reference_params": None,
                    "computed_overrides": [],
                    "execution_results": [],
                    "reply": "",
                    "activity_log": [],
                }

            adj_graph = build_adjustment_graph()
            _reply_slot.markdown("_Analyzing and enhancing audio..._")
            final = adj_graph.invoke(initial)

            if final.get("needs_clarification") or final.get("rejected"):
                st.session_state["pending_adjustment"] = {
                    k: v for k, v in final.items()
                    if k not in ("reply", "execution_results", "activity_log")
                }

            for entry in final.get("activity_log", []):
                # Only surface entries flagged as user-visible summaries; the JSON
                # log file still receives every sub-step for fault tracking.
                if not entry.get("summary"):
                    continue
                st.session_state.setdefault("agent_notifications", []).append(
                    {"type": entry.get("level", "info"),
                     "text": f"🎛 AUDIO — {entry.get('message', '')}",
                     "timestamp": entry.get("timestamp", "")}
                )

            _adj_reply = final.get("reply") or "Something went wrong."
            _reply_slot.markdown(_adj_reply)
            st.session_state["chat_msgs"].append(
                {"role": "assistant", "content": _adj_reply}
            )

        else:
            from atdj.rag.query import answer_question
            _reply_slot.markdown("_Searching tango knowledge..._")
            try:
                response = answer_question(msg_text.strip())
                reply = response if isinstance(response, str) else str(response)
            except Exception as e:
                reply = f"(Agent error: {e})"
            _reply_slot.markdown(reply)
            st.session_state["chat_msgs"].append({"role": "assistant", "content": reply})

        st.rerun()

# ── Center column: Music ─────────────────────────────────────────────────────

def _section_music():
    # Compact icon buttons in playlist rows
    st.markdown(
        """<style>
        /* ── Minimize top padding to keep content high ── */
        .stApp [data-testid="stAppViewBlockContainer"] {
            padding-top: 0.25rem !important;
        }
        /* ── Playlist compact icon buttons (default) ── */
        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] button[kind="secondary"] {
            height: 26px !important; min-height: 26px !important; max-height: 26px !important;
            padding: 0 4px !important; font-size: 12px !important;
            line-height: 1 !important; min-width: 0 !important;
            border-radius: 4px !important;
        }
        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] button[kind="secondary"] > div {
            padding: 0 !important;
        }
        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] button[kind="secondary"] p {
            margin: 0 !important; font-size: 12px !important;
        }
        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] {
            margin-top: 2px !important; margin-bottom: 0 !important;
        }
        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] ~ div,
        div[data-testid="stVerticalBlock"] [data-testid="element-container"] {
            margin-top: 0 !important; margin-bottom: 0 !important;
            padding-top: 0 !important; padding-bottom: 0 !important;
        }
        /* ── Tight gap only inside scroll/height containers ── */
        [data-testid="stLayoutWrapper"] [data-testid="stHorizontalBlock"] {
            gap: 2px !important;
            margin-top: 0 !important; margin-bottom: 0 !important;
            padding-top: 0 !important; padding-bottom: 0 !important;
            flex-wrap: nowrap !important;
        }
        /* ── Playlist rows (4-col): fixed button columns, flexible info band ── */
        [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(4))
            > [data-testid="stColumn"]:nth-child(n+2) {
            flex: 0 0 32px !important;
            max-width: 36px !important;
        }
        [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(4))
            > [data-testid="stColumn"]:first-child {
            flex: 1 1 0 !important;
            min-width: 0 !important;
            overflow: hidden !important;
        }
        /* ── Playlist/scroll secondary buttons: 28px to match song row height ── */
        [data-testid="stLayoutWrapper"] [data-testid="stHorizontalBlock"]
            [data-testid="stButton"] button[kind="secondary"] {
            height: 28px !important; min-height: 28px !important; max-height: 28px !important;
        }
        /* ── Remove gap above buttons inside scroll containers ── */
        [data-testid="stLayoutWrapper"] [data-testid="stHorizontalBlock"]
            div[data-testid="stButton"] {
            margin-top: 0 !important; margin-bottom: 0 !important;
        }
        [data-testid="stLayoutWrapper"] [data-testid="stVerticalBlock"]
            > [data-testid="stElementContainer"] {
            padding-top: 0 !important; padding-bottom: 0 !important;
            margin-top: 0 !important; margin-bottom: 2px !important;
        }
        /* ── Toggle label: no-wrap ── */
        [data-testid="stToggle"] label span { white-space: nowrap !important; font-size: 12px !important; }
        /* ── Playlist/scroll buttons: stLayoutWrapper ancestor overrides to 28px ── */
        [data-testid="stLayoutWrapper"] [data-testid="stHorizontalBlock"]
            [data-testid="stHorizontalBlock"] button[kind="secondary"] {
            height: 28px !important; min-height: 28px !important; max-height: 28px !important;
            padding: 0 4px !important; font-size: 12px !important; line-height: 1 !important;
        }
        /* ── Toggle: blue when checked (sibling + :has fallback) ── */
        [data-testid="stToggle"] input[type="checkbox"]:checked ~ div,
        [data-testid="stToggle"] input[type="checkbox"]:checked + div {
            background-color: #1A5294 !important;
        }
        [data-testid="stToggle"] label:has(input:checked) > div {
            background-color: #1A5294 !important;
        }
        /* ── Column min-widths only (ratio set by Python [3,5]) ── */
        [data-testid="stMain"] > [data-testid="stVerticalBlock"]
            > [data-testid="stHorizontalBlock"]
            > [data-testid="stColumn"]:first-child {
            min-width: 260px !important;
        }
        [data-testid="stMain"] > [data-testid="stVerticalBlock"]
            > [data-testid="stHorizontalBlock"]
            > [data-testid="stColumn"]:last-child {
            min-width: 280px !important;
        }
        /* ── Session scroll buttons ── */
        section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]
            [data-testid="stVerticalBlock"] div[data-testid="stButton"] button {
            height: 26px !important;
            min-height: 26px !important;
            max-height: 26px !important;
        }
        /* ── Agent chat column: left padding for visual separation ── */
        [data-testid="stElementContainer"]:has(#agent-col-marker) { display: none !important; }
        [data-testid="stColumn"]:has(#agent-col-marker) > [data-testid="stVerticalBlock"] {
            padding-left: 24px !important;
        }
        /* ── Column gap between main content sections ── */
        [data-testid="stMain"] > [data-testid="stVerticalBlock"]
            > [data-testid="stHorizontalBlock"] {
            column-gap: 24px !important;
            gap: 24px !important;
        }
        [data-testid="stColumn"] > [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {
            column-gap: 24px !important;
            gap: 24px !important;
        }
        /* ── Agent chat messages: compact padding ── */
        [data-testid="stColumn"]:has(#agent-col-marker) [data-testid="stChatMessage"] {
            padding: 4px 8px !important;
            gap: 6px !important;
        }
        [data-testid="stColumn"]:has(#agent-col-marker) [data-testid="stChatMessage"] [data-testid="stVerticalBlock"] {
            gap: 0px !important;
        }
        /* ── Chat input card: consistent 10px padding and gap ── */
        [data-testid="stLayoutWrapper"]:has(#chat-input-card) > [data-testid="stVerticalBlock"] {
            padding-top: 10px !important;
            padding-bottom: 10px !important;
            gap: 10px !important;
        }
        [data-testid="stElementContainer"]:has(#chat-input-card) { display: none !important; }
        /* ── Agent chat: disable textarea resize handle ── */
        [data-testid="stColumn"]:has(#agent-col-marker) textarea {
            resize: none !important;
        }
        /* Hide Streamlit's "Press Ctrl+Enter to apply" hint — chat send is via the ➤ button */
        [data-testid="stColumn"]:has(#agent-col-marker) [data-testid="InputInstructions"] {
            display: none !important;
        }
        /* ── Hide send button marker ── */
        [data-testid="stElementContainer"]:has(#send-btn-marker) { display: none !important; }
        /* ── Playlist scroll container: mark via hidden element ── */
        [data-testid="stElementContainer"]:has(#playlist-marker) { display: none !important; }
        /* ── Search result ＋ button: compact like playlist buttons ── */
        [data-testid="stColumn"]:has(#agent-col-marker) [data-testid="stLayoutWrapper"]
            [data-testid="stButton"] button {
            height: 28px !important; min-height: 28px !important; max-height: 28px !important;
            padding: 0 4px !important; font-size: 12px !important;
            line-height: 1 !important;
        }
        /* ── Agent chat send button: override compact rule, match selectbox 40px ── */
        [data-testid="stColumn"]:has(#agent-col-marker) > [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"]:has(#chat-input-card)
            > [data-testid="stVerticalBlock"]
            [data-testid="stButton"]
            button[data-testid="stBaseButton-secondary"] {
            height: 40px !important;
            min-height: 40px !important;
            max-height: 40px !important;
            font-size: 14px !important;
            padding: 0 8px !important;
        }
        /* ── Agent col: flex layout so search container fills remaining space ── */
        [data-testid="stColumn"]:has(#agent-col-marker) > [data-testid="stVerticalBlock"] {
            display: flex !important;
            flex-direction: column !important;
        }
        [data-testid="stColumn"]:has(#agent-col-marker) > [data-testid="stVerticalBlock"]
            > [data-testid="stElementContainer"]:last-of-type + [data-testid="stLayoutWrapper"],
        [data-testid="stColumn"]:has(#agent-col-marker) > [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"]:last-of-type {
            flex-grow: 1 !important;
            height: auto !important;
            min-height: 150px !important;
        }
        /* ── Hide np-row-marker ── */
        [data-testid="stElementContainer"]:has(#np-row-marker) { display: none !important; }
        /* ── Card/ctrl row: pack controls tightly to reduce vertical gap ── */
        [data-testid="stColumn"] [data-testid="stHorizontalBlock"]:has(#np-row-marker)
            > [data-testid="stColumn"]:last-child [data-testid="stElementContainer"] {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
        }
        [data-testid="stColumn"] [data-testid="stHorizontalBlock"]:has(#np-row-marker)
            > [data-testid="stColumn"]:last-child [data-testid="stVerticalBlock"] {
            gap: 2px !important;
        }
        /* ── Chat container: height set in Python st.container(height=380) ── */
        /* ── Search result rows: fixed 32px button column ── */
        [data-testid="stColumn"]:has(#agent-col-marker)
            [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(2):last-child)
            > [data-testid="stColumn"]:last-child {
            flex: 0 0 32px !important;
            max-width: 36px !important;
        }
        [data-testid="stColumn"]:has(#agent-col-marker)
            [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(2):last-child)
            > [data-testid="stColumn"]:first-child {
            flex: 1 1 0 !important;
            min-width: 0 !important;
            overflow: hidden !important;
        }
        /* ── Force bold to 700 (Streamlit defaults to 600) ── */
        [data-testid="stMain"] [data-testid="stMarkdownContainer"] strong {
            font-weight: 700 !important;
        }
        /* ── Hide markers ── */
        [data-testid="stElementContainer"]:has(#energy-arc-marker) { display: none !important; }
        [data-testid="stElementContainer"]:has(#main-col-marker) { display: none !important; }
        /* ── Collapse hr separators: tight above, normal gap below for title ── */
        [data-testid="stColumn"]:has(#main-col-marker) [data-testid="stElementContainer"]:has(hr) {
            margin-top: -14px !important;
            margin-bottom: 0px !important;
        }
        /* ── Energy Arc section: compact internal gap (scoped to exclude playlist) ── */
        [data-testid="stLayoutWrapper"]:has(#energy-arc-marker):not(:has(#playlist-marker)) > [data-testid="stVerticalBlock"] {
            gap: 12px !important;
        }
        /* ── Playlist scroll container: small gap between rows ── */
        [data-testid="stLayoutWrapper"]:has(#playlist-marker):not(:has(#energy-arc-marker)) > [data-testid="stVerticalBlock"] {
            gap: 4px !important;
        }
        /* ── Playlist rows: min-height + clip so inner divs don't bleed into next row ── */
        [data-testid="stLayoutWrapper"]:has(#playlist-marker):not(:has(#energy-arc-marker))
            > [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"] {
            min-height: 34px !important;
            overflow: hidden !important;
        }
        /* ── Playlist rows: stretch columns so border-left bands fill full height ── */
        [data-testid="stLayoutWrapper"]:has(#playlist-marker):not(:has(#energy-arc-marker))
            [data-testid="stHorizontalBlock"] {
            align-items: stretch !important;
        }
        [data-testid="stLayoutWrapper"]:has(#playlist-marker):not(:has(#energy-arc-marker))
            [data-testid="stColumn"] {
            overflow: visible !important;
        }
        /* ── Hide ctrl-col-marker ── */
        [data-testid="stElementContainer"]:has(#ctrl-col-marker) { display: none !important; }
        /* ── Playback ctrl column: unbold all labels ── */
        [data-testid="stColumn"]:has(#ctrl-col-marker) [data-testid="stWidgetLabel"] p {
            font-size: 13px !important;
            font-weight: 400 !important;
            color: #31333F !important;
        }
        /* ── Playback controls: center-align buttons with transition bar ── */
        [data-testid="stColumn"]:has(> [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(#ctrl-col-marker)) [data-testid="stHorizontalBlock"] {
            align-items: center !important;
        }
        [data-testid="stColumn"]:has(#ctrl-col-marker) [data-testid="stBaseButton-secondary"] {
            margin-top: 0 !important;
        }
        [data-testid="stColumn"]:has(#ctrl-col-marker) [data-testid="stElementContainer"]:has([data-testid="stBaseButton-secondary"]) [data-testid="stWidgetLabel"] {
            display: none !important;
        }
        /* ── Compact number inputs so added spacing doesn't grow total height ── */
        [data-testid="stColumn"]:has(#ctrl-col-marker) [data-testid="stNumberInput"] input {
            height: 34px !important;
            min-height: 34px !important;
            padding: 4px 10px !important;
        }
        /* ── Number input: fill container background to remove white-line gaps ── */
        [data-testid="stColumn"]:has(#ctrl-col-marker) [data-testid="stNumberInputContainer"] {
            background: rgb(240, 240, 240) !important;
        }
        /* ── Remove default vertical gap inside ctrl column so spacers control spacing ── */
        [data-testid="stColumn"]:has(#ctrl-col-marker) > [data-testid="stVerticalBlock"] {
            gap: 0.25rem !important;
        }
        /* ── Main column: consistent section spacing (must come after ctrl-col rule) ── */
        [data-testid="stColumn"]:has(#main-col-marker) > [data-testid="stVerticalBlock"] {
            gap: 16px !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )
    main_col, agent_col = st.columns([4, 5])

    pq = _get_pq()

    with main_col:
        st.markdown('<div id="main-col-marker"></div>', unsafe_allow_html=True)
        # ── Row 1: NOW PLAYING card (left) | player + controls (right) ──
        _lbl("Now Playing")
        np_item = pq.current_track()
        pos = pq.current_index + 1
        total = len(pq.items)
        card_col, ctrl_col = st.columns([2, 3], vertical_alignment="top")

        with card_col:
            st.markdown('<div id="np-row-marker"></div>', unsafe_allow_html=True)
            if np_item and np_item.get("type") == "song":
                np_style = np_item.get("style", "TANGO").upper()
                np_clr = STYLE_COLORS.get(np_style, "#888")
                np_year = np_item.get("year", 0)
                np_decade = f'{(np_year // 10) * 10}s' if np_year else ""
                np_singer_html = (
                    f'<p style="color:#666;font-size:12px;margin:0 0 3px">{np_item["singer"]}</p>'
                    if np_item.get("singer") else ""
                )
                np_year_html = (
                    f'<p style="color:#999;font-size:12px;margin:0">{np_decade} · {np_year}</p>'
                    if np_year else '<p style="color:#999;font-size:12px;margin:0">Unknown year</p>'
                )
                st.markdown(
                    f'<div style="position:relative;background:#FFF;border:1px solid #EBEBEB;'
                    f'border-left:3px solid {np_clr};border-radius:8px;padding:6px 14px;'
                    f'margin:0;min-height:140px">'
                    f'<span style="position:absolute;top:8px;right:12px;font-size:10px;font-weight:700;color:#AAA">'
                    f'{pos}/{total}</span>'
                    f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
                    f'{_badge(np_style, np_clr+"22", np_clr)}'
                    f'{_source_badge(np_item.get("source", "agent"))}</div>'
                    f'<p style="font-size:18px;font-weight:700;margin:0 0 6px">{np_item.get("title", "")}</p>'
                    f'<p style="color:#333;font-size:12px;font-weight:700;margin:0 0 3px">{np_item.get("orchestra", "")}</p>'
                    f'{np_singer_html}'
                    f'{np_year_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            elif np_item and np_item.get("type") == "cortina":
                cort_len = st.session_state.get("cortina_len", 30)
                c_m, c_s = divmod(cort_len, 60)
                cort_dur = f"{c_m}:{c_s:02d}"
                cortina_badge = _badge("CORTINA", "#E0E0E0", "#777777")
                st.markdown(
                    f'<div style="position:relative;background:#FFF;border:1px solid #EBEBEB;'
                    f'border-left:3px solid #BBB;border-radius:8px;padding:6px 14px;'
                    f'margin:0;min-height:140px">'
                    f'<span style="position:absolute;top:8px;right:12px;font-size:10px;font-weight:700;color:#AAA">'
                    f'{pos}/{total}</span>'
                    f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
                    f'{cortina_badge}'
                    f'{_source_badge(np_item.get("source", "agent"))}</div>'
                    f'<p style="font-size:18px;font-weight:700;margin:0 0 6px">{np_item.get("title", "")}</p>'
                    f'<p style="color:#999;font-size:12px;margin:0">Plays for {cort_dur}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="background:#F9F9F9;border:1px dashed #DEDEDE;'
                    'border-radius:8px;padding:16px 14px;min-height:140px;'
                    'display:flex;flex-direction:column;justify-content:center;'
                    'align-items:center;text-align:center">'
                    '<p style="font-size:13px;color:#AAAAAA;margin:0 0 4px">No track playing</p>'
                    '<p style="font-size:12px;color:#BBBBBB;margin:0">Plan a session to get started</p>'
                    '</div>',
                    unsafe_allow_html=True,
                )

        with ctrl_col:
            st.markdown('<div id="ctrl-col-marker"></div>', unsafe_allow_html=True)
            if np_item:
                file_path = pq.resolve_file_path(np_item)
                gap_sec = st.session_state.get("song_gap", 10)
                cortina_sec = st.session_state.get("cortina_len", 30)
                is_cortina = np_item.get("type") == "cortina"
                max_dur = cortina_sec if is_cortina else None
                effective_gap = 0 if is_cortina else gap_sec
                if file_path:
                    # 2026-05-01 (Test 7.9): autoplay only after the user has
                    # explicitly initiated playback (clicked a ▶ jump button or
                    # ⏭/⏮). Until then the iframe renders with controls but no
                    # autoplay, so a fresh PLAN doesn't blast music.
                    _autoplay_ok = bool(st.session_state.get("playback_initiated", False))
                    render_audio_player(
                        file_path, gap_seconds=effective_gap,
                        max_duration=max_dur, fade_in_seconds=2.0,
                        autoplay=_autoplay_ok,
                    )
                else:
                    _autoskip_html = f"""
                    <span style="display:none">skip:{pq.current_index}</span>
                    <style>* {{ margin:0; padding:0; box-sizing:border-box; }}
                    #msg {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                      background:#FFF8E1;border:1px solid #FFE082;border-radius:8px;
                      padding:10px 14px;font-size:12px;color:#8D6E00; }}</style>
                    <div id="msg">Audio file not found — auto-skipping…</div>
                    <script>
                    const gapMs = {int(effective_gap * 1000)};
                    const myNonce = Math.random().toString(36);
                    window.parent.__atdjAutoSkipNonce = myNonce;
                    if (window.parent.__atdjAutoSkipTimer) window.parent.clearTimeout(window.parent.__atdjAutoSkipTimer);
                    function clickSkip() {{
                        if (window.parent.__atdjAutoSkipNonce !== myNonce) return;
                        const btns = window.parent.document.querySelectorAll('button');
                        for (const btn of btns) {{
                            if (btn.innerText.includes('\\u23ed')) {{ btn.click(); break; }}
                        }}
                    }}
                    if (gapMs > 0) {{
                        window.parent.__atdjGapSignal = {{duration: gapMs, id: myNonce}};
                        window.parent.__atdjAutoSkipTimer = window.parent.setTimeout(clickSkip, gapMs);
                    }} else {{
                        window.parent.__atdjAutoSkipTimer = window.parent.setTimeout(clickSkip, 500);
                    }}
                    </script>
                    """
                    st_components.html(_autoskip_html, height=40)

                st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
                btn1, btn2, gap_bar_col = st.columns([1, 1, 6], vertical_alignment="center")
                with btn1:
                    if st.button("⏮", use_container_width=True, help="Previous track", key="pb_prev"):
                        pq.previous_track()
                        _save_pq(pq)
                        st.session_state["playback_initiated"] = True
                        st.rerun()
                with btn2:
                    if st.button("⏭", use_container_width=True, help="Skip to next", key="pb_skip"):
                        pq.next_track()
                        _save_pq(pq)
                        st.session_state["playback_initiated"] = True
                        st.rerun()
                with gap_bar_col:
                    _gap_bar_html = f"""
                    <span style="display:none">track:{pq.current_index}</span>
                    <style>
                      * {{ margin:0; padding:0; box-sizing:border-box; }}
                      html, body {{ height:100%; }}
                      body {{ display:flex; align-items:center; }}
                      #gap-wrap {{ width:100%; display:flex; align-items:center;
                        border-left:1px solid #E0E0E0; padding-left:12px; gap:10px; }}
                      #gap-label {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                        font-size:13px; font-weight:400; color:#31333F;
                        white-space:nowrap; flex-shrink:0; }}
                      #gap-track {{ flex:1; height:4px; background:#E5E5E5; border-radius:2px; overflow:hidden; }}
                      #gap-fill {{ height:100%; width:0%; background:#1A5294; border-radius:2px; transition:none; }}
                    </style>
                    <div id="gap-wrap">
                      <div id="gap-label">Transition</div>
                      <div id="gap-track"><div id="gap-fill"></div></div>
                    </div>
                    <script>
                    let __lastSigId = null;
                    setInterval(() => {{
                        const sig = window.parent.__atdjGapSignal;
                        if (sig && sig.id && sig.id !== __lastSigId) {{
                            __lastSigId = sig.id;
                            const fill = document.getElementById('gap-fill');
                            fill.style.transition = 'none';
                            fill.style.width = '0%';
                            requestAnimationFrame(() => {{
                                requestAnimationFrame(() => {{
                                    fill.style.transition = 'width ' + sig.duration + 'ms linear';
                                    fill.style.width = '100%';
                                }});
                            }});
                        }}
                    }}, 100);
                    </script>
                    """
                    st_components.html(_gap_bar_html, height=28)
                st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
                # 2026-05-01: wrapped in a fragment so slider changes don't trigger
                # a full page rerun (which would re-render the audio iframe and
                # interrupt the currently-playing song). The new value still flows
                # into session_state immediately; render_audio_player picks it up
                # on the next track auto-advance. Also unified the slider/toggle
                # log entries to the "change" kind so they share the grey colour
                # with the other user actions (move/remove/clear/add).
                # 2026-05-01: in-fragment changes don't repaint the Session Log
                # panel (it lives outside this fragment). To still give the user
                # immediate confirmation, each change also fires st.toast — toasts
                # render globally and appear right after the fragment rerun. The
                # Session Log entry is still recorded via _log() and shows on the
                # next full rerun.
                def _on_gap_change():
                    v = st.session_state.get("song_gap")
                    _log(f'Transition gap set to {v}s (applies to next track).', "change")
                    st.toast(f'Transition gap set to {v}s — applies to next track', icon='👤')

                def _on_cortina_change():
                    v = st.session_state.get("cortina_len")
                    _log(f'Cortina length set to {v}s (applies to next cortina).', "change")
                    st.toast(f'Cortina length set to {v}s — applies to next cortina', icon='👤')

                @st.fragment
                def _audio_settings_fragment():
                    gap_c, cort_c = st.columns(2)
                    with gap_c:
                        st.number_input(
                            "Transition (s)", min_value=0, max_value=60, value=10, key="song_gap",
                            label_visibility="visible",
                            on_change=_on_gap_change,
                        )
                    with cort_c:
                        st.number_input(
                            "Cortina (s)", min_value=5, max_value=120, value=30, key="cortina_len",
                            label_visibility="visible",
                            on_change=_on_cortina_change,
                        )
                    # 2026-05-01: write the live slider values to the top window
                    # so the audio iframe's currentGapMs() / currentMaxDur()
                    # readers see the latest value at advance / timeupdate time.
                    # Without this, the audio iframe (which is NOT re-rendered
                    # by fragment-scoped reruns) would keep using its baked
                    # initial values forever. The varying timestamp comment
                    # forces components.html to re-render the iframe instead of
                    # caching the previous identical-content one.
                    import time as _time_mod
                    _gap_ms = int(st.session_state.get("song_gap", 10)) * 1000
                    _cor_s  = int(st.session_state.get("cortina_len", 30))
                    _stamp = int(_time_mod.time() * 1000)
                    st_components.html(
                        f"""<!-- atdj-slider-write {_stamp} -->
                        <script>
                          try {{ window.top.__atdjGapMs = {_gap_ms}; }} catch (e) {{}}
                          try {{ window.top.__atdjCortinaSec = {_cor_s}; }} catch (e) {{}}
                          try {{ window.parent.__atdjGapMs = {_gap_ms}; }} catch (e) {{}}
                          try {{ window.parent.__atdjCortinaSec = {_cor_s}; }} catch (e) {{}}
                        </script>""",
                        height=1,
                    )

                _audio_settings_fragment()

        # ── Row 2: ENERGY ARC (full width of main_col) ──
        _hr()
        with st.container():
            st.markdown('<div id="energy-arc-marker"></div>', unsafe_allow_html=True)
            _lbl("Energy Arc")
            _render_energy_chart(pq.items, pq.current_index)

        # ── Row 3: FULL PLAYLIST ──
        _hr()
        title_col, clear_col = st.columns([8, 1], vertical_alignment="center")
        with title_col:
            _lbl("Full Playlist")
        with clear_col:
            if pq.items and st.button("Clear", key="pl_clear_all", help="Clear all tracks", use_container_width=True):
                _log(f'Cleared playlist ({len(pq.items)} tracks).', "change")
                pq.clear()
                _save_pq(pq)
                # 2026-05-01 (Test 7.9): clearing is the "explicit stop" — reset
                # the autoplay-armed flag so the next plan won't blast music until
                # the user manually clicks ▶ again.
                st.session_state["playback_initiated"] = False
                st.rerun()
        playlist = pq.items
        cortina_len = st.session_state.get("cortina_len", 30)

        with st.container(height=782):
            st.markdown('<div id="playlist-marker"></div>', unsafe_allow_html=True)
            for i, item in enumerate(playlist):
                # ── Cortina row ──
                if item["type"] == "cortina":
                    b_src_c = _source_icon(item.get("source", "agent"))
                    b_cort  = _badge_sm("C", "#EEEEEE", "#888888")
                    sc_c, cb0, cb1, cb2, cb3 = st.columns([19, 1, 1, 1, 1])
                    c_mins, c_secs = divmod(cortina_len, 60)
                    c_dur_str = f"{c_mins}:{c_secs:02d}"
                    with sc_c:
                        st.markdown(
                            f'<div style="padding:5px 8px;border-left:2px solid #BBBBBB;'
                            f'background:#F2F2F2;margin-bottom:0;display:flex;'
                            f'align-items:center;gap:5px;overflow:hidden;white-space:nowrap">'
                            f'{b_cort}{b_src_c}'
                            f'<span style="font-size:12px;font-weight:700;color:#555;'
                            f'flex-shrink:0">{item["title"]}</span>'
                            f'<span style="font-size:12px;color:#999;"> · {c_dur_str}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with cb0:
                        if i != pq.current_index:
                            if st.button("▶", key=f"pl_play_{i}", help="Jump to this cortina", use_container_width=True):
                                pq.jump_to(i)
                                _save_pq(pq)
                                # 2026-05-01: no log entry — pure navigation, not a state change worth recording.
                                # 2026-05-01 (Test 7.9): user explicitly initiated playback → enable autoplay.
                                st.session_state["playback_initiated"] = True
                                st.rerun()
                    with cb1:
                        if i > 0:
                            if st.button("↑", key=f"pl_up_{i}", help="Move up", use_container_width=True):
                                pq.move_up(i)
                                _save_pq(pq)
                                _log(f'Moved "{item["title"]}" up in playlist.', "change")
                                st.rerun()
                    with cb2:
                        if i < len(playlist) - 1:
                            if st.button("↓", key=f"pl_dn_{i}", help="Move down", use_container_width=True):
                                pq.move_down(i)
                                _save_pq(pq)
                                _log(f'Moved "{item["title"]}" down in playlist.', "change")
                                st.rerun()
                    with cb3:
                        if st.button("x", key=f"pl_rm_{i}", help="Remove", use_container_width=True):
                            _log(f'Removed "{item["title"]}" from playlist.', "change")
                            pq.remove(i)
                            _save_pq(pq)
                            st.rerun()
                    continue

                # ── Song row ──
                clr        = STYLE_COLORS.get(item["style"].upper(), "#888")
                decade     = f'{(item["year"] // 10) * 10}s' if item.get("year") else ""
                singer_txt = f' · {item["singer"]}' if item.get("singer") else ""
                dur_txt    = f' · {item["duration"]}' if item.get("duration") else ""
                meta       = f'<strong>{item["orchestra"]}</strong>{singer_txt} · {decade}{dur_txt}'
                abbrev     = STYLE_ABBREV.get(item["style"].upper(), item["style"][0])
                b_style    = _badge_sm(abbrev, clr + "22", clr)
                b_src      = _source_icon(item.get("source", "agent"))

                is_current = (i == pq.current_index)
                if is_current:
                    sc, _b0, _b1, _b2, _b3 = st.columns([19, 1, 1, 1, 1])
                    with sc:
                        st.markdown(
                            f'<div style="padding:5px 8px;border-left:3px solid {clr};'
                            f'background:{clr}22;margin-bottom:0;display:flex;align-items:center;'
                            f'gap:5px;overflow:hidden;white-space:nowrap">'
                            f'<span style="font-size:12px;color:{clr};flex-shrink:0">▶</span>'
                            f'{b_style}{b_src}'
                            f'<span style="font-size:12px;font-weight:700;color:#1A1A1A;'
                            f'flex-shrink:0">{item["title"]}</span>'
                            f'<span style="font-size:12px;color:#555;overflow:hidden;'
                            f'text-overflow:ellipsis"> · {meta}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    prev_s = next((j for j in range(i - 1, -1, -1) if playlist[j]["type"] != "cortina"), -1)
                    next_s = next((j for j in range(i + 1, len(playlist)) if playlist[j]["type"] != "cortina"), -1)
                    sc, b0, b1, b2, b3 = st.columns([19, 1, 1, 1, 1])
                    with sc:
                        st.markdown(
                            f'<div style="padding:5px 8px;border-left:2px solid {clr}88;'
                            f'background:{clr}11;margin-bottom:0;display:flex;'
                            f'align-items:center;gap:5px;overflow:hidden;white-space:nowrap">'
                            f'{b_style}{b_src}'
                            f'<span style="font-size:12px;font-weight:700;color:#333;'
                            f'flex-shrink:0">{item["title"]}</span>'
                            f'<span style="font-size:12px;color:#777;overflow:hidden;'
                            f'text-overflow:ellipsis"> · {meta}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with b0:
                        if st.button("▶", key=f"pl_play_{i}", help="Jump to this track", use_container_width=True):
                            pq.jump_to(i)
                            _save_pq(pq)
                            # 2026-05-01: no log entry — pure navigation, not a state change worth recording.
                            # 2026-05-01 (Test 7.9): user explicitly initiated playback → enable autoplay.
                            st.session_state["playback_initiated"] = True
                            st.rerun()
                    with b1:
                        if prev_s >= 0 and prev_s != pq.current_index:
                            if st.button("↑", key=f"pl_up_{i}", help="Move up", use_container_width=True):
                                pq.move_up(i)
                                _save_pq(pq)
                                _log(f'Moved "{item["title"]}" up in playlist.', "change")
                                st.rerun()
                    with b2:
                        if next_s >= 0:
                            if st.button("↓", key=f"pl_dn_{i}", help="Move down", use_container_width=True):
                                pq.move_down(i)
                                _save_pq(pq)
                                _log(f'Moved "{item["title"]}" down in playlist.', "change")
                                st.rerun()
                    with b3:
                        if st.button("x", key=f"pl_rm_{i}", help="Remove", use_container_width=True):
                            _log(f'Removed "{item["title"]}" from playlist.', "change")
                            pq.remove(i)
                            _save_pq(pq)
                            st.rerun()


    # ── Agent Chat (full height, right column) ────────────────────────────────
    with agent_col:
        _section_chat()
        st.markdown(
            '<hr style="margin:2px 0 2px;border:none;border-top:1px solid #EEEEEE">',
            unsafe_allow_html=True,
        )
        _lbl("Session Log")
        # Hoist any new activity_log entries (from Tina's LangGraph nodes) into the
        # agent_notifications list that this panel renders. Dedup on identical entries.
        # 2026-05-01: filter to summary=True; raw [node_name] prefixes replaced
        # with 📋 PLAN category prefix.
        if "activity_log" in st.session_state:
            for entry in st.session_state["activity_log"]:
                if not entry.get("summary"):
                    continue
                notification = {
                    "type": entry.get("level", "info"),
                    "text": f"📋 PLAN — {entry.get('message', '')}",
                    "timestamp": entry.get("timestamp", ""),
                }
                if notification not in st.session_state["agent_notifications"]:
                    st.session_state["agent_notifications"].append(notification)
        notif_colors = {
            "info":    ("#E8F4FD", "#1A6FAD"),  # blue — agent informational entries
            "change":  ("#F0F2F5", "#5A6C7E"),  # grey — user actions (was amber, conflicted with warning)
            "warning": ("#FEF9E7", "#B7770D"),  # amber — reserved for failures / non-fatal problems
            "error":   ("#FDE8E8", "#C44040"),  # red — exceptions
        }
        with st.container(height=150):
            for n in reversed(st.session_state["agent_notifications"]):
                bg, clr = notif_colors.get(n["type"], ("#F7F7F7", "#555"))
                ts = n.get("timestamp", "")
                # Tina's _log emits ISO datetime; the manual _log helper emits HH:MM:SS.
                # Normalize to HH:MM:SS for the panel.
                if ts and "T" in ts:
                    ts = ts.split("T", 1)[1][:8]
                ts_html = f'<span style="color:#999;font-size:10px;margin-right:6px">{ts}</span>' if ts else ''
                st.markdown(
                    f'<div style="background:{bg};border-left:3px solid {clr};'
                    f'border-radius:0 4px 4px 0;padding:5px 10px;margin-bottom:4px;font-size:12px;color:#333">'
                    f'{ts_html}{n["text"]}</div>',
                    unsafe_allow_html=True,
                )

        # ── Search Music ─────────────────────────────────────────────────────
        st.markdown(
            '<hr style="margin:2px 0 2px;border:none;border-top:1px solid #EEEEEE">',
            unsafe_allow_html=True,
        )
        _lbl("Search Music")
        pq = _get_pq()
        query = st.text_input(
            "Search", placeholder="Title, artist, style…",
            label_visibility="collapsed", key="music_search",
        )
        with st.container(height=280):
            if query.strip():
                df = _load_catalog()
                mask = (
                    df["title"].str.contains(query, case=False, na=False) |
                    df["orchestra"].str.contains(query, case=False, na=False) |
                    df["style"].str.contains(query, case=False, na=False) |
                    df["singer"].astype(str).str.contains(query, case=False, na=False)
                )
                results = df[mask].head(6)
                # Also search cortinas (filename match against the CORTINAS_DIR folder).
                # Cortinas have no orchestra/singer/year/energy in metadata — just the filename.
                cortinas_path = _Path(CORTINAS_DIR)
                cortina_matches = []
                if cortinas_path.exists():
                    q_lower = query.lower()
                    for f in sorted(list(cortinas_path.glob("*.mp3")) + list(cortinas_path.glob("*.wav"))):
                        if q_lower in f.stem.lower() or q_lower in "cortina":
                            cortina_matches.append(f)
                            if len(cortina_matches) >= 6:
                                break

                if results.empty and not cortina_matches:
                    st.caption("No results found.")
                else:
                    next_tid = max((p.get("tanda_id", 0) for p in pq.items if p["type"] == "song"), default=0) + 1
                    for _, row in results.iterrows():
                        rclr = STYLE_COLORS.get(row["style"].upper(), "#888")
                        res_col, add_col = st.columns([7, 1])
                        with res_col:
                            singer_part = f' · {row["singer"]}' if str(row.get("singer", "")) not in ("", "nan") else ""
                            st.markdown(
                                f'<div style="padding:3px 0;font-size:12px;'
                                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                                f'<span style="display:inline-block;width:7px;height:7px;background:{rclr};'
                                f'border-radius:50%;margin-right:5px;vertical-align:middle"></span>'
                                f'<strong>{row["title"]}</strong>'
                                f'<span style="color:#777"> · {row["orchestra"]}{singer_part} · {int(row["year"]) if pd.notna(row.get("year")) else ""}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        with add_col:
                            if st.button("＋", key=f"srch_add_{row['title']}", use_container_width=True,
                                         help="Add to end of playlist"):
                                entry = {
                                    "type": "song", "title": row["title"],
                                    "style": row["style"].upper(), "orchestra": row["orchestra"],
                                    "singer": str(row.get("singer", "")) if str(row.get("singer", "")) != "nan" else "",
                                    "year": int(row["year"]) if pd.notna(row.get("year")) else 0,
                                    "energy": float(row["energy"]) if pd.notna(row.get("energy")) else None,
                                    "source": "user", "tanda_id": next_tid,
                                }
                                pq.items.append(entry)
                                _save_pq(pq)
                                _log(f'Added "{row["title"]}" to playlist end.', "change")
                                st.toast(f'"{row["title"]}" added to playlist.', icon="👤")
                                st.rerun()

                    # Cortina results — filename-based, "C" badge, no orchestra/singer/year metadata.
                    for cf in cortina_matches:
                        c_title = cf.stem
                        res_col, add_col = st.columns([7, 1])
                        with res_col:
                            st.markdown(
                                f'<div style="padding:3px 0;font-size:12px;'
                                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                                f'<span style="display:inline-block;width:14px;height:14px;background:#EEEEEE;'
                                f'color:#888;border-radius:3px;font-size:9px;font-weight:700;text-align:center;'
                                f'line-height:14px;margin-right:5px;vertical-align:middle">C</span>'
                                f'<strong>{c_title}</strong>'
                                f'<span style="color:#999"> · cortina</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        with add_col:
                            if st.button("＋", key=f"srch_add_cor_{c_title}", use_container_width=True,
                                         help="Add cortina to end of playlist"):
                                entry = {
                                    "type": "cortina",
                                    "title": c_title,
                                    "duration": "0:20",
                                    "source": "user",
                                }
                                pq.items.append(entry)
                                _save_pq(pq)
                                _log(f'Added cortina "{c_title}" to playlist end.', "change")
                                st.toast(f'Cortina "{c_title}" added to playlist.', icon="👤")
                                st.rerun()
            else:
                st.caption("Search to find and add songs or cortinas.")

# ── Bottom: Library, Queue, Upload ──────────────────────────────────────────

def _section_library():
    st.divider()
    _tab_library()


def _tab_library():
    df = _load_catalog()

    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 3])
    with fc1:
        styles = ["All"] + sorted(df["style"].dropna().unique().tolist())
        sel_style = st.selectbox("Style", styles, key="lib_style", label_visibility="collapsed")
        st.caption("Style")
    with fc2:
        orchs = ["All"] + sorted(df["orchestra"].dropna().unique().tolist())
        sel_orch = st.selectbox("Orchestra", orchs, key="lib_orch", label_visibility="collapsed")
        st.caption("Orchestra")
    with fc3:
        decades = ["All", "1920s", "1930s", "1940s", "1950s", "1960s"]
        sel_decade = st.selectbox("Decade", decades, key="lib_decade", label_visibility="collapsed")
        st.caption("Decade")
    with fc4:
        search = st.text_input("Search", placeholder="Search title or singer…", key="lib_search", label_visibility="collapsed")
        st.caption("Search")

    filtered = df.copy()
    if sel_style != "All":
        filtered = filtered[filtered["style"].str.lower() == sel_style.lower()]
    if sel_orch != "All":
        filtered = filtered[filtered["orchestra"] == sel_orch]
    if sel_decade != "All":
        ds = int(sel_decade[:4])
        filtered = filtered[(filtered["year"] >= ds) & (filtered["year"] < ds + 10)]
    if search:
        mask = (
            filtered["title"].str.contains(search, case=False, na=False) |
            filtered["singer"].astype(str).str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    _, cnt = st.columns([9, 1])
    with cnt:
        st.caption(f"{len(filtered)} tracks")
    st.dataframe(filtered, use_container_width=True, hide_index=True, height=220)


def _tab_queue():
    st.caption("Upcoming queue — 💡 = agent planned · 👤 = hand-picked by you. Remove or reorder as needed.")
    queue = st.session_state.get("live_queue", [])

    if not queue:
        st.info("Queue is empty.")
        return

    for i, item in enumerate(queue):
        row_l, row_r = st.columns([8, 1])
        with row_l:
            if item["type"] == "cortina":
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;padding:5px 10px;'
                    f'border:1px dashed #DDD;border-radius:6px;margin-bottom:3px;background:#FAFAFA">'
                    f'<span style="font-size:10px;font-weight:700;color:#999">CORTINA</span>'
                    f'<span style="font-size:12px;color:#666;flex:1">{item["title"]}</span>'
                    f'<span style="font-size:12px;color:#AAA">{item["duration"]}</span>'
                    f'</div>', unsafe_allow_html=True)
            else:
                clr = STYLE_COLORS.get(item["style"], "#888")
                src = _source_badge(item.get("source", "agent"))
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;padding:6px 12px;'
                    f'background:#FFF;border:1px solid #EBEBEB;border-radius:8px;margin-bottom:3px">'
                    f'<span style="background:{clr}22;color:{clr};font-size:10px;font-weight:700;'
                    f'border-radius:100px;padding:2px 7px">{item["style"]}</span>'
                    f'{src}'
                    f'<span style="font-weight:600;font-size:13px;flex:1">{item["orchestra"]}</span>'
                    f'<span style="font-size:12px;color:#999">{item.get("decade","")}</span>'
                    f'</div>', unsafe_allow_html=True)
        with row_r:
            if st.button("x", key=f"rm_{i}", help="Remove from queue", use_container_width=True):
                queue.pop(i)
                st.session_state["live_queue"] = queue
                st.toast("Removed from queue.", icon="🗑")
                st.rerun()


# ── Main entry point ─────────────────────────────────────────────────────────

def show():
    import datetime as _dt
    if "agent_notifications" not in st.session_state:
        st.session_state["agent_notifications"] = []

    _sidebar()

    # Header — compact: title + today's date
    today = _dt.date.today().strftime("%Y-%m-%d")
    st.markdown(
        f'<div style="padding:4px 0 2px;display:flex;align-items:baseline;gap:12px">'
        f'<span style="font-size:18px;font-weight:700;color:#1A1A1A">DJ Console</span>'
        f'<span style="font-size:12px;color:#999">{today}</span>'
        f'</div>'
        f'<hr style="margin:4px 0 0;border:none;border-top:1px solid #EBEBEB">',
        unsafe_allow_html=True,
    )

    _section_music()
