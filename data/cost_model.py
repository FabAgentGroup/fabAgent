"""디스포지션 비용 모델 파라미터

실 fab에선 원가회계 + Yield Management System에서 산출되는 값
웨이퍼는 라인을 따라 누적 가공원가가 쌓이므로, 뒤 공정에서 폐기할수록 손실이 큼
hold(보류)/rework(재작업)/scrap(폐기)/continue(진행) 네 결정의 기대비용 산출에 사용

숫자는 300mm 라인 대표값 기반 예시이며, 절대값보다 결정 간 상대 트레이드오프가 핵심
"""

# 공정별 웨이퍼 누적 가치 (해당 step 통과 시점까지 쌓인 가공원가, USD)
WAFER_VALUE_BY_PROCESS = {
    "Photo": 3200.0,
    "Etch": 3800.0,
    "CMP": 4300.0,
    "Diffusion": 5000.0,
    "Implant": 5600.0,
}
DEFAULT_WAFER_VALUE = 4000.0

# 완성 웨이퍼 가치 (불량이 그대로 진행돼 최종 test에서 fail 시 잃는 값)
FINAL_WAFER_VALUE = 8200.0

# hold 비용: 보류 시 cycle-time 지연 + WIP carrying (웨이퍼당 일당) + 검사비
HOLD_COST_PER_WAFER_PER_DAY = 65.0
DEFAULT_HOLD_DAYS = 2.0
INSPECT_COST_PER_WAFER = 30.0

# rework 가능 공정 + 파라미터 (자원 제거형 공정은 비가역이라 rework 불가)
REWORK = {
    "Photo": {"cost_per_wafer": 250.0, "success_rate": 0.92},
    # Etch/CMP/Diffusion/Implant은 재작업 불가 (식각·연마·주입은 비가역)
}

# 불량 추정 확률(p_defect) 추정 시 가중
#   commonality 실측 fail_rate가 있으면 그대로 사용 (가장 신뢰)
#   없으면 tier1 score와 top cause 기여도로 근사
P_DEFECT_BAND = 0.15  # 추정 불확실성 폭 (신뢰구간 산출용)


def wafer_value(process: str) -> float:
    return WAFER_VALUE_BY_PROCESS.get(process, DEFAULT_WAFER_VALUE)


def rework_feasible(process: str) -> bool:
    return process in REWORK


def estimate_p_defect(
    tier1_score: float | None = None,
    top_cause_pct: int | None = None,
    commonality_fail_rate: float | None = None,
) -> float:
    """영향 웨이퍼가 실제 불량일 확률 추정 (0~1)

    우선순위: commonality 실측 fail_rate > tier1×cause 근사
    """
    if commonality_fail_rate is not None:
        return max(0.0, min(1.0, commonality_fail_rate))
    if tier1_score is None:
        return 0.5
    conf = (top_cause_pct or 50) / 100.0
    p = tier1_score * (0.5 + 0.5 * conf)
    return max(0.02, min(0.98, p))
