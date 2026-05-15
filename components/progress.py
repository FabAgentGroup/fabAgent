"""4단계 진행 스트립 (개발 가이드 부록 C)

TODO(M1): 가이드 부록 C의 render_progress_strip() 구현
st.session_state.stage 기준으로 각 단계를 idle / active / done 으로 렌더
"""
import streamlit as st


def render_progress_strip():
    # TODO(M1) 이상 탐지 -> 원인 분석 -> 영향 평가 -> 권고서 진행 표시
    st.markdown("<!-- TODO(M1): 진행 스트립 -->", unsafe_allow_html=True)
