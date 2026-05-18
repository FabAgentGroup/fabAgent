"""CRAG (Corrective Retrieval-Augmented Generation)

검색 결과의 관련성을 LLM이 자체 평가하고, 임계치 미달 시 쿼리를 재작성해 재검색합니다.
Yan et al., 2024 "Corrective Retrieval Augmented Generation" 패턴을 본 도메인에 적응.

흐름:
1. base retrieval (hybrid)
2. **grade**: 각 문서가 쿼리에 관련 있는지 LLM이 0~1 점수 부여
3. avg_score >= THRESHOLD 면 그대로 반환
4. 미만이면 **refine**: LLM이 동의어·관련 도메인 용어를 활용해 쿼리 재작성
5. 재검색 (max_retries 까지)

비용 최소화를 위해 grader/refiner는 gpt-4o-mini 사용.
환경변수 CRAG_ENABLED=false로 전체 비활성 가능 (실험 비교용).
"""
import json
import os

from agents.llm import client
from agents.rag.store import load_document, search

GRADER_MODEL = "gpt-4o-mini"
RELEVANCE_THRESHOLD = 0.5  # avg 점수 미만이면 refinement 시도
DEFAULT_MAX_RETRIES = 1

_GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "grades": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "score": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["index", "score", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["grades"],
    "additionalProperties": False,
}


def _llm_call(prompt: str, schema: dict | None = None):
    kwargs = {
        "model": GRADER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    if schema:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "out", "schema": schema, "strict": True},
        }
    return client().chat.completions.create(**kwargs)


def grade_retrieval(query: str, docs: list[dict]) -> list[dict]:
    """각 문서의 query 관련성을 0~1로 채점

    docs: [{"doc_id": str, "snippet": str}, ...]
    반환: [{"index": int, "score": float, "reason": str}, ...]
    """
    if not docs:
        return []
    doc_block = "\n\n".join(
        f"[doc_{i}] (id={d['doc_id']})\n{d['snippet'][:600]}" for i, d in enumerate(docs)
    )
    prompt = f"""당신은 반도체 공정 도메인의 retrieval 평가자입니다.
다음 쿼리에 대해 각 문서가 답변 생성에 얼마나 직접 기여할 수 있는지 평가하세요.

[쿼리]
{query}

[검색된 문서들]
{doc_block}

각 문서에 대해 0~1 점수(소수 둘째 자리)와 한 줄 reason을 JSON으로 응답:
{{"grades": [
  {{"index": 0, "score": 0.85, "reason": "쿼리의 핵심 증상·원인을 직접 기술"}},
  ...
]}}

[채점 기준]
- 0.0: 쿼리와 무관, 또는 쿼리가 의미 불명/무작위 입력
- 0.1~0.3: 도메인은 같으나 다른 주제 (예: 쿼리가 Photo인데 문서는 CMP)
- 0.4~0.6: 인접 주제 또는 일반론 (직접 답은 안 되지만 맥락은 됨)
- 0.7~0.9: 직접 관련 (구체적 사례·SOP·근거)
- 1.0: 쿼리 핵심 키워드를 모두 포함하고 답변 생성에 직접 기여

[중요]
- 쿼리가 의미 불명·무작위 단어·다른 도메인이면 모든 문서에 0.0 부여
- 도메인(반도체 공정)이 같다는 이유만으로 점수를 높이지 마세요
- 보수적으로 채점하세요 (의심스러우면 낮은 점수)"""
    try:
        resp = _llm_call(prompt, schema=_GRADE_SCHEMA)
        parsed = json.loads(resp.choices[0].message.content)
        return parsed.get("grades", [])
    except (json.JSONDecodeError, KeyError):
        return [{"index": i, "score": 0.5, "reason": "(grader parse failed)"} for i in range(len(docs))]


def refine_query(original_query: str, weak_docs: list[dict]) -> str:
    """약한 검색 결과를 보고 쿼리를 재작성"""
    weak_block = "\n".join(
        f"- [{d['doc_id']}] {d['snippet'][:200]}" for d in weak_docs
    )
    prompt = f"""원 쿼리가 적절한 문서를 찾지 못했습니다. 더 잘 작동할 쿼리로 한 줄 재작성하세요.

[원 쿼리]
{original_query}

[검색된 (관련성 낮은) 문서들]
{weak_block}

[재작성 규칙]
- 동의어·관련 도메인 용어 활용 (예: '렌즈 오염' → '헤이즈, 광학 표면 오염, projection lens contamination')
- 너무 좁거나 너무 넓지 않게 유지
- 한국어 + 영어 도메인 용어 혼용 가능
- 약 10~25 단어

재작성된 쿼리만 한 줄로 답하세요 (다른 설명 없이):"""
    resp = _llm_call(prompt)
    content = resp.choices[0].message.content or ""
    return content.strip().splitlines()[0] if content.strip() else original_query


def crag_search(
    query: str,
    top_k: int = 3,
    max_retries: int = DEFAULT_MAX_RETRIES,
    trace_list: list | None = None,
) -> dict:
    """CRAG: search → grade → (낮으면) refine → re-search

    반환: {"hits": [{"doc_id", "snippet", "relevance_score"}, ...],
           "crag_meta": {"retries": int, "final_query": str, "final_avg_score": float}}
    """
    current_query = query
    retries = 0
    last_docs: list[dict] = []
    last_grades: list[dict] = []
    avg_score = 0.0

    while True:
        doc_ids = search(current_query, top_k=top_k)
        docs = []
        for d in doc_ids:
            text = load_document(d)
            if not text:
                continue
            docs.append({"doc_id": d, "snippet": text[:600] + ("..." if len(text) > 600 else "")})

        if not docs:
            break

        grades = grade_retrieval(current_query, docs)
        avg_score = sum(g.get("score", 0.0) for g in grades) / max(len(grades), 1)
        last_docs = docs
        last_grades = grades

        if trace_list is not None:
            trace_list.append({
                "query": current_query,
                "retry": retries,
                "avg_score": round(avg_score, 3),
                "doc_ids": [d["doc_id"] for d in docs],
                "grades": [{"id": docs[g["index"]]["doc_id"], "score": g["score"]}
                           for g in grades if g.get("index", -1) < len(docs)],
            })

        if avg_score >= RELEVANCE_THRESHOLD or retries >= max_retries:
            break

        # 관련성 낮음 → query refinement
        current_query = refine_query(current_query, docs)
        retries += 1

    # docs와 grades 정렬 (index 기준)
    score_by_idx = {g["index"]: g.get("score", 0.0) for g in last_grades}
    hits = [
        {"doc_id": d["doc_id"], "snippet": d["snippet"], "relevance_score": round(score_by_idx.get(i, 0.0), 2)}
        for i, d in enumerate(last_docs)
    ]
    return {
        "hits": hits,
        "crag_meta": {
            "retries": retries,
            "final_query": current_query,
            "final_avg_score": round(avg_score, 3),
            "refined": retries > 0,
        },
    }


def crag_enabled() -> bool:
    """환경변수로 CRAG on/off 토글 (기본 on)"""
    return os.getenv("CRAG_ENABLED", "true").lower() not in ("false", "0", "no")
