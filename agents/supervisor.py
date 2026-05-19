"""Supervisor Agent - LLM-driven dynamic workflow routing

Tier 2 원인 분석 결과를 보고 후속 행동을 LLM이 동적으로 결정합니다.
threshold 기반 conditional edge(orchestrator)와 다른 점:
- 사람이 정의한 임계치가 아니라 LLM이 맥락을 보고 판단
- 기여도·증상·영향 lot·공정 critical 여부를 종합 고려

가용 action:
- proceed_full: 표준 경로 (Tier 3 -> Tier 4)
- fast_track: 원인이 명확해 영향 평가 skip, Tier 4 직진 (latency·cost 절감)
- escalate: 고위험 - 정상 진행 + human review 플래그

severity 분류: low / medium / high / critical

비용 절감: 의사결정만 하는 소작업이라 SUPERVISOR_MODEL = gpt-4o-mini
환경변수 SUPERVISOR_ENABLED=false 면 항상 proceed_full (Supervisor 호출 자체 skip)
"""
import json
import os

from langsmith import traceable

from agents.llm import client
from core.schema import Tier1, Tier2

SUPERVISOR_MODEL = "gpt-4o-mini"

ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["proceed_full", "fast_track", "escalate"],
        },
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
        "reasoning": {"type": "string"},
    },
    "required": ["action", "severity", "reasoning"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 반도체 fab의 incident response supervisor 에이전트입니다.
원인 분석(Tier 2) 결과를 보고 후속 단계 진행 방식을 결정합니다.

[가용 action]
- proceed_full: 표준 - Tier 3(영향평가) → Tier 4(대응권고) 순차 진행 (대부분의 경우)
- fast_track: 원인이 1~2개로 명확하고 즉시 조치만 필요 - Tier 3 skip, Tier 4 직진 (latency·cost 절감)
- escalate: 고위험 - 정상 진행하되 human review 플래그 (조치 전 운영자 추가 검토 강제)

[severity 분류]
- low: 사소한 변동, 자동 처리 가능
- medium: 표준 대응으로 충분
- high: 영향 큼, 빠른 조치 필요
- critical: 라인 정지 검토 수준

[판단 기준]
- 원인 1개가 기여도 70%+ 단독 우세 + medium/low severity → fast_track 후보
- 원인 다수(3개+) 분포 또는 high/critical severity → proceed_full
- critical severity, downstream 영향이 클 것으로 추정 → escalate
- 일반적으로 proceed_full이 안전한 기본값

[중요] reasoning은 한 문장으로 결정 근거를 명시 (예: "단일 원인 80% 단독 우세, medium severity → fast_track")"""


def _build_user_prompt(alarm: dict, tier1: Tier1, tier2: Tier2) -> str:
    causes = "\n".join(
        f"- [{c['pct']}%] {c['name']}: {c['evidence'][:120]}"
        for c in tier2["causes"]
    )
    return f"""## 이상 알람
- 공정: {alarm['title']}
- lot: {alarm['lot_id']}

## Tier 1 이상 탐지
- 이상 점수: {tier1['score']}

## Tier 2 원인 분석 결과
{causes}

후속 action·severity·reasoning을 결정해 주세요."""


def supervisor_enabled() -> bool:
    return os.getenv("SUPERVISOR_ENABLED", "true").lower() not in ("false", "0", "no")


@traceable(name="Supervisor_Agent", run_type="chain")
def run_supervisor(alarm: dict, tier1: Tier1, tier2: Tier2) -> dict:
    """후속 workflow action을 LLM이 결정

    반환: {"action": "proceed_full"|"fast_track"|"escalate",
           "severity": "low"|"medium"|"high"|"critical",
           "reasoning": str}
    """
    if not supervisor_enabled():
        return {"action": "proceed_full", "severity": "medium",
                "reasoning": "(Supervisor 비활성 - 항상 표준 경로)"}

    resp = client().chat.completions.create(
        model=SUPERVISOR_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(alarm, tier1, tier2)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "supervisor", "schema": ACTION_SCHEMA, "strict": True},
        },
    )
    return json.loads(resp.choices[0].message.content)
