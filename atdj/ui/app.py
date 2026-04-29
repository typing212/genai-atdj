import sys
from pathlib import Path as _Path
_project_root = str(_Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
from atdj.ui import page_main

_CSS = """
<style>
/* Chrome — hide clutter, never touch sidebar toggle */
#MainMenu, footer { visibility: hidden; }
[data-testid="stDeployButton"],
[data-testid="stToolbarActions"] { display: none; }
/* Ensure sidebar re-open button always shows */
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapsedControl"] * { visibility: visible !important; display: flex !important; }

/* Reduce top padding and inner gap */
[data-testid="stMainBlockContainer"] { padding-top: 64px !important; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: 10px !important; }

/* Base */
html, body, [data-testid="stAppViewContainer"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
    background: #FAFAFA; color: #1A1A1A;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #F0F0F0;
    border-right: 1px solid #E4E4E4;
}
[data-testid="stSidebar"] * { font-size: 13px; }

/* Buttons — border-only style */
.stButton > button {
    border: 1px solid #E0E0E0; border-radius: 6px;
    background: #FFF; color: #333; font-size: 13px;
    transition: border-color .15s, color .15s;
}
.stButton > button:hover { border-color: #1A5294 !important; color: #1A5294 !important; }
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {
    background: #1A5294 !important; border-color: #1A5294 !important; color: #FFF !important;
}
.stButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {
    background: #0F3369 !important; border-color: #0F3369 !important; color: #FFF !important;
}

/* Metric cards */
[data-testid="stMetric"] {
    background: #FFF; border: 1px solid #EBEBEB;
    border-radius: 8px; padding: 12px 16px;
}

/* Expanders */
[data-testid="stExpander"] {
    border: 1px solid #EBEBEB; border-radius: 8px; background: #FFF;
}

/* Divider */
hr { border-color: #EBEBEB; }

/* Chat input card — seamless textarea inside bordered container */
[data-testid="stBorderContainer"] {
    border-radius: 12px !important;
    background: #FAFAFA !important;
    border-color: #E0E0E0 !important;
    padding: 8px 12px 6px !important;
}
[data-testid="stBorderContainer"] textarea {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    resize: none !important;
    font-size: 13px !important;
}
[data-testid="stBorderContainer"] [data-testid="stTextArea"] > label { display: none; }
[data-testid="stBorderContainer"] [data-baseweb="select"] {
    background: transparent !important;
    border: none !important;
    font-size: 12px !important;
}
[data-testid="stBorderContainer"] [data-baseweb="select"] > div {
    background: transparent !important;
    border: none !important;
}

/* Sidebar buttons — compact card style for all secondary buttons */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
    text-align: left !important;
    justify-content: flex-start !important;
    background: #FFF !important;
    border: 1px solid #E4E4E4 !important;
    border-radius: 4px !important;
    color: #333 !important;
    font-size: 11px !important;
    padding: 0 6px !important;
    height: 28px !important;
    min-height: 28px !important;
    max-height: 28px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    line-height: 28px !important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
    color: #1A5294 !important;
    background: #F0F5FB !important;
}

/* Tighten column gaps and element spacing in sidebar */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
    gap: 2px !important;
    align-items: center !important;
}
[data-testid="stSidebar"] .stElementContainer {
    margin-bottom: 2px !important;
}

/* Toggle — blue when checked */
[data-testid="stToggle"] input[type="checkbox"]:checked ~ div,
[data-testid="stToggle"] input[type="checkbox"]:checked + div {
    background-color: #1A5294 !important;
    border-color: #1A5294 !important;
}
[data-testid="stToggle"] label:has(input:checked) > div {
    background-color: #1A5294 !important;
    border-color: #1A5294 !important;
}

/* Progress bar — blue */
[data-testid="stProgress"] [role="progressbar"] > div {
    background-color: #1A5294 !important;
}
</style>
"""


def run_app():
    st.set_page_config(
        page_title="AT-DJ",
        layout="wide",
        page_icon="🎶",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CSS, unsafe_allow_html=True)

    pages = [
        st.Page(page_main.show, title="DJ Console", icon="🎵", default=True, url_path="console"),
    ]
    st.navigation(pages).run()


# Removed 2026-04-29: this module-level call caused run_app() to fire on import,
# AND main.py also calls run_app(), so the page rendered TWICE per script run —
# producing intermittent StreamlitDuplicateElementKey errors on every keyed widget
# (sb_provider, new_session, etc.). main.py is the canonical entry point.
# run_app()
