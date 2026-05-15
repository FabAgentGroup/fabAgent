"""Tier 3 공정 간 영향 평가 에이전트 (M2에서 구현)

입력: 알람 컨텍스트 + Tier 1·2 결과
출력: core.schema.Tier3 (예상 수율 손실 + 공정 의존성 + 영향 lot)
모델: GPT-5 mini + tool use (후공정 의존성 그래프 조회 툴)
"""
from core.schema import Tier1, Tier2, Tier3


def run_impact(alarm: dict, tier1: Tier1, tier2: Tier2) -> Tier3:
    raise NotImplementedError("M2: Tier 3 영향 평가 에이전트 구현 예정")
