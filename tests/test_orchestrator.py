"""오케스트레이터 회귀 테스트

LLM/RAG를 타지 않는 순수 라우팅·핸드오프 헬퍼를 검증한다
무거운 end-to-end(로컬 ML+RAG 로딩)는 slow 마커로 분리해 기본 수트를 빠르게 유지한다
"""
import pytest

from agents.orchestrator import (
    SEVERITY_THRESHOLD,
    _incident_to_alarm,
    _incident_to_tier1,
    _incident_wafers,
    _incident_wip,
    _node_noise,
    _route_after_detect,
)
from core.pipeline import REAL_AGENT_ALARMS, get_tier_data


def test_severity_gate_routes_high_score_to_go():
    state = {"tier1": {"score": SEVERITY_THRESHOLD + 0.1}}
    assert _route_after_detect(state) == "go"


def test_severity_gate_suppresses_low_score():
    state = {"tier1": {"score": SEVERITY_THRESHOLD - 0.01}}
    assert _route_after_detect(state) == "noise"


def test_noise_node_zeroes_all_tiers():
    out = _node_noise({})
    assert out["skipped"] is True
    assert out["tier2"]["causes"] == []
    assert out["tier3"]["yield_loss"] == 0.0
    assert out["tier4"]["immediate"] == []


def test_incident_to_alarm_carries_scope_and_severity(incidents):
    inc = incidents[0]  # risk 90.7 -> critical
    alarm = _incident_to_alarm(inc)
    assert alarm["id"] == inc["incident_id"]
    assert alarm["status"] in ("critical", "warn")
    assert alarm["equipment_id"] == inc["dominant_tool"]
    assert "_commonality_scope" in alarm


def test_incident_to_alarm_critical_threshold(incidents):
    for inc in incidents:
        alarm = _incident_to_alarm(inc)
        assert alarm["status"] == ("critical" if inc["risk_score"] >= 80 else "warn")


def test_incident_to_tier1_score_normalized(incidents):
    from agents.commonality import commonality_for_incident

    inc = incidents[0]
    t1 = _incident_to_tier1(inc, commonality_for_incident(inc))
    assert 0.0 <= t1["score"] <= 1.0
    assert t1["features"]  # 최소 1개 기여 피처
    assert len(t1["features"]) <= 3
    assert t1["lot"]["wafers"] == _incident_wafers(inc)


def test_incident_wip_split_conserves_wafers(incidents):
    inc = incidents[0]
    wip = _incident_wip(inc)
    assert sum(w["wafers"] for w in wip) == _incident_wafers(inc)


def test_pipeline_unknown_alarm_returns_none():
    assert get_tier_data("DOES-NOT-EXIST") is None


def test_real_agent_alarms_registered():
    assert {"A1", "A2", "A3"} <= REAL_AGENT_ALARMS


@pytest.mark.slow
def test_end_to_end_incident_produces_four_tiers():
    # 로컬 ML+결정론 폴백으로 OpenAI 키 없이 완주 (HF 임베딩 로딩 -> 느림)
    from agents.orchestrator import run_orchestrator_for_incident

    data = run_orchestrator_for_incident("TRIAGE-0001")
    assert set(data.keys()) == {"tier1", "tier2", "tier3", "tier4"}
    assert data["tier2"]["causes"]
    assert data["tier4"]["immediate"]
