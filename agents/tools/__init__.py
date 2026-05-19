"""Agent tool registry - LLM이 자율 호출하는 도구 모음

각 tool은 (function, OpenAI schema) 쌍으로 구성
- knowledge.search_knowledge: hybrid RAG 검색
- incident.lookup_incident_history: 과거 incident 구조화 조회
- equipment.get_pm_history / check_pm_schedule: PM 이력·예정
- process.get_downstream_steps / query_wip_status / get_yield_baseline: 공정 의존성·WIP·수율

Tier별 사용 가능 tool 묶음:
- TOOLS_CAUSE: Tier 2 원인 분석 (search, incident, pm)
- TOOLS_IMPACT: Tier 3 영향 평가 (wip, downstream, yield, pm)
- TOOLS_RESPONSE: Tier 4 대응 권고 (search, incident, pm, schedule)

LLM 호출 패턴:
    from agents.tools import TOOLS_CAUSE, dispatch_tool
    resp = client().chat.completions.create(
        model=..., messages=..., tools=TOOLS_CAUSE, tool_choice="auto"
    )
    for tc in resp.choices[0].message.tool_calls or []:
        result = dispatch_tool(tc.function.name, json.loads(tc.function.arguments))
"""
import json

from langsmith import traceable

from agents.tools import equipment, incident, knowledge, process

_REGISTRY = {
    "search_knowledge": knowledge.search_knowledge,
    "lookup_incident_history": incident.lookup_incident_history,
    "get_pm_history": equipment.get_pm_history,
    "check_pm_schedule": equipment.check_pm_schedule,
    "get_downstream_steps": process.get_downstream_steps,
    "query_wip_status": process.query_wip_status,
    "get_yield_baseline": process.get_yield_baseline,
}

# Tier별 노출 tool 묶음
TOOLS_CAUSE = [
    knowledge.SCHEMA,
    incident.SCHEMA,
    equipment.SCHEMA_GET_PM,
]
TOOLS_IMPACT = [
    process.SCHEMA_WIP,
    process.SCHEMA_DOWNSTREAM,
    process.SCHEMA_YIELD,
    equipment.SCHEMA_GET_PM,
]
TOOLS_RESPONSE = [
    knowledge.SCHEMA,
    incident.SCHEMA,
    equipment.SCHEMA_GET_PM,
    equipment.SCHEMA_CHECK_PM,
]


@traceable(name="tool_call", run_type="tool")
def dispatch_tool(name: str, args: dict) -> str:
    """tool 함수를 이름으로 호출, 결과를 JSON string으로 반환 (LLM 입력용)"""
    fn = _REGISTRY.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
    try:
        result = fn(**args)
    except TypeError as e:
        return json.dumps({"error": f"invalid args: {e}"}, ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False, default=str)


def all_tool_names() -> list[str]:
    return list(_REGISTRY.keys())
