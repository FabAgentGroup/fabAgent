"""Tier 1 이상 탐지 에이전트 (M2에서 구현)

입력: 알람 컨텍스트 + SECOM 센서 데이터 (data.secom.loader.load_secom)
출력: core.schema.Tier1 (이상 점수 + 기여 피처 Top-N + 영향 lot)
모델: GPT-5 mini + tool use, IsolationForest 등으로 이상 점수 계산
"""
from core.schema import Tier1


def run_detection(alarm: dict) -> Tier1:
    raise NotImplementedError("M2: Tier 1 이상 탐지 에이전트 구현 예정")
