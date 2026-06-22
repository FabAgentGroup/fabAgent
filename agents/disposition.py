"""리스크 정량 디스포지션 엔진 (Tier 4 의사결정)

영향 WIP를 어떻게 처리할지(진행/보류/재작업/폐기)를 기대비용으로 정량 비교한다
현장에서 가장 고가이고 압박이 큰 결정을, 불확실성(p_defect 신뢰구간)까지 반영해
"수치상 이게 최소 비용"으로 추천한다

[설계 원칙] 비용 계산은 전적으로 결정론(감사가능)
모든 입력(웨이퍼 가치·불량확률·hold일수)과 항을 노출하고, LLM은 권고 문장만 생성
커몬낼리티 실측 fail_rate가 있으면 p_defect로 직접 사용해 추정 오차를 줄인다

기대비용 (영향 n장, 현 공정 가치 V, 완성 가치 F):
- 진행(continue): n·p·F        불량이 그대로 진행돼 최종 test에서 fail
- 보류(hold):     n·(hold일비+검사비) + n·p·V   검사 후 진짜 불량만 현 가치로 폐기
- 재작업(rework): n·rework비 + n·(1-성공률)·V   (가역 공정만)
- 폐기(scrap):    n·V           전량 현 가치로 손실
"""
from data.cost_model import (
    DEFAULT_HOLD_DAYS,
    FINAL_WAFER_VALUE,
    HOLD_COST_PER_WAFER_PER_DAY,
    INSPECT_COST_PER_WAFER,
    P_DEFECT_BAND,
    REWORK,
    estimate_p_defect,
    rework_feasible,
    wafer_value,
)

_LABELS = {
    "continue": "진행 (as-is 출하)",
    "hold": "보류 (검사 후 선별 폐기)",
    "rework": "재작업",
    "scrap": "전량 폐기",
}


def _costs_at(process: str, n: int, p: float) -> dict:
    v = wafer_value(process)
    costs = {
        "continue": n * p * FINAL_WAFER_VALUE,
        "hold": n * (HOLD_COST_PER_WAFER_PER_DAY * DEFAULT_HOLD_DAYS + INSPECT_COST_PER_WAFER) + n * p * v,
        "scrap": n * v,
    }
    if rework_feasible(process):
        rw = REWORK[process]
        costs["rework"] = n * rw["cost_per_wafer"] + n * (1 - rw["success_rate"]) * v
    return costs


def expected_costs(process: str, n_wafers: int, p_defect: float) -> dict:
    """공정·영향수·불량확률로 각 디스포지션의 기대비용 (평가·검증용 공개 헬퍼)"""
    return _costs_at(process, max(1, int(n_wafers)), max(0.0, min(1.0, p_defect)))


def _rationale(action: str, process: str, n: int, p: float) -> str:
    v = wafer_value(process)
    if action == "continue":
        return f"불량확률 {p:.0%}로 낮아 진행 시 기대손실(최종 fail)이 보류·폐기보다 작음"
    if action == "hold":
        return f"검사로 진짜 불량({p:.0%})만 선별 폐기하면 전량 폐기·진행보다 손실 최소"
    if action == "rework":
        rw = REWORK[process]
        return f"가역 공정({process})이라 웨이퍼당 ${rw['cost_per_wafer']:.0f}·성공률 {rw['success_rate']:.0%}로 폐기보다 저렴"
    return f"불량확률 {p:.0%}로 높아 진행 시 손실이 현 가치(${v:.0f}/장) 폐기를 초과"


def compute_disposition(
    process: str,
    n_wafers: int,
    p_defect: float,
    p_band: float = P_DEFECT_BAND,
) -> dict:
    """영향 WIP 디스포지션을 기대비용으로 추천

    p_band: p_defect 불확실성 폭. 추천이 [p-band, p+band]에서 유지되면 robust=True
    """
    n = max(1, int(n_wafers))
    p = max(0.0, min(1.0, p_defect))
    p_lo = max(0.0, p - p_band)
    p_hi = min(1.0, p + p_band)

    base = _costs_at(process, n, p)
    lo = _costs_at(process, n, p_lo)
    hi = _costs_at(process, n, p_hi)

    options = []
    for action, cost in base.items():
        options.append({
            "action": action,
            "label": _LABELS[action],
            "expected_cost_usd": round(cost),
            "cost_range_usd": [round(min(lo[action], hi[action])), round(max(lo[action], hi[action]))],
            "rationale": _rationale(action, process, n, p),
            "feasible": True,
        })
    options.sort(key=lambda o: o["expected_cost_usd"])

    recommended = options[0]["action"]
    rec_lo = min(lo, key=lo.get)
    rec_hi = min(hi, key=hi.get)
    robust = recommended == rec_lo == rec_hi

    worst = options[-1]["expected_cost_usd"]
    best = options[0]["expected_cost_usd"]
    second = options[1]["expected_cost_usd"] if len(options) > 1 else worst
    # 신뢰도: band 내 추천 유지 + 2순위와의 상대 격차
    margin = (second - best) / second if second else 0.0
    confidence = round((0.7 if robust else 0.4) + 0.3 * min(1.0, margin / 0.3), 2)

    return {
        "recommended": recommended,
        "recommended_label": _LABELS[recommended],
        "options": options,
        "savings_vs_worst_usd": round(worst - best),
        "confidence": min(1.0, confidence),
        "robust": robust,
        "inputs": {
            "process": process,
            "n_wafers": n,
            "p_defect": round(p, 3),
            "p_band": p_band,
            "wafer_value_usd": wafer_value(process),
            "final_wafer_value_usd": FINAL_WAFER_VALUE,
            "hold_days": DEFAULT_HOLD_DAYS,
        },
    }


def _n_wafers_from_tier(tier1: dict, tier3: dict) -> int:
    impact = sum(l.get("wafers", 0) for l in tier3.get("impact_lots", []))
    own = tier1.get("lot", {}).get("wafers", 0)
    return impact + own or own or 25


def disposition_for_tier(alarm: dict, tier1: dict, tier2: dict, tier3: dict) -> dict:
    """4-Tier 분석 결과로 디스포지션 산출 (오케스트레이터 response 단계용)"""
    process = alarm["title"].split()[0]
    top_pct = max((c.get("pct", 0) for c in tier2.get("causes", [])), default=50)
    p = estimate_p_defect(tier1_score=tier1.get("score"), top_cause_pct=top_pct)
    n = _n_wafers_from_tier(tier1, tier3)
    return compute_disposition(process, n, p)


def disposition_for_incident(incident: dict, commonality: dict, n_wafers: int | None = None) -> dict:
    """트리아지 incident + 커몬낼리티로 디스포지션 산출

    커몬낼리티 top 용의자의 실측 entity_fail_rate를 p_defect로 사용
    """
    suspects = commonality.get("suspects", [])
    fail_rate = suspects[0]["entity_fail_rate"] if suspects else None
    p = estimate_p_defect(commonality_fail_rate=fail_rate)
    n = n_wafers if n_wafers is not None else incident["n_alarms"] * 5
    return compute_disposition(incident["process"], n, p)
