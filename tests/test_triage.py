"""Tier 0 트리아지 회귀 테스트

D12에서 공표한 압축 성능(397->3, 132.3x, nuisance 354 억제)을 회귀 앵커로 잠그고,
랭킹·점수 분해의 결정론 불변식을 검증한다
"""
import pytest

from agents.triage import triage


# D12 공표값 (experiments/triage_eval/results.md) - 변하면 회귀로 검토
def test_d12_compression_anchor(triage_result):
    assert triage_result["n_total"] == 397
    assert triage_result["n_incidents"] == 3
    assert triage_result["n_suppressed"] == 354
    assert triage_result["compression_ratio"] == 132.3


def test_nuisance_suppression_rate(triage_result):
    # nuisance 억제율 89% (354/397) - 알람 피로 해소의 핵심 지표
    rate = triage_result["n_suppressed"] / triage_result["n_total"]
    assert rate > 0.85


def test_clustered_plus_suppressed_covers_all(triage_result):
    assert triage_result["n_clustered"] + triage_result["n_suppressed"] == triage_result["n_total"]


def test_incidents_ranked_by_risk_desc(incidents):
    scores = [i["risk_score"] for i in incidents]
    assert scores == sorted(scores, reverse=True)


def test_ranks_are_contiguous(incidents):
    assert [i["rank"] for i in incidents] == list(range(1, len(incidents) + 1))


def test_risk_score_matches_breakdown(incidents):
    # risk = 100*(0.55*severity + 0.30*spread + 0.15*confidence) - 감사 가능성 보장
    # breakdown은 3자리 반올림 저장이라 재계산 시 ±0.1 오차 허용
    for inc in incidents:
        b = inc["score_breakdown"]
        expected = 100.0 * (0.55 * b["severity"] + 0.30 * b["spread"] + 0.15 * b["confidence"])
        assert inc["risk_score"] == pytest.approx(expected, abs=0.2)


def test_incident_required_fields(incidents):
    required = {
        "incident_id", "process", "param", "kind", "dominant_tool",
        "dominant_recipe", "dominant_chamber", "n_alarms", "max_sigma",
        "risk_score", "confidence", "alarm_ids",
    }
    for inc in incidents:
        assert required <= inc.keys()
        assert inc["n_alarms"] == len(inc["alarm_ids"])
        assert 0.0 <= inc["confidence"] <= 1.0
        assert inc["kind"] in ("tool", "systemic")


def test_determinism(alarms):
    # seed 고정 결정론 - 두 번 돌려 완전 동일
    a = triage(alarms)
    b = triage(alarms)
    assert a == b


def test_top_incident_is_cmp_chamber_excursion(incidents):
    # 최상위 incident는 planted CMP MRR excursion (risk 최고)
    top = incidents[0]
    assert top["incident_id"] == "TRIAGE-0001"
    assert top["process"] == "CMP"
    assert top["param"] == "MRR"
    assert top["dominant_tool"] == "AMAT-CMP-02"
