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
from atdj.config import CATALOG_PATH
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
    "Ollama": ["llama3.2", "mistral", "phi3"],
}
KEY_LABELS = {
    "Claude": "Anthropic API Key",
    "Gemini": "Google API Key",
    "Ollama": "Ollama Host URL (optional)",
}
CHAT_STUB = "Got it — I'm still warming up. Connect me to the music pool for real responses. _(stub)_"

# ── Playback helpers ─────────────────────────────────────────────────────────
# These are new helpers specific to this UI page — no equivalent exists elsewhere.

def _get_pq() -> PlaybackQueue:
    if "pq_data" not in st.session_state:
        pq = PlaybackQueue(list(PLAYLIST_STUB))
        st.session_state["pq_data"] = pq.to_session_state()
    return PlaybackQueue.from_session_state(st.session_state["pq_data"])


def _save_pq(pq: PlaybackQueue) -> None:
    st.session_state["pq_data"] = pq.to_session_state()
    st.session_state["playlist"] = pq.items


def _log(text: str, kind: str = "info") -> None:
    """Append a timestamped entry to the session log."""
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S")
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
    """Solid line = played · Dotted line = planned · Hover = song card."""
    import altair as alt

    songs = [s for s in playlist if s["type"] == "song"]
    if not songs:
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

    # Normalize energy to [0, 1] using catalog min/max
    # NOTE: must use the RAG catalog (reduced_catalog.csv) — that's the catalog the planner
    # pulls track-level `energy` from, and `_load_catalog()` returns the playback catalog
    # with no `energy` column, which silently fell through to a wrong fallback range.
    try:
        cat = _get_rag_catalog()
        e_vals = cat["energy"].dropna().astype(float)
        e_min, e_max = float(e_vals.min()), float(e_vals.max())
    except Exception:
        e_min, e_max = 0.0, 1.0

    def _norm_energy(s: dict) -> tuple[float, bool]:
        """Return (normalised 0-1 value, has_real_energy)."""
        raw = s.get("energy")
        if raw is not None:
            try:
                v = float(raw)
                norm = (v - e_min) / (e_max - e_min) if e_max > e_min else 0.5
                return norm, True
            except (ValueError, TypeError):
                pass
        return 0.5, False   # unknown → mid-point, flagged as estimated

    # Map playlist-level current_index to song-only index
    song_indices = [i for i, s in enumerate(playlist) if s["type"] == "song"]
    playing_pos = 0
    for si, pi in enumerate(song_indices):
        if pi >= current_index:
            playing_pos = si
            break
    records = []
    for idx, s in enumerate(songs):
        decade = f"{(int(s['year']) // 10) * 10}s" if s.get("year") else "—"
        energy_val, has_energy = _norm_energy(s)
        base_rec = {
            "pos":        idx,
            "title":      s["title"],
            "orchestra":  s["orchestra"],
            "singer":     s.get("singer", "—") or "—",
            "style":      s["style"],
            "decade":     decade,
            "source":     "💡 Agent" if s.get("source") == "agent" else "👤 You",
            "energy":     energy_val,
            "has_energy": has_energy,
            "segment":    "played" if idx <= playing_pos else "planned",
        }
        records.append(base_rec)
        if idx == playing_pos:
            records.append({**base_rec, "segment": "planned"})

    df = pd.DataFrame(records)
    base = alt.Chart(df).encode(
        x=alt.X("pos:Q", axis=alt.Axis(title=None, labels=False, ticks=False, grid=False)),
        y=alt.Y("energy:Q",
                scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(title=None, format=".0%", tickCount=3,
                              gridColor="#F5F5F5", domainColor="#DDD")),
        tooltip=[
            alt.Tooltip("title:N",     title="Song"),
            alt.Tooltip("style:N",     title="Style"),
            alt.Tooltip("orchestra:N", title="Orchestra"),
            alt.Tooltip("singer:N",    title="Singer"),
            alt.Tooltip("decade:N",    title="Decade"),
            alt.Tooltip("source:N",    title="Source"),
        ],
    )
    played_line  = base.mark_line(color="#1A5294", strokeWidth=2.5).transform_filter(
        alt.datum.segment == "played"
    )
    planned_line = base.mark_line(color="#BBBBBB", strokeWidth=2,
                                  strokeDash=[5, 4]).transform_filter(
        alt.datum.segment == "planned"
    )
    # Known-energy tracks: filled circle; unknown: hollow square at 50%
    dots_known = base.mark_circle(size=55, opacity=0.9).transform_filter(
        alt.datum.has_energy == True
    ).encode(
        color=alt.condition(
            alt.datum.segment == "played",
            alt.value("#1A5294"),
            alt.value("#BBBBBB"),
        )
    )
    dots_unknown = base.mark_point(size=50, shape="square", filled=False,
                                   opacity=0.5, strokeWidth=1.5).transform_filter(
        alt.datum.has_energy == False
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
    pm = {"claude": "Claude", "gemini": "Gemini", "ollama": "Ollama"}
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
        provider_opts = list(PROVIDER_MODELS.keys()) + ["Others"]
        cur_provider  = st.session_state.get("s_provider", "Claude")
        with pv_col:
            sel_provider = st.selectbox(
                "Provider", provider_opts,
                index=provider_opts.index(cur_provider) if cur_provider in provider_opts else len(provider_opts) - 1,
                key="sb_provider", label_visibility="collapsed",
            )
        provider = sel_provider if sel_provider != "Others" else st.session_state.get("sb_provider_custom", "")
        if sel_provider == "Others":
            provider = st.text_input("Provider name", placeholder="e.g. OpenAI",
                                     key="sb_provider_custom", label_visibility="collapsed")
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
        msg_text = st.text_area(
            "Message", placeholder="Message the agent…",
            label_visibility="collapsed", key=_input_key,
            height=87,
        )
        _, send_col = st.columns([6, 1])
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
                    "session_plan": session_plan,
                    "picked_tracks": [],
                }
                final_state = graph.invoke(initial_state)

                # Hand the per-node log entries off to the Session Log panel.
                for entry in final_state.get("activity_log", []):
                    st.session_state.setdefault("activity_log", []).append(entry)

                # Original parallel selection loop kept below (commented) for reference.
                # Replaced by tanda_planner, which now calls search_catalog_rag itself
                # and writes the chosen tracks into state["picked_tracks"].
                # from atdj.rag.select_tanda import select_tanda as _select_tanda
                # from atdj.rag.prompt_to_features import build_translator, load_catalog
                # from atdj.config import RAG_CATALOG_PATH
                # df = _get_rag_catalog()
                # translator = _get_rag_translator(
                #     st.session_state.get("s_provider", "Claude").lower()
                # )
                # tanda_rules = {"tango": 4, "vals": 3, "milonga": 3}
                # new_playlist = []
                # tanda_idx = 0
                # for tanda_prompt, style in session_plan:
                #     bundle = translator.translate(tanda_prompt)
                #     result = _select_tanda(bundle, df)
                #     if result and result.tanda:
                #         expected_count = tanda_rules.get(style, 4)
                #         tracks = result.tanda[:expected_count]
                #         for i, track in enumerate(tracks):
                #             new_playlist.append({...})
                #         if tanda_idx < len(session_plan) - 1:
                #             new_playlist.append({"type": "cortina", ...})
                #         tanda_idx += 1

                new_playlist = []
                picked_per_tanda = final_state.get("picked_tracks") or []
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
                            "tanda_id": tanda_idx,
                        })
                    if tanda_idx < len(picked_per_tanda) - 1:
                        new_playlist.append({
                            "type": "cortina", "title": "Cortina",
                            "duration": "0:20", "source": "agent",
                        })

                if new_playlist:
                    # Append to the existing queue instead of overwriting it,
                    # so successive plans stack rather than replacing the previous tanda.
                    pq = _get_pq()
                    pq.items.extend(new_playlist)
                    _save_pq(pq)

                    if st.session_state.get("auto_enhance", False):
                        from atdj.audio.enhancement import enhance_tanda
                        from atdj.audio.adjustment_graph import compute_intent_overrides
                        from atdj.config import PROCESSED_DIR
                        from pathlib import Path
                        track_paths = []
                        for item in new_playlist:
                            if item["type"] == "song":
                                raw_path = pq.resolve_raw_path(item)
                                if raw_path:
                                    track_paths.append(Path(raw_path))
                        if track_paths:
                            try:
                                stored_intent = st.session_state.get("stored_adjustment_intent")
                                overrides = (
                                    compute_intent_overrides(stored_intent, len(track_paths))
                                    if stored_intent else None
                                )
                                enhance_tanda(track_paths, Path(PROCESSED_DIR), param_overrides=overrides)
                                st.session_state.setdefault("agent_notifications", []).append(
                                    {"type": "decision", "text": f"Enhanced {len(track_paths)} tracks", "timestamp": ""}
                                )
                            except Exception as e:
                                st.session_state.setdefault("agent_notifications", []).append(
                                    {"type": "warning", "text": f"Enhancement skipped: {e}", "timestamp": ""}
                                )

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
                    "auto_enhance_on": st.session_state.get("auto_enhance", False),
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
                    "store_intent": False,
                    "intent_to_store": None,
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

            if final.get("store_intent") and st.session_state.get("auto_enhance"):
                st.session_state["stored_adjustment_intent"] = final["intent_to_store"]

            for entry in final.get("activity_log", []):
                st.session_state.setdefault("agent_notifications", []).append(
                    {"type": "info", "text": entry.get("message", ""),
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
                    render_audio_player(
                        file_path, gap_seconds=effective_gap,
                        max_duration=max_dur, fade_in_seconds=2.0,
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
                        st.rerun()
                with btn2:
                    if st.button("⏭", use_container_width=True, help="Skip to next", key="pb_skip"):
                        pq.next_track()
                        _save_pq(pq)
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
                enh_c, gap_c, cort_c = st.columns(3)
                with enh_c:
                    st.markdown(
                        '<p style="font-size:13px;font-weight:400;color:#31333F;margin:0 0 14px">Quality Enhance</p>',
                        unsafe_allow_html=True,
                    )
                    st.toggle("Quality Enhance", value=False, key="auto_enhance",
                              label_visibility="collapsed",
                              on_change=lambda: _log(f'Quality Enhance turned {"ON" if st.session_state.get("auto_enhance") else "OFF"}.', "info"))
                with gap_c:
                    st.number_input(
                        "Transition (s)", min_value=0, max_value=60, value=10, key="song_gap",
                        label_visibility="visible",
                        on_change=lambda: _log(f'Transition gap set to {st.session_state.get("song_gap")}s.', "info"),
                    )
                with cort_c:
                    st.number_input(
                        "Cortina (s)", min_value=5, max_value=120, value=30, key="cortina_len",
                        label_visibility="visible",
                        on_change=lambda: _log(f'Cortina length set to {st.session_state.get("cortina_len")}s.', "info"),
                    )

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
                pq.items.clear()
                _save_pq(pq)
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
                    sc_c, cb1, cb2, cb3 = st.columns([20, 1, 1, 1])
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
                    sc, _b1, _b2, _b3 = st.columns([20, 1, 1, 1])
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
                    sc, b1, b2, b3 = st.columns([20, 1, 1, 1])
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
        if "activity_log" in st.session_state:
            for entry in st.session_state["activity_log"]:
                notification = {
                    "type": entry.get("level", "info"),
                    "text": f"[{entry.get('node', '?')}] {entry.get('message', '')}",
                    "timestamp": entry.get("timestamp", ""),
                }
                if notification not in st.session_state["agent_notifications"]:
                    st.session_state["agent_notifications"].append(notification)
        notif_colors = {
            "info": ("#E8F4FD", "#1A6FAD"),
            "change": ("#FEF9E7", "#B7770D"),
            "decision": ("#E8F8E8", "#2D8A4E"),
            "warning": ("#FEF9E7", "#B7770D"),
            "error": ("#FDE8E8", "#C44040"),
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
                if results.empty:
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
                                st.session_state.setdefault("agent_notifications", []).append(
                                    {"type": "change", "text": f'You added "{row["title"]}" to playlist end.'}
                                )
                                st.toast(f'"{row["title"]}" added to playlist.', icon="👤")
                                st.rerun()
            else:
                st.caption("Search to find and add songs.")

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
