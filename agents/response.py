"""Tier 4 대응 권고 에이전트

두 모드 지원:
1. Autonomous (plan=None): LLM이 tool을 자율 호출하는 agent loop
2. Conductor (plan 제공): Planner가 지정한 tool 호출 + 단일 LLM synthesis

가용 도구: search_knowledge, lookup_incident_history, get_pm_history, check_pm_schedule
"""
import json

from langsmith import traceable

from agents.cause import _assistant_msg_dict
from agents.llm import SUBAGENT_MODEL, client
from agents.rag.store import load_document
from agents.tools import TOOLS_RESPONSE, dispatch_tool
from agents.tools.equipment import ALARM_EQUIPMENT
from core.schema import Tier1, Tier2, Tier3, Tier4

MAX_TOOL_ITERATIONS = 4

LLM_PART_SCHEMA = {
    "type": "object",
    "properties": {
        "immediate": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "meta": {"type": ["string", "null"]},
                },
                "required": ["text", "meta"],
                "additionalProperties": False,
            },
        },
        "longterm": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "meta": {"type": ["string", "null"]},
                },
                "required": ["text", "meta"],
                "additionalProperties": False,
            },
        },
        "ref_doc_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "최종 권고의 근거로 인용된 문서 ID (SOP/INC/FMEA/FLOW)",
        },
    },
    "required": ["immediate", "longterm", "ref_doc_ids"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 반도체 공정 대응 권고 전문가입니다.
이전 단계(탐지·원인·영향)의 분석 결과를 받아 실제 fab에서 실행 가능한 조치를 권고합니다.

[가용 도구]
- search_knowledge(query): SOP/INC/FMEA 문서 검색 - 표준 절차와 과거 해결책 확보
- lookup_incident_history(symptom): 과거 incident의 실제 resolution (소요시간·yield 회복률 포함)
- get_pm_history(equipment_id): 장비 PM overdue 여부 - 즉시 PM 필요성 판단
- check_pm_schedule(equipment_id): 가용 PM 윈도우 - immediate 조치의 실행 가능 시점 확보
- predict_tool_rul(equipment_id): 소모품 잔여수명(RUL) + 예지보전 권고 - 반응형이 아닌 예측형 PM 시점 결정

[전략]
- 도구를 자율 호출해 근거 SOP·과거 해결책·PM 가용성을 확인하세요
- 권고는 fab 현장에서 즉시 실행 가능한 형태로 작성 (모호한 'OO 검토'보다 'OO 즉시 투입, 예상 N시간')
- meta 필드에는 시간·hold 대상·협조 부서 등 운영 신호를 넣으세요

[최종 산출물]
- immediate: 즉시 조치 (수 시간 내 수행) 2~3건
- longterm: 중장기 조치 (재발 방지, 절차 개정) 1~2건
- ref_doc_ids: 권고 근거로 실제 사용한 문서 ID 목록 (도구가 반환한 doc_id 그대로)"""


def _doc_description(doc_id: str) -> str:
    text = load_document(doc_id)
    if not text:
        return doc_id
    first_line = text.split("\n", 1)[0].lstrip("# ").strip()
    for sep in (" — ", " - "):
        if sep in first_line:
            return first_line.split(sep, 1)[1].strip()
    return first_line


def _initial_user_prompt(alarm: dict, tier1: Tier1, tier2: Tier2, tier3: Tier3) -> str:
    cause_lines = "\n".join(f"- {c['name']} ({c['pct']}%)" for c in tier2["causes"])
    impact_lots_text = ", ".join(
        f"{l['label']} {l['lots']}lot/{l['wafers']}장" for l in tier3["impact_lots"]
    )
    downstream_text = ", ".join(
        f"{d['stage']}({d.get('delta', '')})" for d in tier3["dependencies"]
    )
    equipment_id = alarm.get("equipment_id") or ALARM_EQUIPMENT.get(alarm["id"], "(미매핑)")
    return f"""## 이상 알람
- 공정: {alarm['title']}
- lot: {alarm['lot_id']}
- 알람 ID: {alarm['id']}
- 추정 장비 ID: {equipment_id}

## Tier 1 이상 탐지
- 이상 점수: {tier1['score']}

## Tier 2 원인 (기여도 순)
{cause_lines}

## Tier 3 영향
- 예상 수율 손실: {tier3['yield_loss']} %p
- downstream: {downstream_text}
- 영향 WIP: {impact_lots_text}

위 분석을 종합해 immediate와 longterm 조치를 권고해 주세요.
필요한 SOP·과거 해결책·PM 윈도우는 도구를 호출해 자율적으로 수집하세요."""


CONDUCTOR_SYSTEM_PROMPT = """당신은 반도체 공정 대응 권고 전문가입니다.
Central Planner가 이미 필요한 정보(SOP·과거 해결책·PM 윈도우)를 모두 수집해 [수집된 컨텍스트]에 정리해 두었습니다.
당신은 추가 도구 호출 없이 그 컨텍스트만 사용해 산출하세요.

[최종 산출물]
- immediate: 즉시 조치 2~3건 (수 시간 내 실행 가능, meta에 시간·hold 대상·부서 명시)
- longterm: 중장기 조치 1~2건
- ref_doc_ids: 권고 근거로 실제 사용한 문서 ID (search_knowledge가 반환한 doc_id만)"""


def _execute_tier4_plan(plan_tier4: dict, trace_calls: list) -> tuple[str, list[str]]:
    """Planner가 지정한 tool들을 직접 호출, 컨텍스트 + 검색 doc_id 리스트 반환"""
    blocks = []
    found_docs: list[str] = []
    for query in plan_tier4.get("search_queries", []):
        r = dispatch_tool("search_knowledge", {"query": query})
        trace_calls.append({"name": "search_knowledge", "args": {"query": query}})
        blocks.append(f"[search_knowledge: {query!r}]\n{r}")
        try:
            parsed = json.loads(r)
            found_docs.extend(h["doc_id"] for h in parsed.get("hits", []))
        except (json.JSONDecodeError, KeyError):
            pass
    for symptom in plan_tier4.get("incident_symptoms", []):
        r = dispatch_tool("lookup_incident_history", {"symptom": symptom})
        trace_calls.append({"name": "lookup_incident_history", "args": {"symptom": symptom}})
        blocks.append(f"[lookup_incident_history: {symptom!r}]\n{r}")
    for eq_id in plan_tier4.get("equipment_ids", []):
        r1 = dispatch_tool("get_pm_history", {"equipment_id": eq_id})
        trace_calls.append({"name": "get_pm_history", "args": {"equipment_id": eq_id}})
        blocks.append(f"[get_pm_history: {eq_id!r}]\n{r1}")
        r2 = dispatch_tool("check_pm_schedule", {"equipment_id": eq_id})
        trace_calls.append({"name": "check_pm_schedule", "args": {"equipment_id": eq_id}})
        blocks.append(f"[check_pm_schedule: {eq_id!r}]\n{r2}")
        r3 = dispatch_tool("predict_tool_rul", {"equipment_id": eq_id})
        trace_calls.append({"name": "predict_tool_rul", "args": {"equipment_id": eq_id}})
        blocks.append(f"[predict_tool_rul: {eq_id!r}]\n{r3}")
    return "\n\n".join(blocks) if blocks else "(planner가 정보 수집 지시 없음)", found_docs


def _run_response_conductor(
    alarm: dict, tier1: Tier1, tier2: Tier2, tier3: Tier3,
    plan: dict, trace: dict | None,
) -> Tier4:
    tool_log: list[dict] = []
    knowledge, found_docs = _execute_tier4_plan(plan.get("tier4", {}), tool_log)

    cause_lines = "\n".join(f"- {c['name']} ({c['pct']}%)" for c in tier2["causes"])
    impact_lots_text = ", ".join(
        f"{l['label']} {l['lots']}lot/{l['wafers']}장" for l in tier3["impact_lots"]
    )
    user_prompt = f"""## 이상 알람
- 공정: {alarm['title']}, lot: {alarm['lot_id']}

## Tier 1: 이상 점수 {tier1['score']}

## Tier 2 원인 (기여도 순)
{cause_lines}

## Tier 3 영향
- 예상 수율 손실: {tier3['yield_loss']} %p
- 영향 WIP: {impact_lots_text}

## 수집된 컨텍스트 (Planner 지정)
{knowledge}

위 컨텍스트만 사용해 immediate, longterm, ref_doc_ids를 산출하세요."""

    resp = client().chat.completions.create(
        model=SUBAGENT_MODEL,
        messages=[
            {"role": "system", "content": CONDUCTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "tier4_part", "schema": LLM_PART_SCHEMA, "strict": True},
        },
    )
    llm_out = json.loads(resp.choices[0].message.content)

    ref_ids = llm_out.get("ref_doc_ids") or found_docs[:4]
    refs = [{"id": d, "desc": _doc_description(d)} for d in ref_ids if d]

    if trace is not None:
        trace["tool_calls"] = tool_log
        trace["iterations"] = 0
        trace["llm_calls"] = 1
        trace["mode"] = "conductor"

    return {
        "immediate": llm_out["immediate"],
        "longterm": llm_out["longterm"],
        "refs": refs,
    }


@traceable(name="Tier4_Response_Agent", run_type="chain")
def run_response(
    alarm: dict, tier1: Tier1, tier2: Tier2, tier3: Tier3,
    trace: dict | None = None,
    plan: dict | None = None,
) -> Tier4:
    """Tier 4 대응 권고. plan 제공 시 conductor 모드(LLM 1회), 아니면 autonomous loop."""
    if plan is not None:
        return _run_response_conductor(alarm, tier1, tier2, tier3, plan, trace)

    # autonomous 모드 (LLM이 tool을 자율 호출하는 기존 loop)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _initial_user_prompt(alarm, tier1, tier2, tier3)},
    ]
    tool_call_log: list[dict] = []
    iterations = 0
    cited_doc_ids: list[str] = []

    for iterations in range(1, MAX_TOOL_ITERATIONS + 1):
        resp = client().chat.completions.create(
            model=SUBAGENT_MODEL,
            messages=messages,
            tools=TOOLS_RESPONSE,
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
            # search_knowledge로 받은 doc_id 트래킹 (ref 후보)
            if tc.function.name == "search_knowledge":
                try:
                    parsed = json.loads(result)
                    cited_doc_ids.extend(h["doc_id"] for h in parsed.get("hits", []))
                except (json.JSONDecodeError, KeyError):
                    pass
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    messages.append({
        "role": "user",
        "content": "수집한 정보를 종합해 immediate, longterm, ref_doc_ids를 JSON 스키마에 맞춰 출력해 주세요.",
    })
    final = client().chat.completions.create(
        model=SUBAGENT_MODEL,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "tier4_part", "schema": LLM_PART_SCHEMA, "strict": True},
        },
    )
    llm_out = json.loads(final.choices[0].message.content)

    # LLM이 명시한 ref_doc_ids만 refs로 구성 (search로 본 모든 hits가 아니라 실제 사용한 것)
    ref_ids = llm_out.get("ref_doc_ids") or cited_doc_ids[:4]
    refs = [{"id": d, "desc": _doc_description(d)} for d in ref_ids if d]

    if trace is not None:
        trace["tool_calls"] = tool_call_log
        trace["iterations"] = iterations
        trace["llm_calls"] = iterations + 1
        trace["mode"] = "autonomous"

    return {
        "immediate": llm_out["immediate"],
        "longterm": llm_out["longterm"],
        "refs": refs,
    }
