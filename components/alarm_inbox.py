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
        critical_count = sum(1 for a in ss.alarms if a["status"] == "critical")
        total = len(ss.alarms)
        badge = f'<span class="badge">긴급 {critical_count}</span>' if critical_count else ""
        st.markdown(
            f"""
            <div class="fab-sidebar-head">
              <div class="fab-sidebar-title">알람 인박스</div>
              <div class="fab-sidebar-count">
                {badge}
                <span>전체 {total}건</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for alarm in ss.alarms:
            _render_alarm_card(alarm)


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

    st.markdown(
        f"""
        <div class="{classes}">
          <div class="alarm-head">
            <span class="chip chip-{alarm['status']}">
              <span class="dot"></span>{STATUS_LABELS[alarm['status']]}
            </span>
            {selected_tag}
          </div>
          <div class="alarm-title">{alarm['title']}</div>
          <div class="alarm-meta">
            <span style="font-family: var(--mono); font-size: 11px;">{alarm['lot_id']}</span>
            {feat_html}
          </div>
          <div class="alarm-time">{alarm['time']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("이 알람 분석", key=f"sel-{alarm['id']}", use_container_width=True):
        _on_alarm_click(alarm["id"])


def _on_alarm_click(alarm_id: str):
    ss = st.session_state
    if alarm_id == ss.selected_alarm_id:
        return
    ss.selected_alarm_id = alarm_id
    ss.stage = 0
    ss.completed_tiers = set()
    ss.approved = False
    ss.animation_pending = True
    st.rerun()
