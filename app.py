"""FabAgent 운영자 대시보드 엔트리포인트

실행: streamlit run app.py --server.port 8501
"""
from pathlib import Path

import streamlit as st

from components.alarm_inbox import render_alarm_inbox
from components.header import render_header
from components.progress import render_progress_strip
from components.tiers import render_tier_cascade
from data.demo import DEFAULT_ALARMS

st.set_page_config(
    page_title="FabAgent — 운영자 대시보드",
    page_icon="🟦",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css():
    css_path = Path("styles/main.css")
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )
    st.markdown(
        '<link rel="stylesheet" '
        'href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">',
        unsafe_allow_html=True,
    )


def init_state():
    ss = st.session_state
    ss.setdefault("selected_alarm_id", "A1")
    ss.setdefault("stage", 0)  # 0=idle, 1..4=loading, 5=done
    ss.setdefault("completed_tiers", set())
    ss.setdefault("approved", False)
    ss.setdefault("alarms", [a.copy() for a in DEFAULT_ALARMS])
    ss.setdefault("animation_pending", False)
    ss.setdefault("speed", "normal")  # "fast" | "normal" | "real"


def render_main():
    render_header()

    col_title, col_progress = st.columns([5, 4])
    with col_title:
        # TODO(M1) 메인 타이틀 + 4-Tier 워크플로우 서브텍스트
        st.markdown("<!-- TODO(M1): 메인 타이틀 -->", unsafe_allow_html=True)
    with col_progress:
        render_progress_strip()

    st.markdown(
        '<hr style="border-color: var(--border); margin: 16px 0 22px;"/>',
        unsafe_allow_html=True,
    )
    render_tier_cascade()


inject_css()
init_state()
render_alarm_inbox()
render_main()
