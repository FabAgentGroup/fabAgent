"""Tier 2 원인 분석 에이전트

알람 컨텍스트 + Tier 1 결과 + RAG 지식 문서를 근거로
추정 원인을 기여도(%)와 근거, citation과 함께 산출
모델: GPT-5 mini (agents.llm.SUBAGENT_MODEL)
"""
import json

from agents.llm import SUBAGENT_MODEL, client
from agents.rag.store import load_document, search
from core.schema import Tier1, Tier2

TOP_K_DOCS = 3

# structured output용 Tier2 JSON 스키마
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

SYSTEM_PROMPT = """당신은 반도체 Photo 공정의 원인 분석 전문가입니다.
주어진 이상 알람과 탐지 결과, 사내 지식 문서를 근거로 가장 가능성 높은 원인을
2~3개 추정합니다. 각 원인은 기여도(pct, %)를 가지며 합이 100에 가깝도록 합니다.
근거(evidence)는 제공된 문서 내용에 기반해 구체적으로 작성하고, citations에는
근거가 된 문서 ID만 정확히 기입합니다. 제공되지 않은 문서는 인용하지 않습니다.
기여도가 높은 원인부터 순서대로 제시합니다."""


def _build_query(alarm: dict, tier1: Tier1) -> str:
    feature = alarm.get("feature") or ""
    return f"{alarm['title']} {feature} 원인 CD 산포 렌즈 노광 진동 표면 결함"


def run_cause(alarm: dict, tier1: Tier1) -> Tier2:
    doc_ids = search(_build_query(alarm, tier1), top_k=TOP_K_DOCS)
    knowledge = "\n\n".join(f"[{d}]\n{load_document(d)}" for d in doc_ids)

    sensors = ", ".join(f["name"] for f in tier1["features"])
    user_prompt = f"""## 이상 알람
- 공정: {alarm['title']}
- lot: {alarm['lot_id']}
- 이상 피처: {alarm.get('feature')} {alarm.get('feature_arrow') or ''}

## Tier 1 이상 탐지 결과
- 이상 점수: {tier1['score']}
- 기여 센서(Top): {sensors}

## 사내 지식 문서
{knowledge}

위 정보를 근거로 원인을 분석해 주세요."""

    resp = client().chat.completions.create(
        model=SUBAGENT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "tier2", "schema": TIER2_SCHEMA, "strict": True},
        },
    )
    return json.loads(resp.choices[0].message.content)
