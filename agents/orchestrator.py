"""4-Tier 멀티에이전트 오케스트레이터 (LangGraph 기반)

LangGraph의 StateGraph로 detection -> cause -> impact -> response를 노드화
- 현재는 고정 직렬 그래프 (분기/사이클 없음)
- 향후 동적 라우팅·재시도·인터럽트 추가 시 동일 구조 위에서 확장 가능
- graph.get_graph().draw_mermaid()로 워크플로우 다이어그램 자동 추출

알람 dict은 data.demo.DEFAULT_ALARMS에서 ID로 조회
LLM 호출 결과는 프로세스 내 결과 캐시(lru_cache)로 동일 알람 재호출 시 즉시 응답
"""
from functools import lru_cache
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agents.cause import run_cause
from agents.detection import run_detection
from agents.impact import run_impact
from agents.response import run_response
from core.schema import Tier1, Tier2, Tier3, Tier4, TierData
from data.demo import DEFAULT_ALARMS


class _GraphState(TypedDict, total=False):
    alarm: dict
    tier1: Tier1
    tier2: Tier2
    tier3: Tier3
    tier4: Tier4


def _node_detect(state: _GraphState) -> dict:
    return {"tier1": run_detection(state["alarm"])}


def _node_cause(state: _GraphState) -> dict:
    return {"tier2": run_cause(state["alarm"], state["tier1"])}


def _node_impact(state: _GraphState) -> dict:
    return {"tier3": run_impact(state["alarm"], state["tier1"], state["tier2"])}


def _node_response(state: _GraphState) -> dict:
    return {"tier4": run_response(state["alarm"], state["tier1"], state["tier2"], state["tier3"])}


@lru_cache(maxsize=1)
def build_graph():
    """4-Tier 직렬 워크플로우, 첫 호출 시 1회 컴파일"""
    g = StateGraph(_GraphState)
    g.add_node("detect", _node_detect)
    g.add_node("cause", _node_cause)
    g.add_node("impact", _node_impact)
    g.add_node("response", _node_response)
    g.add_edge(START, "detect")
    g.add_edge("detect", "cause")
    g.add_edge("cause", "impact")
    g.add_edge("impact", "response")
    g.add_edge("response", END)
    return g.compile()


def _find_alarm(alarm_id: str) -> dict:
    for a in DEFAULT_ALARMS:
        if a["id"] == alarm_id:
            return a
    raise ValueError(f"알람 ID를 찾을 수 없음: {alarm_id}")


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
