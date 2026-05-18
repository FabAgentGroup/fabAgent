"""search_knowledge tool - RAG 검색을 LLM이 자율 호출

기존 agents.rag.store.search()를 tool 인터페이스로 노출
LLM이 추가 정보가 필요하다고 판단할 때 호출
"""
from agents.rag.store import load_document, search


def search_knowledge(query: str, top_k: int = 3) -> dict:
    """사내 지식 문서(INC/FMEA/SOP/FLOW)를 의미 + 키워드 hybrid 검색

    반환: {"hits": [{"doc_id": ..., "snippet": 첫 400자}, ...]}
    """
    doc_ids = search(query, top_k=top_k)
    hits = []
    for doc_id in doc_ids:
        text = load_document(doc_id)
        snippet = text[:400] + ("..." if len(text) > 400 else "")
        hits.append({"doc_id": doc_id, "snippet": snippet})
    return {"hits": hits}


SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": (
            "사내 지식 문서(과거 사례 INC, 실패 모드 FMEA, 표준 절차 SOP, 공정 흐름 FLOW)를 "
            "hybrid 검색해 관련 문서의 doc_id와 본문 요약을 반환합니다. "
            "원인 분석·대응 권고에 필요한 도메인 컨텍스트를 가져올 때 사용하세요."
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
