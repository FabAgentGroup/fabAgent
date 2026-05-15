"""Tier 2 원인 분석 에이전트 (M2에서 구현)

입력: 알람 컨텍스트 + Tier 1 결과
출력: core.schema.Tier2 (추정 원인 + 기여도 % + 근거 + RAG citation)
모델: GPT-5 mini + RAG (agents.rag.store), 과거 인시던트/FMEA 문서 검색
"""
from core.schema import Tier1, Tier2


def run_cause(alarm: dict, tier1: Tier1) -> Tier2:
    raise NotImplementedError("M2: Tier 2 원인 분석 에이전트 구현 예정")
