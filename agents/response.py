"""Tier 4 대응 권고 에이전트 (M2에서 구현)

입력: 알람 컨텍스트 + Tier 1·2·3 결과
출력: core.schema.Tier4 (즉시 조치 + 중장기 조치 + 근거 자료)
모델: GPT-5 (오케스트레이터급) + RAG, SOP/표준 절차 문서 검색
"""
from core.schema import Tier1, Tier2, Tier3, Tier4


def run_response(alarm: dict, tier1: Tier1, tier2: Tier2, tier3: Tier3) -> Tier4:
    raise NotImplementedError("M2: Tier 4 대응 권고 에이전트 구현 예정")
