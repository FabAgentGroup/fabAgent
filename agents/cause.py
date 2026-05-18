"""Tier 2 원인 분석 에이전트 (Agentic RAG)

LLM이 도구를 자율 호출해 컨텍스트를 수집한 뒤 원인을 추정합니다.
가용 도구: search_knowledge, lookup_incident_history, get_pm_history

흐름:
1. system prompt + 알람·Tier1 컨텍스트로 시작 (사전 retrieval 없음)
2. tool-calling loop: LLM이 필요한 도구를 호출 -> 결과를 컨텍스트에 추가
3. LLM이 더 호출하지 않을 때(또는 MAX_ITER 도달) synthesis 호출
4. response_format=json_schema 로 TIER2_SCHEMA 구조화 출력
"""
import json

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

[전략]
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


def run_cause(alarm: dict, tier1: Tier1, trace: dict | None = None) -> Tier2:
    """원인 분석을 agentic RAG로 실행, trace dict 전달 시 호출 메타 기록"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _initial_user_prompt(alarm, tier1)},
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

    return result
