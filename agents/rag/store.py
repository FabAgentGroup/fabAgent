"""RAG 도메인 지식 검색 - 키워드 매칭 + FAISS 벡터 백엔드 디스패치

knowledge/ 의 마크다운 문서(INC-*, FMEA-*, SOP-* 등)를 검색해
원인 분석(Tier 2)·대응 권고(Tier 4) 에이전트에 근거를 제공한다.

기본은 키워드 매칭 (작은 코퍼스에 빠르고 정확)
환경 변수 RAG_BACKEND=faiss 설정 시 sentence-transformer + FAISS 벡터 검색으로
교체 (의미 유사도, 동의어 처리에 우위, 코퍼스 확장 시 유리)

파일명이 곧 citation ID (예: INC-2024-0312.md -> "INC-2024-0312")
"""
import os
import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def load_document(doc_id: str) -> str:
    """citation ID로 knowledge 문서 본문을 로드, 없으면 빈 문자열"""
    path = KNOWLEDGE_DIR / f"{doc_id}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _knowledge_docs() -> dict[str, str]:
    """knowledge/ 의 모든 문서를 {doc_id: 본문}으로 로드, README는 제외"""
    docs = {}
    for path in KNOWLEDGE_DIR.glob("*.md"):
        if path.stem == "README":
            continue
        docs[path.stem] = path.read_text(encoding="utf-8")
    return docs


def keyword_search(query: str, top_k: int = 3) -> list[str]:
    """키워드 매칭 - 쿼리 단어가 문서 본문에 등장하는 빈도 합계로 랭킹"""
    keywords = [w for w in re.split(r"\W+", query.lower()) if len(w) >= 2]
    scored = []
    for doc_id, text in _knowledge_docs().items():
        low = text.lower()
        hits = sum(low.count(kw) for kw in keywords)
        if hits > 0:
            scored.append((doc_id, hits))
    scored.sort(key=lambda x: -x[1])
    return [doc_id for doc_id, _ in scored[:top_k]]


def search(query: str, top_k: int = 3) -> list[str]:
    """기본 검색 진입점, 환경변수 RAG_BACKEND로 백엔드 전환

    backend 옵션:
    - keyword (기본): 단순 키워드 매칭
    - faiss: sentence-transformer + FAISS dense vector
    - hybrid: BM25 + FAISS + Reciprocal Rank Fusion (production 표준)
    - hybrid_rerank: hybrid 결과를 cross-encoder로 재정렬 (최고 정확도)
    """
    # 기본값: hybrid (BM25+FAISS+RRF)
    # 근거: experiments/rag_paradigm 실측에서 본 코퍼스 규모(~10문서)에 가장 적합
    # 코퍼스 100+ 확장 시 hybrid_rerank 재평가 권장
    backend = os.getenv("RAG_BACKEND", "hybrid").lower()
    if backend == "faiss":
        from agents.rag.faiss_store import faiss_search

        return faiss_search(query, top_k)
    if backend == "hybrid":
        from agents.rag.hybrid_store import hybrid_search

        return hybrid_search(query, top_k)
    if backend == "hybrid_rerank":
        from agents.rag.hybrid_store import hybrid_search
        from agents.rag.rerank import rerank

        candidates = hybrid_search(query, top_k=10)
        return rerank(query, candidates, top_k)
    return keyword_search(query, top_k)
