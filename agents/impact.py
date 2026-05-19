"""Tier 3 공정 간 영향 평가 에이전트

두 모드 지원:
1. Autonomous (plan=None): LLM이 tool을 자율 호출하는 agent loop
2. Conductor (plan 제공): Planner가 지정한 tool 호출 + 단일 LLM synthesis

가용 도구: query_wip_status, get_downstream_steps, get_yield_baseline, get_pm_history
"""
import json

from langsmith import traceable

from agents.cause import _assistant_msg_dict
from agents.llm import SUBAGENT_MODEL, client
from agents.tools import TOOLS_IMPACT, dispatch_tool
from agents.tools.equipment import ALARM_EQUIPMENT
from core.schema import Tier1, Tier2, Tier3
from data.wip import get_affected_wip

MAX_TOOL_ITERATIONS = 4

LLM_PART_SCHEMA = {
    "type": "object",
    "properties": {
        "yield_loss": {"type": "number"},
        "downstream_dependencies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string"},
                    "delta": {"type": "string"},
                    "tag": {"type": "string"},
                    "kind": {"type": "string", "enum": ["impacted", "minor"]},
                },
                "required": ["stage", "delta", "tag", "kind"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["yield_loss", "downstream_dependencies"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 반도체 공정 영향 평가 전문가입니다.
이상이 발생한 공정에서 출발해 downstream 영향을 정량 평가합니다.

[가용 도구]
- query_wip_status(alarm_id): 영향 받는 WIP(가공중·대기중) lot/wafer 수
- get_downstream_steps(current_stage): 후공정 의존성 (typical_delta_pct·severity 포함)
- get_yield_baseline(process): 공정 최근 30일 yield 기준선 - baseline 대비로 yield_loss 정량화
- get_pm_history(equipment_id): 장비 PM 이력 - PM 누락이 영향을 증폭시키는 요인인지 판단

[전략]
- 도구를 자율 호출해 정량 근거를 모으세요
- downstream 후공정을 알려면 get_downstream_steps를 호출해 fab 흐름 파악
- yield_loss는 Tier 2 원인의 기여도·과거 incident 회복률·baseline을 종합해 추정
- 충분한 정보가 모이면 종료해 최종 구조화 출력으로 넘어가세요

[최종 산출물]
- yield_loss: 본 이상으로 인한 예상 수율 손실(%p, 소수 한 자리)
- downstream_dependencies: 영향 받는 후공정 (current 제외) - stage / delta / tag / kind"""


def _stage_from_alarm(alarm: dict) -> str:
    return alarm["title"].split()[0]


def _initial_user_prompt(alarm: dict, tier1: Tier1, tier2: Tier2) -> str:
    cause_lines = "\n".join(
        f"- {c['name']} ({c['pct']}%): {c['evidence'][:120]}" for c in tier2["causes"]
    )
    equipment_id = ALARM_EQUIPMENT.get(alarm["id"], "(미매핑)")
    current_stage = _stage_from_alarm(alarm)
    return f"""## 이상 알람
- 공정: {alarm['title']} (current_stage: {current_stage})
- lot: {alarm['lot_id']}
- 알람 ID: {alarm['id']}
- 추정 장비 ID: {equipment_id}

## Tier 1 이상 탐지
- 이상 점수: {tier1['score']}

## Tier 2 원인 분석 (기여도 순)
{cause_lines}

위 정보를 바탕으로 yield_loss와 downstream_dependencies를 산출해 주세요.
WIP·downstream·yield·PM 컨텍스트는 도구를 호출해 자율적으로 수집하세요."""


CONDUCTOR_SYSTEM_PROMPT = """당신은 반도체 공정 영향 평가 전문가입니다.
Central Planner가 이미 필요한 정보(WIP·downstream·yield·PM)를 모두 수집해 [수집된 컨텍스트]에 정리해 두었습니다.
당신은 추가 도구 호출 없이 그 컨텍스트만 사용해 산출하세요.

[최종 산출물]
- yield_loss: 본 이상으로 인한 예상 수율 손실(%p, 소수 한 자리)
- downstream_dependencies: 영향 받는 후공정 (current 제외) - stage / delta / tag / kind"""


def _execute_tier3_plan(plan_tier3: dict, trace_calls: list) -> str:
    """Planner가 지정한 tool들을 직접 호출하고 컨텍스트로 변환"""
    blocks = []
    if plan_tier3.get("alarm_id"):
        r = dispatch_tool("query_wip_status", {"alarm_id": plan_tier3["alarm_id"]})
        trace_calls.append({"name": "query_wip_status", "args": {"alarm_id": plan_tier3["alarm_id"]}})
        blocks.append(f"[query_wip_status: {plan_tier3['alarm_id']!r}]\n{r}")
    for stage in plan_tier3.get("downstream_stages", []):
        r = dispatch_tool("get_downstream_steps", {"current_stage": stage})
        trace_calls.append({"name": "get_downstream_steps", "args": {"current_stage": stage}})
        blocks.append(f"[get_downstream_steps: {stage!r}]\n{r}")
    for proc in plan_tier3.get("yield_processes", []):
        r = dispatch_tool("get_yield_baseline", {"process": proc})
        trace_calls.append({"name": "get_yield_baseline", "args": {"process": proc}})
        blocks.append(f"[get_yield_baseline: {proc!r}]\n{r}")
    for eq_id in plan_tier3.get("equipment_ids", []):
        r = dispatch_tool("get_pm_history", {"equipment_id": eq_id})
        trace_calls.append({"name": "get_pm_history", "args": {"equipment_id": eq_id}})
        blocks.append(f"[get_pm_history: {eq_id!r}]\n{r}")
    return "\n\n".join(blocks) if blocks else "(planner가 정보 수집 지시 없음)"


def _run_impact_conductor(
    alarm: dict, tier1: Tier1, tier2: Tier2, plan: dict, trace: dict | None
) -> Tier3:
    tool_log: list[dict] = []
    knowledge = _execute_tier3_plan(plan.get("tier3", {}), tool_log)

    cause_lines = "\n".join(
        f"- {c['name']} ({c['pct']}%): {c['evidence'][:120]}" for c in tier2["causes"]
    )
    current_stage = _stage_from_alarm(alarm)
    user_prompt = f"""## 이상 알람
- 공정: {alarm['title']} (current_stage: {current_stage})

## Tier 1: 이상 점수 {tier1['score']}

## Tier 2 원인 분석
{cause_lines}

## 수집된 컨텍스트 (Planner 지정)
{knowledge}

위 컨텍스트만 사용해 yield_loss와 downstream_dependencies를 산출하세요."""

    resp = client().chat.completions.create(
        model=SUBAGENT_MODEL,
        messages=[
            {"role": "system", "content": CONDUCTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "tier3_part", "schema": LLM_PART_SCHEMA, "strict": True},
        },
    )
    llm_out = json.loads(resp.choices[0].message.content)

    current_dep = {
        "stage": current_stage,
        "delta": f"+{tier1['score']}",
        "tag": "현재",
        "kind": "current",
    }
    if trace is not None:
        trace["tool_calls"] = tool_log
        trace["iterations"] = 0
        trace["llm_calls"] = 1
        trace["mode"] = "conductor"

    return {
        "yield_loss": round(float(llm_out["yield_loss"]), 1),
        "dependencies": [current_dep] + llm_out["downstream_dependencies"],
        "impact_lots": get_affected_wip(alarm["id"]),
    }


@traceable(name="Tier3_Impact_Agent", run_type="chain")
def run_impact(
    alarm: dict,
    tier1: Tier1,
    tier2: Tier2,
    trace: dict | None = None,
    plan: dict | None = None,
) -> Tier3:
    """Tier 3 영향 평가. plan 제공 시 conductor 모드(LLM 1회), 아니면 autonomous loop."""
    if plan is not None:
        return _run_impact_conductor(alarm, tier1, tier2, plan, trace)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _initial_user_prompt(alarm, tier1, tier2)},
    ]
    tool_call_log: list[dict] = []
    iterations = 0

    for iterations in range(1, MAX_TOOL_ITERATIONS + 1):
        resp = client().chat.completions.create(
            model=SUBAGENT_MODEL,
            messages=messages,
            tools=TOOLS_IMPACT,
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

    messages.append({
        "role": "user",
        "content": "수집한 정보를 종합해 yield_loss와 downstream_dependencies를 JSON 스키마에 맞춰 출력해 주세요.",
    })
    final = client().chat.completions.create(
        model=SUBAGENT_MODEL,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "tier3_part", "schema": LLM_PART_SCHEMA, "strict": True},
        },
    )
    llm_out = json.loads(final.choices[0].message.content)

    # current 항목은 결정론적 (Tier 1 score 기반)
    current_dep = {
        "stage": _stage_from_alarm(alarm),
        "delta": f"+{tier1['score']}",
        "tag": "현재",
        "kind": "current",
    }

    if trace is not None:
        trace["tool_calls"] = tool_call_log
        trace["iterations"] = iterations
        trace["llm_calls"] = iterations + 1
        trace["mode"] = "autonomous"

    return {
        "yield_loss": round(float(llm_out["yield_loss"]), 1),
        "dependencies": [current_dep] + llm_out["downstream_dependencies"],
        "impact_lots": get_affected_wip(alarm["id"]),
    }
