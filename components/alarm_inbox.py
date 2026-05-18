"""사이드바 알람 인박스 (개발 가이드 6장)

HTML 카드 + 바로 아래 작은 선택 버튼 분리 방식 (가이드 권장안)
on_alarm_click()에서 stage/completed_tiers/approved 리셋 후
animation_pending=True로 두고 st.rerun()
"""
import streamlit as st

from data.demo import STATUS_LABELS


def render_alarm_inbox():
    ss = st.session_state
    with st.sidebar:
        _render_logo()

        critical_count = sum(1 for a in ss.alarms if a["status"] == "critical")
        total = len(ss.alarms)
        badge = f'<span class="badge">긴급 {critical_count}</span>' if critical_count else ""
        st.html(
            f'<div class="fab-sidebar-head">'
            f'<div class="fab-sidebar-title">알람 인박스</div>'
            f'<div class="fab-sidebar-count">{badge}<span>전체 {total}건</span></div>'
            f'</div>'
        )

        for alarm in ss.alarms:
            _render_alarm_card(alarm)


def _render_logo():
    # 클릭 시 ?reset=1 쿼리로 진입 -> app.maybe_handle_home이 세션 초기화
    st.markdown(
        """
        <a href="?reset=1" class="fab-sidebar-logo-link" target="_self">
          <div class="fab-sidebar-logo">
            <div class="fab-logo-mark">
              <svg width="16" height="16" viewBox="0 0 160 160" fill="none">
                <circle cx="80" cy="80" r="60" stroke="#fff" stroke-width="10"/>
                <path d="M70 22 L90 22 L86 32 L74 32 Z" fill="#fff"/>
                <rect x="46" y="58" width="68" height="8" rx="4" fill="#fff"/>
                <rect x="46" y="76" width="52" height="8" rx="4" fill="#fff" opacity="0.7"/>
                <rect x="46" y="94" width="36" height="8" rx="4" fill="#fff" opacity="0.4"/>
              </svg>
            </div>
            <span>FabAgent</span>
          </div>
        </a>
        """,
        unsafe_allow_html=True,
    )


def _render_alarm_card(alarm):
    ss = st.session_state
    is_selected = alarm["id"] == ss.selected_alarm_id
    is_done = alarm["status"] == "done"

    classes = f'alarm-card {alarm["status"]}'
    if is_selected:
        classes += " selected"
    if is_done:
        classes += " completed"

    selected_tag = '<span class="alarm-selected-tag">★ 선택됨</span>' if is_selected else ""
    feat_html = ""
    if alarm.get("feature"):
        arrow = alarm.get("feature_arrow") or ""
        feat_html = (
            f'<span class="feat">{alarm["feature"]} '
            f'<span class="alarm-feat-arrow">{arrow}</span></span>'
        )

    # 카드 전체를 클릭 영역으로, ?alarm=X 쿼리로 진입하면 app.handle_query_params가 처리
    # markdown 파서가 <a> 안의 <div>를 reparse하는 문제를 피하려고 st.html 사용
    st.html(
        f'<a href="?alarm={alarm["id"]}" class="alarm-card-link" target="_self">'
        f'<div class="{classes}">'
        f'<div class="alarm-head">'
        f'<span class="chip chip-{alarm["status"]}"><span class="dot"></span>{STATUS_LABELS[alarm["status"]]}</span>'
        f'{selected_tag}'
        f'</div>'
        f'<div class="alarm-title">{alarm["title"]}</div>'
        f'<div class="alarm-meta">'
        f'<span style="font-family: var(--mono); font-size: 11px;">{alarm["lot_id"]}</span>'
        f'{feat_html}'
        f'</div>'
        f'<div class="alarm-time">{alarm["time"]}</div>'
        f'</div>'
        f'</a>'
    )
