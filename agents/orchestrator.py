"""4-Tier 멀티에이전트 오케스트레이터 (LangGraph 기반)

두 가지 실행 모드 지원 (환경변수 AGENT_MODE):
- **conductor** (기본): Central Planner Agent가 전체 plan 1회 산출
  각 Tier executor가 plan대로 tool 호출 + LLM 1회 synthesis
  → LLM 호출 ~70% 감소, latency 큰 폭 단축
- **autonomous**: 각 Tier가 tool-using agent loop로 자율 실행
  → 적응성 높으나 LLM 호출 많음

[그래프 - conductor 모드]
    START → detect → (severity gate) → planner → (action 분기)
            ↓
            +→ cause → impact → response → END           (proceed_full)
            +→ cause → fast_impact → response → END      (fast_track)
            +→ cause → impact → response_escalate → END  (escalate, T4에 🚨 prepend)

[그래프 - autonomous 모드]
    기존 구조 (severity gate + cause_retry + supervisor 분기)

알람 dict은 data.demo.DEFAULT_ALARMS에서 ID로 조회.
@traceable (LangSmith) + wrap_openai 로 LLM·tool 호출 자동 트레이스.
"""
import os
from functools import lru_cache
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from agents.cause import run_cause
from agents.detection import run_detection
from agents.impact import run_impact
from agents.planner import plan_workflow
from agents.response import run_response
from agents.supervisor import run_supervisor
from core.schema import Tier1, Tier2, Tier3, Tier4, TierData
from data.demo import DEFAULT_ALARMS
from data.wip import get_affected_wip

SEVERITY_THRESHOLD = 0.30
CAUSE_CONFIDENCE_THRESHOLD = 40


def _agent_mode() -> str:
    return os.getenv("AGENT_MODE", "conductor").lower()


class _GraphState(TypedDict, total=False):
    alarm: dict
    tier1: Tier1
    tier2: Tier2
    tier3: Tier3
    tier4: Tier4
    skipped: bool
    cause_retried: bool
    supervisor_decision: dict
    plan: dict  # conductor 모드의 Planner 결과


def _node_detect(state: _GraphState) -> dict:
    return {"tier1": run_detection(state["alarm"])}


def _route_after_detect(state: _GraphState) -> str:
    return "go" if state["tier1"]["score"] >= SEVERITY_THRESHOLD else "noise"


def _node_noise(state: _GraphState) -> dict:
    return {
        "skipped": True,
        "tier2": {"causes": []},
        "tier3": {"yield_loss": 0.0, "dependencies": [], "impact_lots": []},
        "tier4": {"immediate": [], "longterm": [], "refs": []},
    }


# ==================== Conductor 모드 노드 ====================

def _node_planner(state: _GraphState) -> dict:
    return {"plan": plan_workflow(state["alarm"], state["tier1"])}


def _route_after_planner(state: _GraphState) -> str:
    action = state["plan"].get("action", "proceed_full")
    if action == "fast_track":
        return "fast_track"
    return "proceed"  # proceed_full + escalate 모두 표준 경로


def _node_cause_conductor(state: _GraphState) -> dict:
    return {"tier2": run_cause(state["alarm"], state["tier1"], plan=state["plan"])}


def _node_impact_conductor(state: _GraphState) -> dict:
    return {"tier3": run_impact(state["alarm"], state["tier1"], state["tier2"], plan=state["plan"])}


def _node_fast_impact(state: _GraphState) -> dict:
    """fast_track: deterministic 경량 처리 (LLM 호출 없음)"""
    alarm = state["alarm"]
    tier1 = state["tier1"]
    return {
        "tier3": {
            "yield_loss": round(float(tier1["score"]) * 3.0, 1),
            "dependencies": [{
                "stage": alarm["title"].split()[0],
                "delta": f"+{tier1['score']}",
                "tag": "현재",
                "kind": "current",
            }],
            "impact_lots": get_affected_wip(alarm["id"]),
        }
    }


