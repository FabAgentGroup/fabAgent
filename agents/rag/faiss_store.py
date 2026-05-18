"""FAISS 벡터 검색 백엔드

sentence-transformers로 knowledge 문서를 임베딩하고 FAISS IndexFlatIP로 코사인
유사도 검색을 수행한다. 키워드 매칭(store.py)과 동일 시그니처로 교체 가능.

모델: paraphrase-multilingual-MiniLM-L12-v2 (한국어 포함 50+ 언어)
"""
from functools import lru_cache

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from agents.rag.store import _knowledge_docs

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def _build_index():
    """knowledge 문서를 임베딩하고 FAISS index 구축, 첫 호출 시 1회"""
    model = SentenceTransformer(MODEL_NAME)
    docs = _knowledge_docs()
    doc_ids = list(docs.keys())
    texts = list(docs.values())
    embeddings = model.encode(texts, normalize_embeddings=True)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # 내적 = 코사인 (normalize 됨)
    index.add(embeddings.astype(np.float32))
    return model, index, doc_ids


def faiss_search(query: str, top_k: int = 3) -> list[str]:
    """쿼리와 의미적으로 유사한 문서 ID를 코사인 유사도 내림차순으로 반환"""
    model, index, doc_ids = _build_index()
    q_emb = model.encode([query], normalize_embeddings=True).astype(np.float32)
    _, idx = index.search(q_emb, top_k)
    return [doc_ids[i] for i in idx[0] if i >= 0]
