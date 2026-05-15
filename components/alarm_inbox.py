"""사이드바 알람 인박스 (개발 가이드 6장)

TODO(M1): 가이드 6장 '권장 대안', HTML 카드 + 바로 아래 st.button 분리 방식
on_alarm_click()에서 stage / completed_tiers / approved 리셋 후
animation_pending=True 로 두고 st.rerun()
"""
import streamlit as st


def render_alarm_inbox():
    with st.sidebar:
        # TODO(M1) st.session_state.alarms 순회하며 알람 카드 + 선택 버튼 렌더
        st.markdown("<!-- TODO(M1): 알람 인박스 -->", unsafe_allow_html=True)
