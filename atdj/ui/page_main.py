"""
AT-DJ — Single-page DJ dashboard.
Sidebar : session history (top) + inline settings (bottom).
Main    : Agent Chat | Music Center | Agent Log
Bottom  : Library / Queue / Upload
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import atdj.config as cfg
from atdj.config import CATALOG_PATH

# ── Constants ────────────────────────────────────────────────────────────────

STYLE_COLORS  = {"TANGO": "#1A5294", "VALS": "#7B2FA0", "MILONGA": "#C44040"}
STYLE_ABBREV  = {"TANGO": "T", "VALS": "V", "MILONGA": "M"}

NOW_PLAYING = {
    "title": "El Retirado", "orchestra": "Carlos Di Sarli",
    "singer": "Roberto Rufino", "style": "TANGO", "year": 1942,
    "progress": 0.35, "track_num": "2 / 3", "source": "agent",
}
QUEUE_STUB = [
    {"type": "cortina", "title": "La Cumparsita (cortina cut)", "duration": "0:22"},
    {"type": "tanda", "style": "VALS",    "orchestra": "Francisco Canaro", "singer": "Roberto Maida",       "decade": "1940s", "source": "agent",
     "tracks": ["Desde El Alma", "Soñar y Nada Más", "Corazón de Oro"]},
    {"type": "cortina", "title": "Poema (cortina cut)", "duration": "0:20"},
    {"type": "tanda", "style": "MILONGA", "orchestra": "Aníbal Troilo",    "singer": "Francisco Fiorentino","decade": "1940s", "source": "agent",
     "tracks": ["Milongueando En El 40", "Para Qué", "Che Papusa Oí"]},
    {"type": "cortina", "title": "Recuerdo (cortina cut)", "duration": "0:18"},
    {"type": "tanda", "style": "TANGO",   "orchestra": "Juan D'Arienzo",   "singer": "Alberto Echagüe",    "decade": "1930s", "source": "user",
     "tracks": ["La Cumparsita", "El Choclo", "La Puñalada"]},
]
# Flat per-song playlist for the music center (replaces tanda-grouped structure)
PLAYLIST_STUB = [
    {"type":"song","title":"El Retirado",          "playing":True, "style":"TANGO",  "orchestra":"Carlos Di Sarli","singer":"Roberto Rufino",      "year":1942,"duration":"3:12","source":"agent","tanda_id":0},
    {"type":"song","title":"La Capilla Blanca",    "playing":False,"style":"TANGO",  "orchestra":"Carlos Di Sarli","singer":"Roberto Rufino",      "year":1943,"duration":"2:58","source":"agent","tanda_id":0},
    {"type":"cortina","title":"La Cumparsita (cortina cut)","duration":"0:22","source":"agent"},
    {"type":"song","title":"Desde El Alma",        "playing":False,"style":"VALS",   "orchestra":"Francisco Canaro","singer":"Roberto Maida",      "year":1940,"duration":"3:05","source":"agent","tanda_id":1},
    {"type":"song","title":"Soñar y Nada Más",     "playing":False,"style":"VALS",   "orchestra":"Francisco Canaro","singer":"Roberto Maida",      "year":1941,"duration":"2:52","source":"agent","tanda_id":1},
    {"type":"song","title":"Corazón de Oro",       "playing":False,"style":"VALS",   "orchestra":"Francisco Canaro","singer":"Roberto Maida",      "year":1942,"duration":"3:08","source":"agent","tanda_id":1},
    {"type":"cortina","title":"Poema (cortina cut)","duration":"0:20","source":"agent"},
    {"type":"song","title":"Milongueando En El 40","playing":False,"style":"MILONGA","orchestra":"Aníbal Troilo",  "singer":"Francisco Fiorentino","year":1940,"duration":"2:44","source":"agent","tanda_id":2},
    {"type":"song","title":"Para Qué",             "playing":False,"style":"MILONGA","orchestra":"Aníbal Troilo",  "singer":"Francisco Fiorentino","year":1941,"duration":"2:51","source":"agent","tanda_id":2},
    {"type":"song","title":"Che Papusa Oí",        "playing":False,"style":"MILONGA","orchestra":"Aníbal Troilo",  "singer":"Francisco Fiorentino","year":1942,"duration":"2:48","source":"agent","tanda_id":2},
    {"type":"cortina","title":"Recuerdo (cortina cut)","duration":"0:18","source":"agent"},
    {"type":"song","title":"La Cumparsita",        "playing":False,"style":"TANGO",  "orchestra":"Juan D'Arienzo","singer":"Alberto Echagüe",     "year":1935,"duration":"2:39","source":"user", "tanda_id":3},
    {"type":"song","title":"El Choclo",            "playing":False,"style":"TANGO",  "orchestra":"Juan D'Arienzo","singer":"Alberto Echagüe",     "year":1936,"duration":"2:55","source":"user", "tanda_id":3},
    {"type":"song","title":"La Puñalada",          "playing":False,"style":"TANGO",  "orchestra":"Juan D'Arienzo","singer":"Alberto Echagüe",     "year":1937,"duration":"3:02","source":"user", "tanda_id":3},
]
TANDA_PALETTE = ["#8B1A1A", "#1A4E8B", "#1A6B2A", "#7B3F00", "#4A1A7B", "#1A6B6B"]
ENERGY_STUB = {  # title → energy 0–1; used for the Energy Arc chart
    "El Retirado": 0.52, "La Capilla Blanca": 0.55,
    "Desde El Alma": 0.42, "Soñar y Nada Más": 0.45, "Corazón de Oro": 0.48,
    "Milongueando En El 40": 0.68, "Para Qué": 0.72, "Che Papusa Oí": 0.74,
    "La Cumparsita": 0.80, "El Choclo": 0.82, "La Puñalada": 0.85,
}

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
PLANNING_DESCRIPTIONS = {
    "convention": "Strict rules: same orchestra, singer & decade per tanda. No exceptions.",
    "flexible":   "Agent may mix if it supplies a written rationale. Style is always enforced.",
}

CHAT_STUB = "Got it — I'm still warming up. Connect me to the music pool for real responses. _(stub)_"
CHAT_CONTEXTS = {"Any": "💬", "Feedback": "🎯", "Music Q": "🎵", "Plan": "📋"}

SESSION_HISTORY = [
    {"label": "Tonight · 2026-03-18", "duration": "0h 12m", "songs": 2},
    {"label": "2026-03-15",           "duration": "3h 02m", "songs": 34},
    {"label": "2026-03-10",           "duration": "2h 45m", "songs": 31},
    {"label": "2026-03-01",           "duration": "1h 58m", "songs": 22},
]

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
        f'<span style="font-size:11px;background:{bg};color:{color};'
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
        f'<span style="font-size:11px;color:#999999">{item["duration"]}</span>'
        f'</div>'
    )

def _tanda_card(item: dict, compact: bool = False) -> str:
    clr = STYLE_COLORS.get(item["style"], "#888")
    badge_html = _badge(item["style"], clr + "22", clr)
    src_html   = _source_badge(item.get("source", "agent"))
    singer_line = (
        f'<p style="font-size:11px;color:#888;margin:0 0 3px">Singer: {item["singer"]}</p>'
        if item.get("singer") else ""
    )
    if compact:
        return (
            f'<div style="background:#FFF;border:1px solid #EBEBEB;border-radius:8px;'
            f'padding:10px 14px;margin-bottom:5px">'
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">'
            f'{badge_html}{src_html}</div>'
            f'<p style="font-weight:600;font-size:13px;margin:0 0 1px">{item["orchestra"]}</p>'
            f'<p style="font-size:11px;color:#999;margin:0">{item["decade"]}</p>'
            f'</div>'
        )
    tracks_html = "".join(
        f'<li style="font-size:11px;color:#666;margin:1px 0">{t}</li>'
        for t in item.get("tracks", [])
    )
    return (
        f'<div style="background:#FFF;border:1px solid #EBEBEB;border-radius:8px;'
        f'padding:12px 16px;margin-bottom:5px">'
        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
        f'{badge_html}{src_html}</div>'
        f'<p style="font-weight:600;margin:0 0 2px">{item["orchestra"]}</p>'
        f'<p style="font-size:11px;color:#999;margin:0 0 2px">{item["decade"]}</p>'
        f'{singer_line}'
        f'<ul style="margin:0;padding-left:14px">{tracks_html}</ul>'
        f'</div>'
    )

def _tanda_color(tanda_id: int) -> str:
    return TANDA_PALETTE[tanda_id % len(TANDA_PALETTE)]

def _hr():
    st.markdown(
        '<hr style="margin:22px 0 18px;border:none;border-top:1px solid #EEEEEE">',
        unsafe_allow_html=True,
    )

def _lbl(text: str):
    """Tiny uppercase section label (10px) — one of the 4 font sizes used site-wide."""
    st.markdown(
        f'<p style="font-size:10px;font-weight:700;color:#AAAAAA;letter-spacing:.08em;'
        f'text-transform:uppercase;margin:4px 0 8px">{text}</p>',
        unsafe_allow_html=True,
    )

def _render_energy_chart(playlist: list):
    """Solid line = played · Dotted line = planned · Hover = song card."""
    import altair as alt

    songs = [s for s in playlist if s["type"] == "song"]
    if not songs:
        st.caption("No songs yet.")
        return

    playing_pos = next((i for i, s in enumerate(songs) if s.get("playing")), 0)
    records = []
    for idx, s in enumerate(songs):
        decade = f"{(int(s['year']) // 10) * 10}s" if s.get("year") else "—"
        records.append({
            "pos":       idx,
            "title":     s["title"],
            "orchestra": s["orchestra"],
            "singer":    s.get("singer", "—") or "—",
            "style":     s["style"],
            "decade":    decade,
            "source":    "💡 Agent" if s.get("source") == "agent" else "👤 You",
            "energy":    ENERGY_STUB.get(s["title"], 0.40 + 0.08 * (idx % 6)),
            "segment":   "played" if idx <= playing_pos else "planned",
        })

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
    dots = base.mark_circle(size=55, opacity=0.9).encode(
        color=alt.condition(
            alt.datum.segment == "played",
            alt.value("#1A5294"),
            alt.value("#BBBBBB"),
        )
    )
    st.altair_chart(
        (played_line + planned_line + dots)
        .properties(height=213)
        .configure_view(strokeWidth=0)
        .interactive(),
        use_container_width=True,
    )

# ── Data helpers ─────────────────────────────────────────────────────────────

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

def _spectrogram_stub(seed: int, brighter: bool = False):
    rng  = np.random.default_rng(seed)
    data = rng.random((64, 128))
    if brighter:
        data = np.clip(data * 1.35, 0, 1)
    fig, ax = plt.subplots(figsize=(5, 2.2))
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#111")
    ax.imshow(data, aspect="auto", origin="lower", cmap="magma", interpolation="lanczos")
    ax.set_xlabel("Time →", fontsize=7, color="#666")
    ax.set_ylabel("Hz →",   fontsize=7, color="#666")
    ax.tick_params(colors="#888", labelsize=6)
    fig.tight_layout(pad=0.4)
    return fig

# ── Settings helpers ─────────────────────────────────────────────────────────

def _init_settings():
    if st.session_state.get("settings_initialized"):
        return
    pm = {"claude": "Claude", "gemini": "Gemini", "ollama": "Ollama"}
    st.session_state["s_provider"] = pm.get(cfg.LLM_PROVIDER, "Claude")
    st.session_state["s_model"]    = cfg.CLAUDE_MODEL
    st.session_state["s_api_key"]  = cfg.ANTHROPIC_API_KEY or ""
    st.session_state["s_planning"] = "convention"
    st.session_state["settings_initialized"] = True

# ── Sidebar ──────────────────────────────────────────────────────────────────

def _sidebar():
    with st.sidebar:

        # ── Sessions ──────────────────────────────────────────────────────────
        st.markdown(
            """<style>
            /* ── Compact icon buttons in sidebar ── */
            section[data-testid="stSidebar"] div[data-testid="stButton"] button {
                height: 24px !important;
                min-height: 24px !important;
                max-height: 24px !important;
                width: 100% !important;
                padding: 0 6px !important;
                line-height: 1 !important;
                font-size: 11px !important;
                border-radius: 4px !important;
            }
            section[data-testid="stSidebar"] div[data-testid="stButton"] button > div {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                padding: 0 !important;
            }
            section[data-testid="stSidebar"] div[data-testid="stButton"] button p {
                margin: 0 !important;
                padding: 0 !important;
                line-height: 1 !important;
                font-size: 11px !important;
            }
            /* ── Session scroll buttons: 4 attrs beats music-section 3 attrs, match card height ── */
            section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]
                [data-testid="stVerticalBlock"] div[data-testid="stButton"] button {
                height: 26px !important;
                min-height: 26px !important;
                max-height: 26px !important;
            }
            /* ── Push session buttons down to align with card center ── */
            section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] div[data-testid="stButton"] {
                margin-top: 13px !important; margin-bottom: 0 !important;
            }
            /* ── Shrink gap + padding in session scroll container ── */
            section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]
                > [data-testid="stVerticalBlock"] {
                gap: 2px !important;
                padding: 4px !important;
            }
            /* ── Shrink gap between the two buttons in btns_col ── */
            section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]
                [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] {
                gap: 1px !important;
            }
            /* ── Vertically center all sidebar horizontal rows ── */
            section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
                align-items: center !important;
            }
            section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"] {
                align-self: center !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
            }
            </style>""",
            unsafe_allow_html=True,
        )
        hdr_col, plus_col = st.columns([5, 1], vertical_alignment="center")
        with hdr_col:
            st.markdown('<p style="font-size:13px;font-weight:600;margin:0">Sessions</p>', unsafe_allow_html=True)
        with plus_col:
            if st.button("＋", key="new_session", help="New session", use_container_width=True):
                import datetime
                sessions = st.session_state.setdefault("sessions", list(SESSION_HISTORY))
                new = {
                    "label": datetime.date.today().strftime("%Y-%m-%d") + " (new)",
                    "duration": "0h 00m", "tandas": 0, "active": False,
                }
                sessions.insert(0, new)
                st.session_state["sessions"] = sessions
                st.session_state["active_session"] = 0
                st.rerun()

        sessions = st.session_state.setdefault("sessions", list(SESSION_HISTORY))

        if "active_session" not in st.session_state:
            st.session_state["active_session"] = 0
        if "renaming_session" not in st.session_state:
            st.session_state["renaming_session"] = None

        session_scroll = st.container(height=200)
        with session_scroll:
            for i, s in enumerate(sessions):
                is_active   = st.session_state["active_session"] == i
                is_renaming = st.session_state["renaming_session"] == i

                if is_renaming:
                    new_name = st.text_input(
                        "Rename", value=s["label"],
                        key=f"rename_input_{i}", label_visibility="collapsed",
                    )
                    save_col, cancel_col = st.columns(2)
                    with save_col:
                        if st.button("Save", key=f"rename_save_{i}", use_container_width=True):
                            sessions[i]["label"] = new_name
                            st.session_state["sessions"] = sessions
                            st.session_state["renaming_session"] = None
                            st.rerun()
                    with cancel_col:
                        if st.button("Cancel", key=f"rename_cancel_{i}", use_container_width=True):
                            st.session_state["renaming_session"] = None
                            st.rerun()

                elif is_active:
                    card_col, btns_col = st.columns([6, 1])
                    songs = s.get("songs", 0)
                    with card_col:
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:6px;'
                            f'padding:5px 8px;border-radius:4px;'
                            f'background:#EEF4FB;border:1px solid #C5D9EE;border-left:3px solid #1A5294;'
                            f'overflow:hidden">'
                            f'<span style="font-size:11px;font-weight:600;color:#1A5294;'
                            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1 1 0;line-height:1.3">'
                            f'{s["label"]}</span>'
                            f'<span style="font-size:10px;color:#7A9EC0;white-space:nowrap;flex-shrink:0;line-height:1.3">'
                            f'{s["duration"]} · {songs} songs</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with btns_col:
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("✎", key=f"rename_{i}", help="Rename", use_container_width=True):
                                st.session_state["renaming_session"] = i
                                st.rerun()
                        with b2:
                            if st.button("x", key=f"del_{i}", help="Delete", use_container_width=True):
                                sessions.pop(i)
                                st.session_state["sessions"] = sessions
                                st.session_state["active_session"] = min(i, max(0, len(sessions) - 1))
                                st.rerun()

                else:
                    card_col, btns_col = st.columns([6, 1])
                    songs = s.get("songs", 0)
                    with card_col:
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:6px;'
                            f'padding:5px 8px;border-radius:4px;'
                            f'background:#FFFFFF;border:1px solid #E0E0E0;border-left:3px solid #BBBBBB;'
                            f'overflow:hidden">'
                            f'<span style="font-size:11px;font-weight:600;color:#333;'
                            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1 1 0;line-height:1.3">'
                            f'{s["label"]}</span>'
                            f'<span style="font-size:10px;color:#999;white-space:nowrap;flex-shrink:0;line-height:1.3">'
                            f'{s["duration"]} · {songs} songs</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with btns_col:
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("▷", key=f"sel_{i}", help="Open session", use_container_width=True):
                                st.session_state["active_session"] = i
                                st.toast(f"Loaded: {s['label']}", icon="📂")
                                st.rerun()
                        with b2:
                            if st.button("x", key=f"del_{i}", help="Delete", use_container_width=True):
                                sessions.pop(i)
                                st.session_state["sessions"] = sessions
                                new_active = st.session_state["active_session"]
                                if new_active >= len(sessions):
                                    new_active = max(0, len(sessions) - 1)
                                st.session_state["active_session"] = new_active
                                st.rerun()

        # ── Settings ──────────────────────────────────────────────────────────
        st.divider()
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
    st.markdown(
        '<p style="font-size:13px;font-weight:700;color:#1A1A1A;margin:0 0 10px">Agent Chat</p>',
        unsafe_allow_html=True,
    )

    if "chat_msgs" not in st.session_state:
        st.session_state["chat_msgs"] = [
            {"role": "user",      "context": "Any", "content": "What style should we open with tonight?"},
            {"role": "assistant", "content": "For a cold room, I'd start with a rhythmic D'Arienzo tango set to warm things up — then introduce vals after you see the floor respond. _(stub)_"},
        ]

    # Chat history — scrollable
    chat_container = st.container(height=530)
    with chat_container:
        for msg in st.session_state["chat_msgs"]:
            avatar = "👤" if msg["role"] == "user" else "💡"
            with st.chat_message(msg["role"], avatar=avatar):
                if msg["role"] == "user" and msg.get("context") and msg["context"] != "Any":
                    st.caption(f"{CHAT_CONTEXTS.get(msg['context'], '')} {msg['context']}")
                st.markdown(msg["content"])

    # Unified input card (Claude-style)
    with st.container(border=True):
        st.markdown('<div id="chat-input-card"></div>', unsafe_allow_html=True)
        msg_text = st.text_area(
            "Message", placeholder="Message the agent…",
            label_visibility="collapsed", key="chat_text_input",
            height=87,
        )
        ctx_col, mode_col, send_col = st.columns([3, 3, 1])
        with ctx_col:
            context = st.selectbox(
                "Context", list(CHAT_CONTEXTS.keys()), index=0,
                format_func=lambda k: f"{CHAT_CONTEXTS[k]} {k}",
                label_visibility="collapsed", key="chat_context_select",
            )
        with mode_col:
            planning_opts = ["convention", "flexible"]
            cur_plan = st.session_state.get("s_planning", "convention")
            cur_idx = planning_opts.index(cur_plan) if cur_plan in planning_opts else 0
            sel_plan = st.selectbox(
                "Mode",
                planning_opts,
                index=cur_idx,
                format_func=lambda x: "🎩 Convention" if x == "convention" else "🎨 Flexible",
                label_visibility="collapsed", key="chat_mode_select",
            )
            st.session_state["s_planning"] = sel_plan
        with send_col:
            send = st.button("➤", use_container_width=True, key="chat_send", help="Send")

    if send and msg_text.strip():
        st.session_state["chat_msgs"].append(
            {"role": "user", "context": context, "content": msg_text.strip()}
        )
        st.session_state["chat_msgs"].append(
            {"role": "assistant", "content": CHAT_STUB}
        )
        st.rerun()

# ── Center column: Music ─────────────────────────────────────────────────────

def _section_music():
    # Compact icon buttons in playlist rows
    st.markdown(
        """<style>
        /* ── Playlist compact icon buttons (default) ── */
        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] button[kind="secondary"] {
            height: 26px !important; min-height: 26px !important; max-height: 26px !important;
            padding: 0 4px !important; font-size: 11px !important;
            line-height: 1 !important; min-width: 0 !important;
            border-radius: 4px !important;
        }
        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] button[kind="secondary"] > div {
            padding: 0 !important;
        }
        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] button[kind="secondary"] p {
            margin: 0 !important; font-size: 11px !important;
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
        [data-testid="stToggle"] label span { white-space: nowrap !important; font-size: 11px !important; }
        /* ── Collapse the marker container so it takes no space ── */
        [data-testid="stElementContainer"]:has(#pb-play-marker) {
            display: none !important;
        }
        /* ── Play button (▶): secondary colored blue via adjacent marker ── */
        [data-testid="stElementContainer"]:has(#pb-play-marker)
            + [data-testid="stElementContainer"] [data-testid="stBaseButton-secondary"] {
            background: #1A5294 !important; border-color: #1A5294 !important; color: #FFF !important;
        }
        [data-testid="stElementContainer"]:has(#pb-play-marker)
            + [data-testid="stElementContainer"] [data-testid="stBaseButton-secondary"]:hover {
            background: #0F3369 !important; border-color: #0F3369 !important;
        }
        /* ── Transport buttons (▶ ⏹ ⏮ ⏭): 4 nested HBs deep — unique to btns_sub grid ── */
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"]
            [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"]
            button[kind="secondary"] {
            height: 36px !important; min-height: 36px !important; max-height: 36px !important;
            padding: 0 8px !important; font-size: 14px !important; line-height: 1 !important;
            overflow: hidden !important;
        }
        /* ── Playlist/scroll buttons: stLayoutWrapper ancestor overrides to 28px ── */
        [data-testid="stLayoutWrapper"] [data-testid="stHorizontalBlock"]
            [data-testid="stHorizontalBlock"] button[kind="secondary"] {
            height: 28px !important; min-height: 28px !important; max-height: 28px !important;
            padding: 0 4px !important; font-size: 11px !important; line-height: 1 !important;
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
        [data-testid="stMain"] > [data-testid="stVerticalBlock"]
            > [data-testid="stHorizontalBlock"]
            > [data-testid="stColumn"]
            > [data-testid="stVerticalBlock"]
            > [data-testid="stHorizontalBlock"] {
            column-gap: 20px !important;
            gap: 20px !important;
        }
        /* ── Agent chat: disable textarea resize handle ── */
        [data-testid="stColumn"]:has(#agent-col-marker) textarea {
            resize: none !important;
        }
        /* ── Agent chat send button: match selectbox height ── */
        [data-testid="stColumn"]:has(#chat-input-card)
            button[data-testid="stBaseButton-secondary"] {
            height: 40px !important;
            min-height: 40px !important;
            max-height: 40px !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )
    main_col, agent_col = st.columns([4, 5])

    with main_col:
        # ── Row 1: NOW PLAYING (col1) | PLAYBACK (col2) | ENERGY ARC (col3) ──
        # Ratios [2,2,5] — row 3 uses [4,5] so col1+col2=4 aligns with SEARCH MUSIC
        np_col, pb_col, ea_col = st.columns([2, 3, 4])

        with np_col:
            _lbl("Now Playing")
            np_clr = STYLE_COLORS[NOW_PLAYING["style"]]
            np_decade = f'{(NOW_PLAYING["year"] // 10) * 10}s'
            np_singer_html = (
                f'<p style="color:#666;font-size:11px;margin:0 0 3px">{NOW_PLAYING["singer"]}</p>'
                if NOW_PLAYING.get("singer") else ""
            )
            st.markdown(
                f'<div style="background:#FFF;border:1px solid #EBEBEB;border-left:3px solid {np_clr};'
                f'border-radius:8px;padding:10px 14px;margin:4px 0 6px">'
                f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
                f'{_badge(NOW_PLAYING["style"], np_clr+"22", np_clr)}'
                f'{_source_badge(NOW_PLAYING["source"])}</div>'
                f'<p style="font-size:18px;font-weight:700;margin:0 0 6px">{NOW_PLAYING["title"]}</p>'
                f'<p style="color:#333;font-size:12px;font-weight:600;margin:0 0 3px">{NOW_PLAYING["orchestra"]}</p>'
                f'{np_singer_html}'
                f'<p style="color:#999;font-size:11px;margin:0">{np_decade} · {NOW_PLAYING["year"]}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.progress(NOW_PLAYING["progress"])
            st.caption(f'Track {NOW_PLAYING["track_num"]} · 1:24 remaining')

        with pb_col:
            _lbl("Playback")
            vol_sub, btns_sub = st.columns([1, 2])
            with vol_sub:
                # Vertical volume slider (rows 1-3)
                st.markdown(
                    '<p style="font-size:10px;color:#AAAAAA;margin:0 0 2px;text-align:center">Vol</p>'
                    '<div style="display:flex;justify-content:center;align-items:center;'
                    'height:106px;padding:2px 0">'
                    '<input type="range" min="0" max="100" value="75" '
                    'style="writing-mode:vertical-lr;direction:rtl;height:96px;width:20px;'
                    'cursor:pointer;accent-color:#1A5294;"></div>',
                    unsafe_allow_html=True,
                )
            with btns_sub:
                # Row 1: Play | Stop
                r1c1, r1c2 = st.columns(2)
                with r1c1:
                    st.markdown('<div id="pb-play-marker"></div>', unsafe_allow_html=True)
                    if st.button("▶", use_container_width=True, help="Play / Pause", type="secondary", key="pb_play"):
                        st.toast("Playing.", icon="▶")
                with r1c2:
                    if st.button("⏹", use_container_width=True, help="Stop", key="pb_stop"):
                        st.toast("Stopped.", icon="⏹")
                # Row 2: Reverse | Skip
                r2c1, r2c2 = st.columns(2)
                with r2c1:
                    if st.button("⏮", use_container_width=True, help="Previous track", key="pb_prev"):
                        st.toast("Previous track.", icon="⏮")
                with r2c2:
                    if st.button("⏭", use_container_width=True, help="Skip to next", key="pb_skip"):
                        st.toast("Skipped.", icon="⏭")
                # Row 3: Auto enhance (spans btns_sub width)
                st.toggle("Auto enhance", value=True, key="auto_enhance")
            # Row 4: Gap setting — label + input on same row
            gl, gi = st.columns([2, 3], vertical_alignment="center")
            with gl:
                st.markdown(
                    '<p style="font-size:12px;color:#555;margin:0">Gap (sec)</p>',
                    unsafe_allow_html=True,
                )
            with gi:
                st.number_input(
                    "Gap", min_value=0, max_value=60, value=10, key="song_gap",
                    label_visibility="collapsed",
                )

        with ea_col:
            _lbl("Energy Arc")
            _render_energy_chart(st.session_state.get("playlist", list(PLAYLIST_STUB)))

        # ── Row 2: FULL PLAYLIST (spans col1+col2+col3, full main_col width) ──
        _hr()
        _lbl("Full Playlist")
        playlist = st.session_state.get("playlist", list(PLAYLIST_STUB))

        with st.container(height=441):
            for i, item in enumerate(playlist):
                # ── Cortina row ──
                if item["type"] == "cortina":
                    b_src_c = _source_icon(item.get("source", "agent"))
                    b_cort  = _badge_sm("CORTINA", "#EEEEEE", "#888888")
                    sc_c, btns_c = st.columns([8, 1])
                    with sc_c:
                        st.markdown(
                            f'<div style="padding:5px 8px;border-left:2px solid #BBBBBB;'
                            f'background:#F2F2F2;margin-bottom:2px;display:flex;'
                            f'align-items:center;gap:5px;overflow:hidden;white-space:nowrap">'
                            f'{b_cort}{b_src_c}'
                            f'<span style="font-size:12px;font-weight:700;color:#555;'
                            f'flex-shrink:0">{item["title"]}</span>'
                            f'<span style="font-size:12px;color:#999;"> · {item["duration"]}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with btns_c:
                        cb1, cb2, cb3 = st.columns(3)
                        with cb1:
                            if i > 0:
                                if st.button("↑", key=f"pl_up_{i}", help="Move up", use_container_width=True):
                                    playlist[i], playlist[i - 1] = playlist[i - 1], playlist[i]
                                    st.session_state["playlist"] = playlist
                                    st.rerun()
                        with cb2:
                            if i < len(playlist) - 1:
                                if st.button("↓", key=f"pl_dn_{i}", help="Move down", use_container_width=True):
                                    playlist[i], playlist[i + 1] = playlist[i + 1], playlist[i]
                                    st.session_state["playlist"] = playlist
                                    st.rerun()
                        with cb3:
                            if st.button("x", key=f"pl_rm_{i}", help="Remove", use_container_width=True):
                                playlist.pop(i)
                                st.session_state["playlist"] = playlist
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

                if item.get("playing"):
                    st.markdown(
                        f'<div style="padding:5px 8px;border-left:3px solid {clr};'
                        f'background:{clr}22;margin-bottom:2px;display:flex;align-items:center;'
                        f'gap:5px;overflow:hidden;white-space:nowrap">'
                        f'<span style="font-size:11px;color:{clr};flex-shrink:0">▶</span>'
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
                    sc, btns_col = st.columns([8, 1])
                    with sc:
                        st.markdown(
                            f'<div style="padding:5px 8px;border-left:2px solid {clr}88;'
                            f'background:{clr}11;margin-bottom:2px;display:flex;'
                            f'align-items:center;gap:5px;overflow:hidden;white-space:nowrap">'
                            f'{b_style}{b_src}'
                            f'<span style="font-size:12px;font-weight:700;color:#333;'
                            f'flex-shrink:0">{item["title"]}</span>'
                            f'<span style="font-size:12px;color:#777;overflow:hidden;'
                            f'text-overflow:ellipsis"> · {meta}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with btns_col:
                        b1, b2, b3 = st.columns(3)
                        with b1:
                            if prev_s >= 0 and not playlist[prev_s].get("playing", False):
                                if st.button("↑", key=f"pl_up_{i}", help="Move up", use_container_width=True):
                                    playlist[i], playlist[prev_s] = playlist[prev_s], playlist[i]
                                    st.session_state["playlist"] = playlist
                                    st.rerun()
                        with b2:
                            if next_s >= 0:
                                if st.button("↓", key=f"pl_dn_{i}", help="Move down", use_container_width=True):
                                    playlist[i], playlist[next_s] = playlist[next_s], playlist[i]
                                    st.session_state["playlist"] = playlist
                                    st.rerun()
                        with b3:
                            if st.button("x", key=f"pl_rm_{i}", help="Remove", use_container_width=True):
                                playlist.pop(i)
                                st.session_state["playlist"] = playlist
                                st.rerun()

        # ── Row 3: SEARCH MUSIC (col1+col2) | SESSION LOG (col3) ─────────────
        # [4,5] mirrors row-1 [2,2,5]: 4=col1+col2, 5=col3
        _hr()
        sm_col, sl_col = st.columns([5, 4])

        with sm_col:
            _lbl("Search Music")
            query = st.text_input(
                "Search", placeholder="Title, artist, style…",
                label_visibility="collapsed", key="music_search",
            )
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
                    pl = st.session_state.get("playlist", list(PLAYLIST_STUB))
                    next_tid = max((p.get("tanda_id", 0) for p in pl if p["type"] == "song"), default=0) + 1
                    for _, row in results.iterrows():
                        rclr = STYLE_COLORS.get(row["style"].upper(), "#888")
                        res_col, add_col = st.columns([5, 1], vertical_alignment="center")
                        with res_col:
                            singer_part = f' · {row["singer"]}' if str(row.get("singer", "")) not in ("", "nan") else ""
                            st.markdown(
                                f'<div style="padding:3px 0;font-size:12px;'
                                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                                f'<span style="display:inline-block;width:7px;height:7px;background:{rclr};'
                                f'border-radius:50%;margin-right:5px;vertical-align:middle"></span>'
                                f'<strong>{row["title"]}</strong>'
                                f'<span style="color:#777"> · {row["orchestra"]}{singer_part} · {int(row["year"])}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        with add_col:
                            if st.button("＋", key=f"srch_add_{row['title']}", use_container_width=True,
                                         help="Add to end of playlist"):
                                entry = {
                                    "type": "song", "title": row["title"], "playing": False,
                                    "style": row["style"].upper(), "orchestra": row["orchestra"],
                                    "singer": str(row.get("singer", "")) if str(row.get("singer", "")) != "nan" else "",
                                    "year": int(row["year"]) if pd.notna(row.get("year")) else 0,
                                    "source": "user", "tanda_id": next_tid,
                                }
                                pl.append(entry)
                                st.session_state["playlist"] = pl
                                st.session_state.setdefault("agent_notifications", []).append(
                                    {"type": "change", "text": f'You added "{row["title"]}" to playlist end.'}
                                )
                                st.toast(f'"{row["title"]}" added to playlist.', icon="👤")
                                st.rerun()
            else:
                st.caption("Search to find and add songs.")

        with sl_col:
            _lbl("Upload")
            with st.container(height=200):
                _tab_upload()

    # ── Agent Chat (full height, right column) ────────────────────────────────
    with agent_col:
        _section_chat()
        st.markdown(
            '<hr style="margin:22px 0 18px;border:none;border-top:1px solid #EEEEEE">',
            unsafe_allow_html=True,
        )
        _lbl("Session Log")
        if "agent_notifications" not in st.session_state:
            st.session_state["agent_notifications"] = [
                {"type": "info",   "text": "Session started — 8 tandas planned."},
                {"type": "change", "text": "Tanda 2 updated: switched from D'Arienzo to Canaro (warmer opening requested)."},
                {"type": "info",   "text": "Crowd energy detected as moderate — vals tanda scheduled for tanda 3."},
                {"type": "change", "text": "Tanda 4 adjusted: D'Arienzo inserted after feedback 'more rhythm'."},
                {"type": "change", "text": "Tanda 5 set to Biagi by you — marked as hand-picked."},
                {"type": "info",   "text": "Cortina after tanda 5 extended to 30s — floor transition detected."},
                {"type": "change", "text": "Tanda 6 swapped: Pugliese replaces Fresedo (user requested more drama)."},
                {"type": "info",   "text": "Energy arc rising — milonga scheduled for tanda 7 to sustain momentum."},
                {"type": "change", "text": "Tanda 8 locked: Fresedo vals for cool-down close."},
                {"type": "info",   "text": "All 8 tandas confirmed. Session map finalized."},
            ]
        notif_colors = {"info": ("#E8F4FD", "#1A6FAD"), "change": ("#FEF9E7", "#B7770D")}
        with st.container(height=200):
            for n in reversed(st.session_state["agent_notifications"]):
                bg, clr = notif_colors.get(n["type"], ("#F7F7F7", "#555"))
                st.markdown(
                    f'<div style="background:{bg};border-left:3px solid {clr};'
                    f'border-radius:0 4px 4px 0;padding:5px 10px;margin-bottom:4px;font-size:12px;color:#333">'
                    f'{n["text"]}</div>',
                    unsafe_allow_html=True,
                )

# ── Right column: Agent Log ──────────────────────────────────────────────────

def _section_log():
    st.markdown("#### Session Planning Log")

    if "agent_notifications" not in st.session_state:
        st.session_state["agent_notifications"] = [
            {"type": "info",    "text": "Session started — 8 tandas planned."},
            {"type": "change",  "text": "Tanda 2 updated: switched from D'Arienzo to Canaro (warmer opening requested)."},
            {"type": "info",    "text": "Crowd energy detected as moderate — vals tanda scheduled for tanda 3."},
            {"type": "change",  "text": "Tanda 4 adjusted: D'Arienzo inserted after feedback 'more rhythm'."},
            {"type": "change",  "text": "Tanda 5 set to Biagi by you — marked as hand-picked."},
            {"type": "info",    "text": "Cortina after tanda 5 extended to 30s — floor transition detected."},
            {"type": "change",  "text": "Tanda 6 swapped: Pugliese replaces Fresedo (user requested more drama)."},
            {"type": "info",    "text": "Energy arc rising — milonga scheduled for tanda 7 to sustain momentum."},
            {"type": "change",  "text": "Tanda 8 locked: Fresedo vals for cool-down close."},
            {"type": "info",    "text": "All 8 tandas confirmed. Session map finalized."},
        ]

    notif_colors = {"info": ("#E8F4FD", "#1A6FAD"), "change": ("#FEF9E7", "#B7770D")}
    log_container = st.container(height=220)
    with log_container:
        for n in reversed(st.session_state["agent_notifications"]):
            bg, clr = notif_colors.get(n["type"], ("#F7F7F7", "#555"))
            st.markdown(
                f'<div style="background:{bg};border-left:3px solid {clr};'
                f'border-radius:0 4px 4px 0;padding:6px 10px;margin-bottom:5px;font-size:11px;color:#333">'
                f'{n["text"]}</div>',
                unsafe_allow_html=True,
            )

# ── Bottom: Library, Queue, Upload ──────────────────────────────────────────

def _section_library():
    st.divider()
    tab_lib, tab_upload = st.tabs(["🔍 Library", "📤 Upload"])

    with tab_lib:
        _tab_library()
    with tab_upload:
        _tab_upload()


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
    queue = st.session_state.get("live_queue", list(QUEUE_STUB))

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
                    f'<span style="font-size:11px;color:#AAA">{item["duration"]}</span>'
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
                    f'<span style="font-size:11px;color:#999">{item.get("decade","")}</span>'
                    f'</div>', unsafe_allow_html=True)
        with row_r:
            if st.button("x", key=f"rm_{i}", help="Remove from queue", use_container_width=True):
                queue.pop(i)
                st.session_state["live_queue"] = queue
                st.toast("Removed from queue.", icon="🗑")
                st.rerun()


def _tab_upload():
    uploaded = st.file_uploader(
        "Drop a track", type=["mp3", "wav", "flac"], label_visibility="collapsed",
    )
    if uploaded is not None:
        st.markdown(f"**{uploaded.name}**")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Before**")
            fig = _spectrogram_stub(42)
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
        with c2:
            st.markdown("**After**")
            fig2 = _spectrogram_stub(99, brighter=True)
            st.pyplot(fig2, use_container_width=True)
            plt.close(fig2)
        m1, m2, m3 = st.columns(3)
        m1.metric("Est. SNR", "18.3 dB", "+5.8 dB")
        m2.metric("Duration", "3:12")
        m3.metric("Format", uploaded.name.rsplit(".", 1)[-1].upper())
        st.write("")
        ec1, ec2 = st.columns([2, 1])
        with ec1:
            if st.button("Enhance & Add to Pool", type="primary", use_container_width=True):
                with st.spinner("Enhancing…"):
                    import time; time.sleep(1.5)
                st.toast("Enhancement complete — track added to pool. _(stub)_", icon="✅")
        with ec2:
            if st.button("Add Without Enhancing", use_container_width=True):
                st.toast("Track added to pool as-is. _(stub)_", icon="📂")

# ── Main entry point ─────────────────────────────────────────────────────────

def show():
    _sidebar()

    # Header — compact: title + active session subtitle
    _sessions = st.session_state.get("sessions", SESSION_HISTORY)
    _active   = st.session_state.get("active_session", 0)
    _sess_lbl = _sessions[_active]["label"] if _sessions else "Tonight"
    st.markdown(
        f'<div style="padding:4px 0 2px;display:flex;align-items:baseline;gap:12px">'
        f'<span style="font-size:18px;font-weight:700;color:#1A1A1A">DJ Console</span>'
        f'<span style="font-size:12px;color:#999">{_sess_lbl}</span>'
        f'</div>'
        f'<hr style="margin:4px 0 10px;border:none;border-top:1px solid #EBEBEB">',
        unsafe_allow_html=True,
    )

    _section_music()
