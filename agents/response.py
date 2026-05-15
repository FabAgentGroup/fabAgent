"""Tier 4 대응 권고 에이전트

알람 + Tier 1/2/3 결과와 RAG 지식을 바탕으로
- immediate: 즉시 조치 목록 (LLM)
- longterm: 중장기 조치 목록 (LLM)
- refs: 근거 자료 (RAG로 검색된 문서 ID와 제목, 결정론적)

모델: GPT-5 mini (agents.llm.SUBAGENT_MODEL)
"""
import json

from agents.llm import SUBAGENT_MODEL, client
from agents.rag.store import load_document, search
from core.schema import Tier1, Tier2, Tier3, Tier4

TOP_K_DOCS = 4

# LLM이 채울 부분만 스키마로, refs는 검색 결과에서 결정론적으로 구성
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
    },
    "required": ["immediate", "longterm"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 반도체 공정 대응 권고 전문가입니다.
이상 알람과 그동안의 분석(탐지·원인·영향)을 종합하여 구체적인 조치를 권고합니다.

산출물:
1. immediate: 즉시 조치 (시간 단위 안에 수행, 예: PM 투입, 후공정 hold, 일정 재조정)
2. longterm: 중장기 조치 (재발 방지, PM 주기 조정, 모니터링 강화, 절차 개정)

각 조치는 text(권고 본문)와 meta(부가 정보, 예: "예상 2시간", "Etch hold", "PPC 협조")로 구성합니다.
meta가 필요 없으면 null로 둡니다. 제공된 지식 문서를 근거로 작성하고, 근거가 약한 권고는 포함하지 않습니다."""


def _doc_description(doc_id: str) -> str:
    """문서 첫 줄(# 제목)에서 ID 다음 부분을 desc로 추출"""
    text = load_document(doc_id)
    if not text:
        return doc_id
    first_line = text.split("\n", 1)[0].lstrip("# ").strip()
    for sep in (" — ", " - "):
        if sep in first_line:
            return first_line.split(sep, 1)[1].strip()
    return first_line


def _build_query(alarm: dict, tier2: Tier2) -> str:
    causes = " ".join(c["name"] for c in tier2["causes"])
    return f"{alarm['title']} 대응 PM 조치 보류 재조정 모니터링 {causes}"


def run_response(alarm: dict, tier1: Tier1, tier2: Tier2, tier3: Tier3) -> Tier4:
    doc_ids = search(_build_query(alarm, tier2), top_k=TOP_K_DOCS)
    knowledge = "\n\n".join(f"[{d}]\n{load_document(d)}" for d in doc_ids)

    cause_lines = "\n".join(
        f"- {c['name']} ({c['pct']}%)" for c in tier2["causes"]
    )
    impact_lots_text = ", ".join(
        f"{l['label']} {l['lots']}lot/{l['wafers']}장" for l in tier3["impact_lots"]
    )
    user_prompt = f"""## 이상 알람
- 공정: {alarm['title']}
- lot: {alarm['lot_id']}

## Tier 1 이상 탐지
- 이상 점수: {tier1['score']}

## Tier 2 원인 (기여도 순)
{cause_lines}

## Tier 3 영향
- 예상 수율 손실: {tier3['yield_loss']} %p
- 영향 WIP: {impact_lots_text}

## 사내 지식 문서
{knowledge}

위 분석을 종합해 immediate와 longterm 조치를 권고해 주세요."""

    resp = client().chat.completions.create(
        model=SUBAGENT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "tier4_part", "schema": LLM_PART_SCHEMA, "strict": True},
        },
    )
    llm_out = json.loads(resp.choices[0].message.content)

    refs = [{"id": d, "desc": _doc_description(d)} for d in doc_ids]

    return {
        "immediate": llm_out["immediate"],
        "longterm": llm_out["longterm"],
        "refs": refs,
    }
