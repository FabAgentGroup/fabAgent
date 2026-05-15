"""RAG 도메인 지식 검색 (M2에서 구현)

knowledge/ 의 마크다운 문서(INC-*, FMEA-*, SOP-* 등)를 검색해
원인 분석(Tier 2)·대응 권고(Tier 4) 에이전트에 근거를 제공

문서가 5~6개뿐이라 벡터DB는 오버스펙
citation ID로 직접 로드하거나 간단한 키워드 매칭이면 충분
"""
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def load_document(doc_id: str) -> str:
    """citation ID(예: 'INC-2024-0312')로 knowledge 문서 본문을 로드, 없으면 빈 문자열"""
    path = KNOWLEDGE_DIR / f"{doc_id}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def search(query: str, top_k: int = 3) -> list[str]:
    """쿼리와 관련된 문서 ID를 반환 (M2: 키워드 매칭 기반)"""
    raise NotImplementedError("M2: RAG 검색 구현 예정")
