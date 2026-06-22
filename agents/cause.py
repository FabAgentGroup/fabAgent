"""Tier 2 원인 분석 에이전트

두 모드 지원:
1. **Autonomous (기본, plan=None)**: LLM이 tool을 자율 호출하는 agent loop
   - 2~3 iteration + synthesis = LLM 호출 3~4회
2. **Conductor (plan 제공)**: Planner가 지정한 tool 호출 + 단일 LLM synthesis
   - Tool 직접 실행 + LLM 호출 1회. 재귀·loop 없음

가용 도구: search_knowledge, lookup_incident_history, get_pm_history
"""
import json

from langsmith import traceable

from agents.llm import SUBAGENT_MODEL, client
from agents.tools import TOOLS_CAUSE, dispatch_tool
from agents.tools.equipment import ALARM_EQUIPMENT
from core.schema import Tier1, Tier2

MAX_TOOL_ITERATIONS = 4

TIER2_SCHEMA = {
    "type": "object",
    "properties": {
        "causes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "pct": {"type": "integer"},
                    "evidence": {"type": "string"},
                    "citations": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "pct", "evidence", "citations"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["causes"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 반도체 공정 원인 분석 전문가입니다.
이상 알람과 Tier 1 탐지 결과를 받아 가장 가능성 높은 원인 2~3개를 추정합니다.

[가용 도구]
- search_knowledge(query): 사내 지식 문서(INC/FMEA/SOP/FLOW) hybrid 검색
- lookup_incident_history(symptom): 과거 incident 구조화 조회 (원인·해결책·yield 회복률)
- get_pm_history(equipment_id): 장비 PM 이력 (마지막 PM 경과일, overdue 여부)
- commonality_analysis(process, scope_tool, scope_recipe): 불량 웨이퍼의 공통 엔티티(장비·챔버·슬러리 lot·작업자)를 통계(lift·p-value)로 추출

[전략]
- 정성 근거(search/incident)와 정량 근거(commonality)를 함께 쓰세요
  commonality의 과대표현 엔티티(lift 높고 p 낮음)는 강력한 물리적 원인 후보이며 evidence·citations에 반영하세요
- 도구를 자율적으로 선택·호출해 충분한 근거를 모으세요 (반복 호출 허용)
- 동일한 도구를 반복 호출하지 말고, 필요한 정보가 다 모이면 호출을 멈추세요
- 모인 정보가 충분하면 자연어로 답하지 말고 곧바로 종료해 최종 구조화 출력으로 넘어가세요

[최종 산출물 (synthesis 단계에서 JSON으로)]
- causes: 2~3개. 각 원인은 name / pct(기여도 %) / evidence(구체적 근거) / citations(문서 ID 또는 incident ID)
- pct 합은 100에 가까워야 함, 기여도 높은 원인부터 정렬
- 도구로 얻지 못한 정보는 인용하지 마세요"""


def _initial_user_prompt(alarm: dict, tier1: Tier1) -> str:
    sensors = ", ".join(f["name"] for f in tier1["features"])
    equipment_id = ALARM_EQUIPMENT.get(alarm["id"], "(미매핑)")
    return f"""## 이상 알람
- 공정: {alarm['title']}
- lot: {alarm['lot_id']}
- 이상 피처: {alarm.get('feature')} {alarm.get('feature_arrow') or ''}
- 알람 ID: {alarm['id']}
- 추정 장비 ID: {equipment_id}

## Tier 1 이상 탐지 결과
- 이상 점수: {tier1['score']}
- 기여 센서(Top): {sensors}

위 정보를 바탕으로 원인을 분석해 주세요.
필요한 컨텍스트는 가용 도구를 호출해 자율적으로 수집하세요."""


def _assistant_msg_dict(msg) -> dict:
    """OpenAI assistant 응답을 messages 배열에 다시 넣을 dict로 변환"""
    out: dict = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    return out


CONDUCTOR_SYSTEM_PROMPT = """당신은 반도체 공정 원인 분석 전문가입니다.
Central Planner가 이미 필요한 정보를 모두 수집해 [수집된 컨텍스트]에 정리해 두었습니다.
당신은 추가 도구 호출 없이 그 컨텍스트만 사용해 원인 2~3개를 산출하세요.

[최종 산출물]
- causes: 2~3개. 각 원인은 name / pct(기여도 %) / evidence(구체적 근거) / citations(문서 ID 또는 incident ID)
- pct 합은 100에 가까워야 함, 기여도 높은 원인부터 정렬
- 제공되지 않은 정보는 인용하지 마세요"""


def _execute_tier2_plan(plan_tier2: dict, trace_calls: list) -> str:
    """Planner가 지정한 tool들을 직접 호출하고 컨텍스트로 변환"""
    blocks = []
    for query in plan_tier2.get("search_queries", []):
        result = dispatch_tool("search_knowledge", {"query": query})
        trace_calls.append({"name": "search_knowledge", "args": {"query": query}})
        blocks.append(f"[search_knowledge: {query!r}]\n{result}")
    for symptom in plan_tier2.get("incident_symptoms", []):
        result = dispatch_tool("lookup_incident_history", {"symptom": symptom})
        trace_calls.append({"name": "lookup_incident_history", "args": {"symptom": symptom}})
        blocks.append(f"[lookup_incident_history: {symptom!r}]\n{result}")
    for eq_id in plan_tier2.get("equipment_ids", []):
        result = dispatch_tool("get_pm_history", {"equipment_id": eq_id})
        trace_calls.append({"name": "get_pm_history", "args": {"equipment_id": eq_id}})
        blocks.append(f"[get_pm_history: {eq_id!r}]\n{result}")
    comm = plan_tier2.get("commonality") or {}
    if comm.get("process"):
        args = {"process": comm["process"]}
        if comm.get("scope_tool"):
            args["scope_tool"] = comm["scope_tool"]
        if comm.get("scope_recipe"):
            args["scope_recipe"] = comm["scope_recipe"]
        result = dispatch_tool("commonality_analysis", args)
        trace_calls.append({"name": "commonality_analysis", "args": args})
        blocks.append(f"[commonality_analysis: {args}]\n{result}")
    return "\n\n".join(blocks) if blocks else "(planner가 정보 수집 지시 없음)"


def _run_cause_conductor(alarm: dict, tier1: Tier1, plan: dict, trace: dict | None) -> Tier2:
    """Conductor 모드: plan대로 tool 실행 + 1회 LLM synthesis"""
    tool_log: list[dict] = []
    knowledge = _execute_tier2_plan(plan.get("tier2", {}), tool_log)

    sensors = ", ".join(f["name"] for f in tier1["features"])
    user_prompt = f"""## 이상 알람
- 공정: {alarm['title']}
- lot: {alarm['lot_id']}
- 이상 피처: {alarm.get('feature')} {alarm.get('feature_arrow') or ''}

## Tier 1 이상 탐지 결과
- 이상 점수: {tier1['score']}
- 기여 센서(Top): {sensors}

## 수집된 컨텍스트 (Planner 지정)
{knowledge}

위 컨텍스트만 사용해 원인을 분석하세요."""

    resp = client().chat.completions.create(
        model=SUBAGENT_MODEL,
        messages=[
            {"role": "system", "content": CONDUCTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "tier2", "schema": TIER2_SCHEMA, "strict": True},
        },
    )
    result = json.loads(resp.choices[0].message.content)

    if trace is not None:
        trace["tool_calls"] = tool_log
        trace["iterations"] = 0
        trace["llm_calls"] = 1
        trace["mode"] = "conductor"

    return result


@traceable(name="Tier2_Cause_Agent", run_type="chain")
def run_cause(
    alarm: dict,
    tier1: Tier1,
    trace: dict | None = None,
    retry_hint: bool = False,
    plan: dict | None = None,
) -> Tier2:
    """원인 분석 실행

    plan 제공 시 conductor 모드 (단일 LLM 호출, tool 직접 실행).
    plan=None이면 기존 autonomous tool-calling loop 모드.

    retry_hint=True 면 autonomous 모드에서 더 적극적으로 도구를 호출하도록 유도.
    """
    if plan is not None:
        return _run_cause_conductor(alarm, tier1, plan, trace)
    user_prompt = _initial_user_prompt(alarm, tier1)
    if retry_hint:
        user_prompt += (
            "\n\n[재시도 신호] 직전 분석에서 최상위 원인의 기여도가 낮게 산정되었습니다. "
            "도구를 더 적극적으로(다양한 쿼리·증상 키워드로 여러 번) 호출해 더 강한 근거를 모으세요."
        )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    tool_call_log: list[dict] = []
    iterations = 0

    for iterations in range(1, MAX_TOOL_ITERATIONS + 1):
        resp = client().chat.completions.create(
            model=SUBAGENT_MODEL,
            messages=messages,
            tools=TOOLS_CAUSE,
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        messages.append(_assistant_msg_dict(msg))

        if not msg.tool_calls:
            break

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result = dispatch_tool(tc.function.name, args)
            tool_call_log.append({"name": tc.function.name, "args": args})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    # synthesis 호출: tools 없이 structured output 강제
    messages.append({
        "role": "user",
        "content": "수집한 정보를 종합해 최종 원인 분석을 JSON 스키마에 맞춰 출력해 주세요.",
    })
    final = client().chat.completions.create(
        model=SUBAGENT_MODEL,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "tier2", "schema": TIER2_SCHEMA, "strict": True},
        },
    )
    result = json.loads(final.choices[0].message.content)

    if trace is not None:
        trace["tool_calls"] = tool_call_log
        trace["iterations"] = iterations
        trace["llm_calls"] = iterations + 1
        trace["mode"] = "autonomous"

    return result
