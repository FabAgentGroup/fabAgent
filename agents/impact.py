"""Tier 3 공정 간 영향 평가 에이전트

알람 + Tier 1 + Tier 2 결과와 RAG 지식을 바탕으로
- yield_loss: 예상 수율 손실 (LLM)
- dependencies: 공정 의존성 그래프 (current는 Tier 1에서 구성, downstream은 LLM)
- impact_lots: 영향 WIP (data.wip 결정론적 조회, LLM 환각 방지)

모델: GPT-5 mini (agents.llm.SUBAGENT_MODEL)
"""
import json

from agents.llm import SUBAGENT_MODEL, client
from agents.rag.store import load_document, search
from core.schema import Tier1, Tier2, Tier3
from data.wip import get_affected_wip

TOP_K_DOCS = 3

# LLM이 채울 부분만 스키마로 정의, downstream_dependencies는 current 제외 후공정만
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
이상이 발생한 공정 이후 단계로 영향이 어떻게 전파될지 평가합니다.

산출물:
1. yield_loss: 본 이상으로 인한 예상 수율 손실(%p, 소수 한 자리 이내)
2. downstream_dependencies: 영향 받는 후공정 목록
   - stage: 후공정 이름 (Etch, CMP 등)
   - delta: 정량 변화 표현 (예: "+18%")
   - tag: 사용자에게 보일 짧은 라벨 (예: "영향", "경미")
   - kind: "impacted" (직접 영향) 또는 "minor" (경미한 영향)

제공된 지식 문서에 기반해 추정하며, 문서에 없는 단계는 포함하지 않습니다.
영향이 큰 후공정부터 순서대로 나열합니다."""


def _stage_from_alarm(alarm: dict) -> str:
    """알람 title 첫 단어를 현재 공정명으로 사용 (예: 'Photo Step 이상' -> 'Photo')"""
    return alarm["title"].split()[0]


def _build_query(alarm: dict, tier2: Tier2) -> str:
    cause_names = " ".join(c["name"] for c in tier2["causes"])
    return f"{alarm['title']} 하류 후공정 영향 수율 {cause_names}"


def run_impact(alarm: dict, tier1: Tier1, tier2: Tier2) -> Tier3:
    doc_ids = search(_build_query(alarm, tier2), top_k=TOP_K_DOCS)
    knowledge = "\n\n".join(f"[{d}]\n{load_document(d)}" for d in doc_ids)

    cause_lines = "\n".join(
        f"- {c['name']} ({c['pct']}%): {c['evidence']}" for c in tier2["causes"]
    )
    user_prompt = f"""## 이상 알람
- 공정: {alarm['title']}
- lot: {alarm['lot_id']}

## Tier 1 이상 탐지
- 이상 점수: {tier1['score']}

## Tier 2 원인 분석
{cause_lines}

## 사내 지식 문서
{knowledge}

위 정보를 바탕으로 yield_loss와 downstream_dependencies를 산출해 주세요."""

    resp = client().chat.completions.create(
        model=SUBAGENT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "tier3_part", "schema": LLM_PART_SCHEMA, "strict": True},
        },
    )
    llm_out = json.loads(resp.choices[0].message.content)

    # current 항목은 Tier 1 score에서 결정론적으로 구성
    current_dep = {
        "stage": _stage_from_alarm(alarm),
        "delta": f"+{tier1['score']}",
        "tag": "현재",
        "kind": "current",
    }

    return {
        "yield_loss": round(float(llm_out["yield_loss"]), 1),
        "dependencies": [current_dep] + llm_out["downstream_dependencies"],
        "impact_lots": get_affected_wip(alarm["id"]),
    }
