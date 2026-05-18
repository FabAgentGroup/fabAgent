"""Cross-encoder Re-ranking - hybrid retrieval 결과를 정밀 재정렬

bi-encoder(임베딩 기반)는 query와 doc을 따로 인코딩하지만, cross-encoder는
(query, doc) 쌍을 통째로 입력해 정밀한 관련성 점수를 산출한다.
계산 비용은 크지만 top-K 후보(보통 10~20)만 재정렬하므로 production에 적합.

모델: BAAI/bge-reranker-base (한국어 일부 지원, ~280MB)
"""
from functools import lru_cache

MODEL_NAME = "BAAI/bge-reranker-base"


@lru_cache(maxsize=1)
def _build_reranker():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(MODEL_NAME)


def rerank(query: str, doc_ids: list[str], top_k: int = 3) -> list[str]:
    """후보 doc 리스트를 cross-encoder 점수 내림차순으로 재정렬해 top-K 반환"""
    if not doc_ids:
        return []

    from agents.rag.store import load_document

    docs = [load_document(d) for d in doc_ids]
    pairs = [[query, doc] for doc in docs]
    model = _build_reranker()
    scores = model.predict(pairs)
    ranked = sorted(zip(doc_ids, scores), key=lambda x: -x[1])
    return [doc_id for doc_id, _ in ranked[:top_k]]
