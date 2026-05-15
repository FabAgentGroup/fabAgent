"""RAG 도메인 지식 검색

knowledge/ 의 마크다운 문서(INC-*, FMEA-*, SOP-* 등)를 검색해
원인 분석(Tier 2)·대응 권고(Tier 4) 에이전트에 근거를 제공

문서가 소수라 벡터DB는 오버스펙, 키워드 매칭으로 충분
파일명이 곧 citation ID (예: INC-2024-0312.md -> "INC-2024-0312")
"""
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


def search(query: str, top_k: int = 3) -> list[str]:
    """쿼리와 관련된 문서 ID를 키워드 매칭으로 반환, 관련도 내림차순"""
    keywords = [w for w in re.split(r"\W+", query.lower()) if len(w) >= 2]
    scored = []
    for doc_id, text in _knowledge_docs().items():
        low = text.lower()
        hits = sum(low.count(kw) for kw in keywords)
        if hits > 0:
            scored.append((doc_id, hits))
    scored.sort(key=lambda x: -x[1])
    return [doc_id for doc_id, _ in scored[:top_k]]
