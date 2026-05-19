"""Cross-encoder Re-ranking - hybrid retrieval 결과를 정밀 재정렬

bi-encoder(임베딩 기반)는 query와 doc을 따로 인코딩하지만, cross-encoder는
(query, doc) 쌍을 통째로 입력해 정밀한 관련성 점수를 산출한다.
계산 비용은 크지만 top-K 후보(보통 10~20)만 재정렬하므로 production에 적합.

모델 옵션 (환경변수 RERANK_MODEL):
- BAAI/bge-reranker-base (기본, 영어 학습, 한국어 일부 지원, ~280MB)
- Dongjin-kr/ko-reranker (한국어 특화, ~280MB) - D6 후속 평가용
"""
import os
from functools import lru_cache

DEFAULT_MODEL = "BAAI/bge-reranker-base"


def _model_name() -> str:
    return os.getenv("RERANK_MODEL", DEFAULT_MODEL)


@lru_cache(maxsize=2)
def _build_reranker(model_name: str):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name)


def rerank(query: str, doc_ids: list[str], top_k: int = 3) -> list[str]:
    """후보 doc 리스트를 cross-encoder 점수 내림차순으로 재정렬해 top-K 반환"""
    if not doc_ids:
        return []

    from agents.rag.store import load_document

    docs = [load_document(d) for d in doc_ids]
    pairs = [[query, doc] for doc in docs]
    model = _build_reranker(_model_name())
    scores = model.predict(pairs)
    ranked = sorted(zip(doc_ids, scores), key=lambda x: -x[1])
    return [doc_id for doc_id, _ in ranked[:top_k]]
