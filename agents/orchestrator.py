"""4-Tier 멀티에이전트 오케스트레이터 (LangGraph 기반)

각 Tier가 tool-using LLM agent이며, LangGraph로 조정합니다.

[그래프 구조]
    START -> detect
    detect --(score >= 0.3)--> cause
    detect --(score < 0.3)---> noise -> END   (severity gate)
    cause --(max pct < 40)---> cause_retry -> supervisor
    cause --(max pct >= 40)--> supervisor
    supervisor --(LLM 결정)-+-> impact -> response -> END   (proceed_full / escalate)
                            +-> fast_impact -> response -> END   (fast_track: Tier 3 skip)

Supervisor (`agents.supervisor`)는 LLM이 Tier 2 결과를 보고 동적으로 routing 결정.
- proceed_full: 표준 (Tier 3 + 4)
- fast_track: 원인 단독 우세 시 Tier 3 skip
- escalate: 고위험 - 정상 진행 + human review 플래그 (tier4.metadata에 기록)

[캐싱] build_graph 1회 컴파일, run_orchestrator 알람당 8개 LRU
[Observability] @traceable + wrap_openai (환경변수 LANGSMITH_TRACING=true 시 활성)
"""
from functools import lru_cache
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from agents.cause import run_cause
from agents.detection import run_detection
from agents.impact import run_impact
from agents.response import run_response
from agents.supervisor import run_supervisor
from core.schema import Tier1, Tier2, Tier3, Tier4, TierData
from data.demo import DEFAULT_ALARMS
from data.wip import get_affected_wip

SEVERITY_THRESHOLD = 0.30
CAUSE_CONFIDENCE_THRESHOLD = 40


class _GraphState(TypedDict, total=False):
    alarm: dict
    tier1: Tier1
    tier2: Tier2
    tier3: Tier3
    tier4: Tier4
    skipped: bool
    cause_retried: bool
    supervisor_decision: dict  # {action, severity, reasoning}


def _node_detect(state: _GraphState) -> dict:
    return {"tier1": run_detection(state["alarm"])}


def _route_after_detect(state: _GraphState) -> str:
    return "cause" if state["tier1"]["score"] >= SEVERITY_THRESHOLD else "noise"


def _node_noise(state: _GraphState) -> dict:
    return {
        "skipped": True,
        "tier2": {"causes": []},
        "tier3": {"yield_loss": 0.0, "dependencies": [], "impact_lots": []},
        "tier4": {"immediate": [], "longterm": [], "refs": []},
    }


def _node_cause(state: _GraphState) -> dict:
    return {"tier2": run_cause(state["alarm"], state["tier1"])}


def _route_after_cause(state: _GraphState) -> str:
    if state.get("cause_retried"):
        return "supervisor"  # 이미 재시도 - supervisor로 직행
    causes = state["tier2"]["causes"]
    max_pct = max((c.get("pct", 0) for c in causes), default=0)
    return "cause_retry" if max_pct < CAUSE_CONFIDENCE_THRESHOLD else "supervisor"


def _node_cause_retry(state: _GraphState) -> dict:
    return {
        "tier2": run_cause(state["alarm"], state["tier1"], retry_hint=True),
        "cause_retried": True,
    }


def _node_supervisor(state: _GraphState) -> dict:
    decision = run_supervisor(state["alarm"], state["tier1"], state["tier2"])
    return {"supervisor_decision": decision}


def _route_after_supervisor(state: _GraphState) -> str:
    action = state["supervisor_decision"]["action"]
    if action == "fast_track":
        return "fast_impact"
    return "impact"  # proceed_full + escalate 모두 impact 경유


def _node_impact(state: _GraphState) -> dict:
    return {"tier3": run_impact(state["alarm"], state["tier1"], state["tier2"])}


def _node_fast_impact(state: _GraphState) -> dict:
    """fast_track: LLM 호출 없이 결정론적 lightweight impact

    Tier 4가 tier3을 요구하므로 최소 정보만 채워 전달.
    yield_loss는 tier1 score를 단순 변환, downstream은 current stage만.
    """
    alarm = state["alarm"]
    tier1 = state["tier1"]
    return {
        "tier3": {
            "yield_loss": round(float(tier1["score"]) * 3.0, 1),  # 단순 추정
            "dependencies": [{
                "stage": alarm["title"].split()[0],
                "delta": f"+{tier1['score']}",
                "tag": "현재",
                "kind": "current",
            }],
            "impact_lots": get_affected_wip(alarm["id"]),
        }
    }


def _node_response(state: _GraphState) -> dict:
    tier4 = run_response(state["alarm"], state["tier1"], state["tier2"], state["tier3"])
    # supervisor가 escalate 결정 시 immediate 첫 항목에 human review 플래그 추가
    decision = state.get("supervisor_decision", {})
    if decision.get("action") == "escalate" and tier4.get("immediate"):
        tier4["immediate"][0]["text"] = "🚨 [HUMAN REVIEW 요구] " + tier4["immediate"][0]["text"]
    return {"tier4": tier4}


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(_GraphState)
    g.add_node("detect", _node_detect)
    g.add_node("noise", _node_noise)
    g.add_node("cause", _node_cause)
    g.add_node("cause_retry", _node_cause_retry)
    g.add_node("supervisor", _node_supervisor)
    g.add_node("impact", _node_impact)
    g.add_node("fast_impact", _node_fast_impact)
    g.add_node("response", _node_response)

    g.add_edge(START, "detect")
    g.add_conditional_edges("detect", _route_after_detect, {
        "cause": "cause",
        "noise": "noise",
    })
    g.add_edge("noise", END)
    g.add_conditional_edges("cause", _route_after_cause, {
        "supervisor": "supervisor",
        "cause_retry": "cause_retry",
    })
    g.add_edge("cause_retry", "supervisor")
    g.add_conditional_edges("supervisor", _route_after_supervisor, {
        "impact": "impact",
        "fast_impact": "fast_impact",
    })
    g.add_edge("impact", "response")
    g.add_edge("fast_impact", "response")
    g.add_edge("response", END)
    return g.compile()


def _find_alarm(alarm_id: str) -> dict:
    for a in DEFAULT_ALARMS:
        if a["id"] == alarm_id:
            return a
    raise ValueError(f"알람 ID를 찾을 수 없음: {alarm_id}")


@traceable(name="FabAgent_Orchestrator", run_type="chain")
@lru_cache(maxsize=8)
def run_orchestrator(alarm_id: str) -> TierData:
    alarm = _find_alarm(alarm_id)
    graph = build_graph()
    final = graph.invoke({"alarm": alarm})
    return {
        "tier1": final["tier1"],
        "tier2": final["tier2"],
        "tier3": final["tier3"],
        "tier4": final["tier4"],
    }
