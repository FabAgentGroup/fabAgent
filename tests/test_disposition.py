"""리스크 정량 디스포지션 회귀 테스트

기대비용 계산은 전적으로 결정론(감사가능)이어야 한다 - 비용 공식 불변식과
추천 로직(최소비용 선택), 신뢰구간 robust 판정을 검증한다
"""
import pytest

from agents.disposition import compute_disposition, expected_costs
from data.cost_model import FINAL_WAFER_VALUE, rework_feasible, wafer_value


def test_scrap_cost_is_n_times_wafer_value():
    # 폐기 = 전량 현 가치 손실, p와 무관
    n = 50
    costs = expected_costs("CMP", n, 0.3)
    assert costs["scrap"] == n * wafer_value("CMP")


def test_continue_cost_is_n_p_final_value():
    n, p = 40, 0.2
    costs = expected_costs("CMP", n, p)
    assert costs["continue"] == pytest.approx(n * p * FINAL_WAFER_VALUE)


def test_continue_cost_monotonic_in_p():
    lo = expected_costs("CMP", 50, 0.1)["continue"]
    hi = expected_costs("CMP", 50, 0.6)["continue"]
    assert hi > lo


def test_rework_option_only_when_feasible():
    for process in ("CMP", "Photo", "Etch"):
        opts = {o["action"] for o in compute_disposition(process, 30, 0.4)["options"]}
        assert ("rework" in opts) == rework_feasible(process)


def test_recommended_is_min_cost_option():
    d = compute_disposition("CMP", 60, 0.5)
    costs = [o["expected_cost_usd"] for o in d["options"]]
    assert costs == sorted(costs)  # 오름차순 정렬
    assert d["recommended"] == d["options"][0]["action"]


def test_savings_vs_worst_nonnegative():
    d = compute_disposition("Etch", 100, 0.45)
    assert d["savings_vs_worst_usd"] >= 0


def test_confidence_within_unit_interval():
    d = compute_disposition("CMP", 50, 0.5)
    assert 0.0 <= d["confidence"] <= 1.0


def test_robust_flag_consistency():
    # robust면 band 양끝에서도 추천 동일
    d = compute_disposition("CMP", 50, 0.05, p_band=0.1)
    if d["robust"]:
        lo = compute_disposition("CMP", 50, max(0.0, 0.05 - 0.1))["recommended"]
        hi = compute_disposition("CMP", 50, 0.05 + 0.1)["recommended"]
        assert lo == hi == d["recommended"]


def test_input_clamping():
    # p_defect는 [0,1], n_wafers는 최소 1로 클램프
    d = compute_disposition("CMP", 0, 1.5)
    assert d["inputs"]["n_wafers"] == 1
    assert d["inputs"]["p_defect"] == 1.0


def test_determinism():
    assert compute_disposition("CMP", 50, 0.3) == compute_disposition("CMP", 50, 0.3)
