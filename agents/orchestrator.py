"""4-Tier 멀티에이전트 오케스트레이터 (LangGraph 기반, 조건부 라우팅)

각 Tier가 tool-using LLM agent이며, 오케스트레이터는 LangGraph로 조정합니다.

[그래프 구조]
    START -> detect
    detect --(score >= 0.3)--> cause
    detect --(score < 0.3)---> noise -> END   (severity gate: 노이즈는 분석 skip)
    cause --(max pct >= 40)--> impact
    cause --(max pct < 40)---> cause_retry -> impact  (confidence retry)
    impact -> response -> END

[캐싱]
- build_graph(): 그래프 컴파일 1회 (lru_cache)
- run_orchestrator(alarm_id): 알람당 결과 캐시 8개 (LLM 비용 절감)
"""
from functools import lru_cache
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from agents.cause import run_cause
from agents.detection import run_detection
from agents.impact import run_impact
from agents.response import run_response
from core.schema import Tier1, Tier2, Tier3, Tier4, TierData
from data.demo import DEFAULT_ALARMS

SEVERITY_THRESHOLD = 0.30      # tier1 score 미만이면 노이즈로 분류
CAUSE_CONFIDENCE_THRESHOLD = 40  # tier2 최대 기여도(%) 미만이면 재시도


class _GraphState(TypedDict, total=False):
    alarm: dict
    tier1: Tier1
    tier2: Tier2
    tier3: Tier3
    tier4: Tier4
    skipped: bool
    cause_retried: bool


def _node_detect(state: _GraphState) -> dict:
    return {"tier1": run_detection(state["alarm"])}


def _route_after_detect(state: _GraphState) -> str:
    return "cause" if state["tier1"]["score"] >= SEVERITY_THRESHOLD else "noise"


def _node_noise(state: _GraphState) -> dict:
    """Tier 1 점수가 낮아 후속 분석 skip - 결과만 표시용으로 채움"""
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
        return "impact"  # 이미 1회 재시도 - 무한 루프 방지
    causes = state["tier2"]["causes"]
    max_pct = max((c.get("pct", 0) for c in causes), default=0)
    return "cause_retry" if max_pct < CAUSE_CONFIDENCE_THRESHOLD else "impact"


def _node_cause_retry(state: _GraphState) -> dict:
    """기여도 낮은 분석 재실행 - retry_hint 신호로 도구 호출 강화 유도"""
    return {
        "tier2": run_cause(state["alarm"], state["tier1"], retry_hint=True),
        "cause_retried": True,
    }


def _node_impact(state: _GraphState) -> dict:
    return {"tier3": run_impact(state["alarm"], state["tier1"], state["tier2"])}


def _node_response(state: _GraphState) -> dict:
    return {"tier4": run_response(state["alarm"], state["tier1"], state["tier2"], state["tier3"])}


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(_GraphState)
    g.add_node("detect", _node_detect)
    g.add_node("noise", _node_noise)
    g.add_node("cause", _node_cause)
    g.add_node("cause_retry", _node_cause_retry)
    g.add_node("impact", _node_impact)
    g.add_node("response", _node_response)

    g.add_edge(START, "detect")
    g.add_conditional_edges("detect", _route_after_detect, {
        "cause": "cause",
        "noise": "noise",
    })
    g.add_edge("noise", END)
    g.add_conditional_edges("cause", _route_after_cause, {
        "impact": "impact",
        "cause_retry": "cause_retry",
    })
    g.add_edge("cause_retry", "impact")
    g.add_edge("impact", "response")
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
