"""Tier 1~4 본문 렌더러 (개발 가이드 9·10장)

TODO(M1): 상호작용 없는 본문은 f-string HTML + st.markdown 한 번에 렌더
Streamlit 위젯을 본문에 쓰지 말 것(레이아웃 깨짐), Tier 4 액션 바만 st.button
디자인 프로토타입의 tiers.jsx 구조를 1:1로 옮길 것
"""
from core.schema import Tier1, Tier2, Tier3, Tier4


def render_tier_1_body(data: Tier1):
    raise NotImplementedError("M1: Tier 1 본문 구현 예정 (가이드 9장 참고)")


def render_tier_2_body(data: Tier2):
    raise NotImplementedError("M1: Tier 2 본문 구현 예정")


def render_tier_3_body(data: Tier3):
    raise NotImplementedError("M1: Tier 3 본문 구현 예정")


def render_tier_4_body(data: Tier4, with_actions: bool):
    # TODO(M1) 본문 HTML + with_actions면 거절/보류/승인 액션 바
    # 승인 시 on_approve, approved=True, 알람 status="done", st.toast, st.rerun
    raise NotImplementedError("M1: Tier 4 본문 + 액션 바 구현 예정 (가이드 10장)")
