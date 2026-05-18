"""search_knowledge tool - RAG 검색 (CRAG self-correction 포함)

기본은 CRAG 활성화 (검색 → 관련성 평가 → 미달 시 쿼리 재작성 + 재검색).
환경변수 CRAG_ENABLED=false 로 비활성 가능 (실험 비교용).

전역 trace list (`LAST_CRAG_TRACE`)에 CRAG 메타가 누적되어 agent 호출별 관찰 가능.
"""
from agents.rag.crag import crag_enabled, crag_search
from agents.rag.store import load_document, search

# 호출 단위로 reset 후 agent loop 동안 CRAG 동작을 추적
LAST_CRAG_TRACE: list[dict] = []


def reset_crag_trace() -> list[dict]:
    """이전 trace 회수 후 새로 시작 - 실험·agent trace 수집용"""
    global LAST_CRAG_TRACE
    out = LAST_CRAG_TRACE
    LAST_CRAG_TRACE = []
    return out


def search_knowledge(query: str, top_k: int = 3) -> dict:
    """사내 지식 문서를 hybrid 검색 + CRAG 자체 평가

    CRAG 활성 시 반환에 relevance_score, refined 여부 포함.
    """
    if crag_enabled():
        result = crag_search(query, top_k=top_k, trace_list=LAST_CRAG_TRACE)
        return result
    # CRAG 비활성: 기존 hybrid search 그대로
    doc_ids = search(query, top_k=top_k)
    hits = []
    for d in doc_ids:
        text = load_document(d)
        hits.append({"doc_id": d, "snippet": text[:400] + ("..." if len(text) > 400 else "")})
    return {"hits": hits}


SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": (
            "사내 지식 문서(과거 사례 INC, 실패 모드 FMEA, 표준 절차 SOP, 공정 흐름 FLOW)를 "
            "hybrid 검색합니다. CRAG self-correction이 활성화되어 있어 검색 결과의 관련성이 "
            "낮으면 자동으로 쿼리를 재작성해 재검색합니다. 반환 값에 relevance_score(0~1)가 포함되어 "
            "원인 분석·대응 권고에 신뢰도와 함께 활용할 수 있습니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색할 키워드/질의문 (예: 'CMP 슬러리 유량 이상')",
                },
                "top_k": {
                    "type": "integer",
                    "description": "반환할 문서 수 (기본 3)",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
}
