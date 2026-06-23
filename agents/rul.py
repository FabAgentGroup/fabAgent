"""RUL(잔여수명) 예측 엔진 - 반응형에서 예측형으로

지금까지 시스템은 이상이 '발생한 뒤' 탐지·분석했다(반응형). RUL 엔진은 소모품
마모 추세를 외삽해 '언제 한계에 도달할지'를 미리 알려 예측 기반 정비(PM)을 가능케 한다

방법: 최근 사용량 이력으로 lot당 열화율을 추정하고 수명한계까지 외삽
  RUL(lot) = (life_limit - 현재사용량) / 열화율
열화율의 분산으로 신뢰구간을 산출하고, worst 소모품이 장비 RUL을 결정한다

[설계 원칙] 결정론 추정(감사가능), LLM은 권고 문장만
"""
from data.phm2016.consumables import (
    CONSUMABLES,
    MRR_NOMINAL,
    MRR_SPEC_LOW,
    equipment_usage_snapshot,
)

CRITICAL_RUL_LOTS = 3
WATCH_RUL_LOTS = 7
MIN_HISTORY = 3


def _slope(history: list[float]) -> tuple[float, float]:
    """사용량 이력에서 lot당 증가율(중앙값)과 변동성(표준편차) 추정

    연속 차분의 중앙값을 robust 추정치로, 표준편차를 신뢰구간용으로 사용
    """
    diffs = [b - a for a, b in zip(history, history[1:]) if b >= a]
    if not diffs:
        return 1.0, 0.0
    diffs_sorted = sorted(diffs)
    n = len(diffs_sorted)
    median = diffs_sorted[n // 2] if n % 2 else (diffs_sorted[n // 2 - 1] + diffs_sorted[n // 2]) / 2
    mean = sum(diffs) / len(diffs)
    var = sum((d - mean) ** 2 for d in diffs) / len(diffs)
    return max(0.1, median), var ** 0.5


def predict_rul(consumable: str, usage_history: list[float]) -> dict:
    """소모품 사용량 이력으로 RUL(lot) 예측 + 신뢰구간

    반환: rul, rul_range[lo,hi], hi(health index), rate, current_usage, mrr_now, breach_in
    """
    c = CONSUMABLES[consumable]
    L = c["life_limit"]
    usage = usage_history[-1] if usage_history else 0.0
    remaining = max(0.0, L - usage)

    rate, rate_std = _slope(usage_history) if len(usage_history) >= 2 else (c["rate_per_lot"], 0.0)
    rul = remaining / rate
    # 신뢰구간: 열화율 ±1σ (빠르면 RUL 짧아짐)
    rate_hi = rate + rate_std
    rate_lo = max(0.1, rate - rate_std)
    rul_lo = remaining / rate_hi
    rul_hi = remaining / rate_lo

    hi = min(1.0, usage / L)
    mrr_now = round(MRR_NOMINAL * (1.0 - c["mrr_drop_pct"] * hi), 1)

    return {
        "consumable": consumable,
        "label": c["label"],
        "rul_lots": round(rul, 1),
        "rul_range_lots": [round(rul_lo, 1), round(rul_hi, 1)],
        "health_index": round(hi, 3),
        "rate_per_lot": round(rate, 1),
        "current_usage": round(usage, 1),
        "life_limit": L,
        "mrr_now": mrr_now,
        "mrr_spec_low": MRR_SPEC_LOW,
    }


def _status(rul: float, hi: float) -> str:
    if rul <= CRITICAL_RUL_LOTS or hi >= 0.9:
        return "critical"
    if rul <= WATCH_RUL_LOTS or hi >= 0.75:
        return "watch"
    return "healthy"


def assess(usage_histories: dict[str, list[float]]) -> dict:
    """소모품별 사용량 이력으로 장비 RUL 종합 평가

    worst(최소 RUL) 소모품이 장비 PM 시점을 결정한다
    """
    per = [predict_rul(c, h) for c, h in usage_histories.items() if c in CONSUMABLES]
    per.sort(key=lambda p: p["rul_lots"])
    driver = per[0] if per else None
    status = _status(driver["rul_lots"], driver["health_index"]) if driver else "healthy"
    return {
        "status": status,
        "driver": driver,            # 가장 먼저 한계 도달하는 소모품
        "consumables": per,          # RUL 오름차순
        "tool_rul_lots": driver["rul_lots"] if driver else None,
    }


def recommend_pm(assessment: dict, pm_windows: list[str], lots_per_day: float = 6.0) -> dict:
    """예측 기반 정비 권고 - 예측 breach 전에 PM 윈도우를 잡는다

    pm_windows: 가용 PM 윈도우 (가까운 순)
    lots_per_day: 일 처리 lot 수 (RUL lot을 일수로 환산)
    """
    driver = assessment.get("driver")
    if not driver:
        return {"action": "none", "reason": "평가할 소모품 이력 없음"}

    rul_lots = driver["rul_lots"]
    rul_days = rul_lots / max(0.1, lots_per_day)
    status = assessment["status"]

    if status == "healthy":
        action = "monitor"
        reason = f"{driver['label']} RUL {rul_lots:.0f}lot(약 {rul_days:.1f}일) 여유, 모니터링 유지"
    elif status == "watch":
        action = "schedule_pm"
        reason = (f"{driver['label']} RUL {rul_lots:.0f}lot(약 {rul_days:.1f}일), "
                  f"breach 전 PM 윈도우 확보 권고")
    else:
        action = "pm_now"
        reason = (f"{driver['label']} RUL {rul_lots:.0f}lot(약 {rul_days:.1f}일)로 임박, "
                  f"즉시 가용 윈도우에 PM 투입")

    window = pm_windows[0] if pm_windows else "(가용 윈도우 없음)"
    return {
        "action": action,
        "consumable": driver["label"],
        "rul_lots": rul_lots,
        "rul_days": round(rul_days, 1),
        "recommended_window": window,
        "reason": reason,
    }


def assess_equipment(equipment_id: str) -> dict:
    """장비 ID로 현재 소모품 스냅샷을 받아 RUL 평가 + 예측 기반 정비 권고

    PM 윈도우는 equipment 도구에서 조회한다. 알 수 없는 장비면 status=unknown
    """
    snapshot = equipment_usage_snapshot(equipment_id)
    if not snapshot:
        return {"equipment_id": equipment_id, "status": "unknown",
                "reason": "소모품 사용량 이력 없음 (CMP 장비만 지원)"}

    from agents.tools.equipment import check_pm_schedule

    a = assess(snapshot)
    windows = check_pm_schedule(equipment_id).get("available_windows", [])
    return {
        "equipment_id": equipment_id,
        "status": a["status"],
        "tool_rul_lots": a["tool_rul_lots"],
        "driver": a["driver"],
        "consumables": a["consumables"],
        "pm": recommend_pm(a, windows),
    }
