"""Hybrid Retrieval - BM25(sparse) + FAISS(dense) + Reciprocal Rank Fusion(RRF)

production RAG의 표준 패턴. 도메인 용어 정확 매칭(sparse) + 의미 유사도(dense)
양쪽 강점을 RRF로 결합

RRF 공식: score(d) = sum over rankings r of 1 / (k + rank_r(d))
- k=60 (Cormack et al. 2009 권장값)
- rank는 1부터 시작
- 결과: rank 1이 가장 큰 점수
"""
import re
from functools import lru_cache

from rank_bm25 import BM25Okapi

from agents.rag.store import _knowledge_docs

RRF_K = 60


def _tokenize(text: str) -> list[str]:
    """BM25용 토큰화, 한국어/영어 혼합 안전하게 단순 처리"""
    return [t for t in re.split(r"\W+", text.lower()) if len(t) >= 2]


@lru_cache(maxsize=1)
def _build_bm25():
    """knowledge 문서로 BM25 인덱스 구축, 첫 호출 시 1회"""
    docs = _knowledge_docs()
    doc_ids = list(docs.keys())
    corpus = [_tokenize(text) for text in docs.values()]
    bm25 = BM25Okapi(corpus)
    return bm25, doc_ids


def bm25_search(query: str, top_k: int = 10) -> list[str]:
    """BM25 점수 내림차순 top-K 문서 ID"""
    bm25, doc_ids = _build_bm25()
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(zip(doc_ids, scores), key=lambda x: -x[1])
    return [doc_id for doc_id, score in ranked[:top_k] if score > 0]


def hybrid_search(query: str, top_k: int = 3, candidates: int = 10) -> list[str]:
    """Hybrid = BM25 + FAISS dense, 결과를 Reciprocal Rank Fusion으로 결합

    각 백엔드에서 top-`candidates` 추출 후 RRF 점수 합산해서 최종 top-K 반환
    """
    from agents.rag.faiss_store import faiss_search

    bm25_ranked = bm25_search(query, top_k=candidates)
    dense_ranked = faiss_search(query, top_k=candidates)

    rrf_scores: dict[str, float] = {}
    for rank, doc_id in enumerate(bm25_ranked, start=1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
    for rank, doc_id in enumerate(dense_ranked, start=1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)

    merged = sorted(rrf_scores.items(), key=lambda x: -x[1])
    return [doc_id for doc_id, _ in merged[:top_k]]
