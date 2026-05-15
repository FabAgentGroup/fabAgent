"""상단 헤더 (개발 가이드 부록 A)

TODO(M1): 가이드 부록 A의 render_header() 구현, 디자인 시안 헤더와 1:1
헤더는 st.columns 밖, .block-container 최상단에 둠
"""
import streamlit as st


def render_header():
    # TODO(M1) 로고 + 공정/라인 컨텍스트 + LIVE 시계 + 사용자 영역
    st.markdown("<!-- TODO(M1): FabAgent 헤더 -->", unsafe_allow_html=True)