def _node_response_conductor(state: _GraphState) -> dict:
    tier4 = run_response(state["alarm"], state["tier1"], state["tier2"], state["tier3"], plan=state["plan"])
    if state["plan"].get("action") == "escalate" and tier4.get("immediate"):
        tier4["immediate"][0]["text"] = "🚨 [HUMAN REVIEW 요구] " + tier4["immediate"][0]["text"]
    return {"tier4": tier4}


# ==================== Autonomous 모드 노드 (기존 보존) ====================

def _node_cause_autonomous(state: _GraphState) -> dict:
    return {"tier2": run_cause(state["alarm"], state["tier1"])}


def _route_after_cause_autonomous(state: _GraphState) -> str:
    if state.get("cause_retried"):
        return "supervisor"
    causes = state["tier2"]["causes"]
    max_pct = max((c.get("pct", 0) for c in causes), default=0)
    return "cause_retry" if max_pct < CAUSE_CONFIDENCE_THRESHOLD else "supervisor"


def _node_cause_retry(state: _GraphState) -> dict:
    return {
        "tier2": run_cause(state["alarm"], state["tier1"], retry_hint=True),
        "cause_retried": True,
    }


def _node_supervisor(state: _GraphState) -> dict:
    return {"supervisor_decision": run_supervisor(state["alarm"], state["tier1"], state["tier2"])}


def _route_after_supervisor(state: _GraphState) -> str:
    return "fast_track" if state["supervisor_decision"]["action"] == "fast_track" else "proceed"


def _node_impact_autonomous(state: _GraphState) -> dict:
    return {"tier3": run_impact(state["alarm"], state["tier1"], state["tier2"])}


def _node_response_autonomous(state: _GraphState) -> dict:
    tier4 = run_response(state["alarm"], state["tier1"], state["tier2"], state["tier3"])
    decision = state.get("supervisor_decision", {})
    if decision.get("action") == "escalate" and tier4.get("immediate"):
        tier4["immediate"][0]["text"] = "🚨 [HUMAN REVIEW 요구] " + tier4["immediate"][0]["text"]
    return {"tier4": tier4}


# ==================== Graph 빌더 ====================

@lru_cache(maxsize=2)
def build_graph(mode: str = "conductor"):
    g = StateGraph(_GraphState)
    g.add_node("detect", _node_detect)
    g.add_node("noise", _node_noise)
    g.add_edge(START, "detect")
    g.add_edge("noise", END)

    if mode == "conductor":
        g.add_node("planner", _node_planner)
        g.add_node("cause", _node_cause_conductor)
        g.add_node("impact", _node_impact_conductor)
        g.add_node("fast_impact", _node_fast_impact)
        g.add_node("response", _node_response_conductor)

        g.add_conditional_edges("detect", _route_after_detect, {"go": "planner", "noise": "noise"})
        g.add_edge("planner", "cause")
        g.add_conditional_edges("cause", _route_after_planner, {
            "proceed": "impact",
            "fast_track": "fast_impact",
        })
        g.add_edge("impact", "response")
        g.add_edge("fast_impact", "response")
        g.add_edge("response", END)
    else:
        # autonomous (기존 구조)
        g.add_node("cause", _node_cause_autonomous)
        g.add_node("cause_retry", _node_cause_retry)
        g.add_node("supervisor", _node_supervisor)
        g.add_node("impact", _node_impact_autonomous)
        g.add_node("fast_impact", _node_fast_impact)
        g.add_node("response", _node_response_autonomous)

        g.add_conditional_edges("detect", _route_after_detect, {"go": "cause", "noise": "noise"})
        g.add_conditional_edges("cause", _route_after_cause_autonomous, {
            "supervisor": "supervisor",
            "cause_retry": "cause_retry",
        })
        g.add_edge("cause_retry", "supervisor")
        g.add_conditional_edges("supervisor", _route_after_supervisor, {
            "proceed": "impact",
            "fast_track": "fast_impact",
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
    graph = build_graph(_agent_mode())
    final = graph.invoke({"alarm": alarm})
    return {
        "tier1": final["tier1"],
        "tier2": final["tier2"],
        "tier3": final["tier3"],
        "tier4": final["tier4"],
    }
