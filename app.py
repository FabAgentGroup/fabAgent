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
    page_title="FabAgent - 운영자 대시보드",
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


def handle_query_params():
    # 사이드바 FabAgent 로고 클릭 -> ?reset=1로 진입 -> 세션 초기화
    if "reset" in st.query_params:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        del st.query_params["reset"]
        return

    # 알람 카드 클릭 -> ?alarm=X로 진입 -> 선택 알람 변경
    if "alarm" in st.query_params:
        alarm_id = st.query_params["alarm"]
        ss = st.session_state
        if alarm_id != ss.get("selected_alarm_id"):
            ss.selected_alarm_id = alarm_id
            ss.stage = 0
            ss.completed_tiers = set()
            ss.approved = False
            ss.animation_pending = True
        del st.query_params["alarm"]


def init_state():
    ss = st.session_state
    ss.setdefault("selected_alarm_id", "A1")
    ss.setdefault("stage", 0)  # 0=idle, 1..4=loading, 5=done
    ss.setdefault("completed_tiers", set())
    ss.setdefault("approved", False)
    ss.setdefault("alarms", [a.copy() for a in DEFAULT_ALARMS])
    ss.setdefault("animation_pending", False)
    ss.setdefault("speed", "normal")  # "fast" | "normal" | "real"


def _current_alarm():
    ss = st.session_state
    for a in ss.alarms:
        if a["id"] == ss.selected_alarm_id:
            return a
    return None


def render_main():
    render_header()

    alarm = _current_alarm()
    title_text = alarm["title"] if alarm else "알람을 선택하세요"
    lot_id = alarm["lot_id"] if alarm else "-"

    col_title, col_progress = st.columns([5, 4])
    with col_title:
        st.markdown(
            f"""
            <h1 class="fab-main-title">
              {title_text} - <span style="font-family:var(--mono); font-weight:700;">{lot_id}</span>
            </h1>
            <div class="fab-main-sub">
              <span>4-Tier 분석 워크플로우</span>
              <span class="sep">·</span>
              <span>이상 탐지 → 원인 분석 → 영향 평가 → 대응 권고</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_progress:
        render_progress_strip()

    st.markdown(
        '<hr style="border-color: var(--border); margin: 16px 0 22px;"/>',
        unsafe_allow_html=True,
    )
    render_tier_cascade()


inject_css()
handle_query_params()
init_state()
render_alarm_inbox()
render_main()
