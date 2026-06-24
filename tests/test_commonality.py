"""커몬낼리티 엔진 회귀 테스트

D12 핵심 주장(root-cause hit@1 3/3)을 잠근다 - 각 incident의 top 용의자가
synth_scenario에 심어둔 정답 엔티티(차원·값)와 일치해야 한다
"""
import pytest

from agents.commonality import (
    _chi2_p,
    analyze_commonality,
    commonality_for_incident,
    scope_for_incident,
)

# 트리아지 incident -> planted root_cause (process+param로 식별)
EXPECTED_ROOT_CAUSE = {
    ("CMP", "MRR"): ("chamber", "AMAT-CMP-02::C"),
    ("CMP", "제거 균일도"): ("slurry_lot", "SL-BAD-2264"),
    ("Photo", "Focus 편차"): ("tool", "ASML-PH-01"),
}


def test_root_cause_hit_at_1(incidents):
    # D12: hit@1 3/3 - 모든 incident의 top 용의자가 정답과 일치
    hits = 0
    for inc in incidents:
        comm = commonality_for_incident(inc)
        assert comm["suspects"], f"{inc['incident_id']} 용의자 없음"
        top = comm["suspects"][0]
        expected = EXPECTED_ROOT_CAUSE[(inc["process"], inc["param"])]
        if (top["dim"], top["value"]) == expected:
            hits += 1
    assert hits == 3


def test_suspects_sorted_by_chi2_desc(incidents):
    # 유의성(χ²) 우선 랭킹 - 소표본 우연을 과대평가하지 않음
    for inc in incidents:
        comm = commonality_for_incident(inc)
        chi2s = [s["chi2"] for s in comm["suspects"]]
        assert chi2s == sorted(chi2s, reverse=True)


def test_all_suspects_above_lift_threshold(incidents):
    for inc in incidents:
        comm = commonality_for_incident(inc)
        for s in comm["suspects"]:
            assert s["lift"] >= 1.3  # MIN_LIFT
            assert s["entity_total"] >= 6  # MIN_SUPPORT


def test_scope_kind_routing(incidents):
    # systemic은 recipe로만, tool-localized는 tool+recipe로 좁힘
    for inc in incidents:
        scope = scope_for_incident(inc)
        if inc["kind"] == "systemic":
            assert "scope_tool" not in scope
            assert scope.get("scope_recipe")
        else:
            assert scope.get("scope_tool")


def test_chi2_independent_table_high_p():
    # 완전 독립 분할표 - χ²≈0, p≈1
    chi2, p = _chi2_p(25, 25, 25, 25)
    assert chi2 == pytest.approx(0.0, abs=1e-9)
    assert p == pytest.approx(1.0, abs=1e-9)


def test_chi2_strong_association_low_p():
    # 강한 연관 - p가 매우 작아야 함
    chi2, p = _chi2_p(40, 2, 3, 45)
    assert chi2 > 10
    assert p < 0.01


def test_chi2_degenerate_table_safe():
    # 0 분모 방어
    chi2, p = _chi2_p(0, 0, 0, 0)
    assert chi2 == 0.0 and p == 1.0


def test_empty_population_returns_no_suspects():
    res = analyze_commonality("CMP", scope_tool="NON-EXISTENT-TOOL")
    assert res["suspects"] == []


def test_determinism(incidents):
    for inc in incidents:
        assert commonality_for_incident(inc) == commonality_for_incident(inc)
