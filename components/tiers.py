"""Tier 1~4 순차 등장 렌더러 (개발 가이드 8·9장)

TODO(M1): 가이드 8장 '접근법 A', st.empty() placeholder 4개 + time.sleep으로
스켈레톤 -> 콘텐츠 순차 교체, stage>=5면 즉시 정적 렌더(새로고침 대응)

중요: Tier 데이터는 반드시 core.pipeline.get_tier_data() 한 함수로만 받음
data.demo.TIER_DATA 를 직접 import 하지 말 것, 실제 에이전트 교체가 막힘
"""
import streamlit as st

from core.pipeline import get_tier_data


def render_tier_cascade():
    data = get_tier_data(st.session_state.selected_alarm_id)
    if data is None:
        st.markdown(
            '<div class="fab-empty">선택한 알람의 분석 데이터가 없습니다.</div>',
            unsafe_allow_html=True,
        )
        return
    # TODO(M1) 가이드 8장 run_sequence(), 스켈레톤 -> 콘텐츠 순차 등장
    st.markdown("<!-- TODO(M1): Tier 1~4 cascade -->", unsafe_allow_html=True)


def render_tier(tier_num: int, data, loading: bool, with_actions: bool = False):
    # TODO(M1) 가이드 9장 render_tier(), Tier 프레임 + 본문/스켈레톤 분기
    raise NotImplementedError("M1: Tier 프레임 렌더러 구현 예정")
