"""FabAgent 운영자 대시보드 엔트리포인트

실행: streamlit run app.py --server.port 8501
"""
from pathlib import Path

import streamlit as st

from components.alarm_inbox import render_alarm_inbox
from components.header import render_header
from components.progress import render_progress_strip
from components.tiers import render_tier_cascade
from components.audit_board import render_audit_board
from components.maintenance_board import render_maintenance_board
from components.triage_board import render_triage_board
from data.demo import DEFAULT_ALARMS

st.set_page_config(
    page_title="FabAgent - 운영자 대시보드",
    page_icon="assets/favicon.png",
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

    # 뷰 전환 -> ?view=triage|analysis
    if "view" in st.query_params:
        st.session_state.view = st.query_params["view"]
        del st.query_params["view"]

    # incident 카드 클릭 -> ?incident=ID -> 트리아지 뷰에서 선택 incident 변경
    if "incident" in st.query_params:
        st.session_state.selected_incident_id = st.query_params["incident"]
        st.session_state.view = "triage"
        del st.query_params["incident"]

    # 알람 카드 클릭 -> ?alarm=X로 진입 -> 선택 알람 변경 + 심층 분석 뷰로
    if "alarm" in st.query_params:
        alarm_id = st.query_params["alarm"]
        ss = st.session_state
        ss.view = "analysis"
        if alarm_id != ss.get("selected_alarm_id"):
            ss.selected_alarm_id = alarm_id
            ss.stage = 0
            ss.completed_tiers = set()
            ss.approved = False
            ss.animation_pending = True
            ss.last_action = None
        del st.query_params["alarm"]


def init_state():
    ss = st.session_state
    ss.setdefault("view", "triage")  # "triage" | "analysis"
    ss.setdefault("selected_incident_id", None)
    ss.setdefault("selected_alarm_id", "A1")
    ss.setdefault("stage", 0)  # 0=idle, 1..4=loading, 5=done
    ss.setdefault("completed_tiers", set())
    ss.setdefault("approved", False)
    ss.setdefault("alarms", [a.copy() for a in DEFAULT_ALARMS])
    ss.setdefault("animation_pending", False)
    ss.setdefault("speed", "normal")  # "fast" | "normal" | "real"
    ss.setdefault("last_action", None)  # 운영자 결정 결과 (approved/held/rejected)


def _current_alarm():
    ss = st.session_state
    for a in ss.alarms:
        if a["id"] == ss.selected_alarm_id:
            return a
    return None


def render_nav():
    ss = st.session_state
    t_active = "active" if ss.view == "triage" else ""
    a_active = "active" if ss.view == "analysis" else ""
    m_active = "active" if ss.view == "maintenance" else ""
    g_active = "active" if ss.view == "audit" else ""
    st.html(
        '<style>'
        '.fab-nav { display:flex; gap:8px; margin: 2px 0 14px; }'
        '.fab-nav a { text-decoration:none; font-size:13px; font-weight:700; padding:6px 14px;'
        ' border-radius:8px; border:1px solid var(--border); color:var(--text-secondary);'
        ' background:var(--bg-card); }'
        '.fab-nav a.active { background:var(--t1-bg); color:var(--t1-text); border-color:var(--t1-border); }'
        '</style>'
        '<div class="fab-nav">'
        f'<a href="?view=triage" target="_self" class="{t_active}">Tier 0 트리아지</a>'
        f'<a href="?view=analysis" target="_self" class="{a_active}">심층 분석 (4-Tier)</a>'
        f'<a href="?view=maintenance" target="_self" class="{m_active}">예지보전</a>'
        f'<a href="?view=audit" target="_self" class="{g_active}">감사 로그</a>'
        '</div>'
    )


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
render_nav()
if st.session_state.view == "triage":
    render_triage_board()
elif st.session_state.view == "maintenance":
    render_maintenance_board()
elif st.session_state.view == "audit":
    render_audit_board()
else:
    render_main()
