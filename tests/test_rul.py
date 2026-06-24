"""예측형 RUL 회귀 테스트

소모품 마모 외삽(RUL = (한계 - 현재) / 열화율)의 수식 불변식과 신뢰구간,
worst-driver 선택, 상태/PM 권고 임계값을 검증한다
"""
from agents.rul import (
    CRITICAL_RUL_LOTS,
    WATCH_RUL_LOTS,
    assess,
    predict_rul,
    recommend_pm,
)
from data.phm2016.consumables import CONSUMABLES


def _linear_history(consumable, frac_start, step, n=4):
    L = CONSUMABLES[consumable]["life_limit"]
    return [L * frac_start + step * i for i in range(n)]


def test_rul_extrapolation_formula():
    # 일정 증가율이면 RUL = 남은수명 / 증가율
    c = "polishing_pad"
    L = CONSUMABLES[c]["life_limit"]
    step = 33.4
    hist = _linear_history(c, 0.5, step)
    r = predict_rul(c, hist)
    remaining = L - hist[-1]
    assert r["rul_lots"] == round(remaining / step, 1)


def test_health_index_in_unit_interval():
    for c in CONSUMABLES:
        r = predict_rul(c, _linear_history(c, 0.4, 10))
        assert 0.0 <= r["health_index"] <= 1.0


def test_confidence_interval_brackets_estimate():
    r = predict_rul("dresser", _linear_history("dresser", 0.3, 12))
    lo, hi = r["rul_range_lots"]
    assert lo <= r["rul_lots"] <= hi


def test_assess_driver_is_worst_consumable():
    # 가장 먼저 한계 도달하는(최소 RUL) 소모품이 driver
    histories = {c: _linear_history(c, 0.5, 8) for c in CONSUMABLES}
    a = assess(histories)
    ruls = [p["rul_lots"] for p in a["consumables"]]
    assert ruls == sorted(ruls)
    assert a["driver"]["rul_lots"] == min(ruls)
    assert a["tool_rul_lots"] == a["driver"]["rul_lots"]


def test_status_thresholds():
    # critical(<=3) / watch(<=7) / healthy 경계
    c = "polishing_pad"
    L = CONSUMABLES[c]["life_limit"]
    # 거의 소진 -> critical
    near = predict_rul(c, [L - 6, L - 4, L - 2])
    assert near["rul_lots"] <= CRITICAL_RUL_LOTS
    crit = assess({c: [L - 6, L - 4, L - 2]})
    assert crit["status"] == "critical"


def test_recommend_pm_action_per_status():
    histories = {c: _linear_history(c, 0.5, 8) for c in CONSUMABLES}
    a = assess(histories)
    rec = recommend_pm(a, ["2026-05-19 02:00"])
    assert rec["action"] in ("monitor", "schedule_pm", "pm_now")
    assert rec["recommended_window"] == "2026-05-19 02:00"


def test_recommend_pm_no_driver():
    rec = recommend_pm({"driver": None}, [])
    assert rec["action"] == "none"


def test_constants_sane():
    assert CRITICAL_RUL_LOTS < WATCH_RUL_LOTS


def test_determinism():
    h = _linear_history("membrane", 0.4, 9)
    assert predict_rul("membrane", h) == predict_rul("membrane", h)
