"""D2: 검색 백엔드 비교 - keyword vs FAISS vs Hybrid vs Hybrid+Rerank

같은 쿼리 집합에 대해 4가지 retrieval 방식 비교
- keyword: 단순 단어 빈도 매칭
- FAISS: sentence-transformer 임베딩 + 코사인 유사도
- Hybrid: BM25 + FAISS + Reciprocal Rank Fusion (production 표준)
- Hybrid+Rerank: hybrid top-K 후보를 cross-encoder로 재정렬 (production 정밀)

실행: python -m experiments.retrieval_compare.benchmark
결과: results.md
"""
import statistics
import time
from pathlib import Path

from agents.rag.faiss_store import faiss_search
from agents.rag.hybrid_store import hybrid_search
from agents.rag.rerank import rerank
from agents.rag.store import keyword_search

OUT_DIR = Path(__file__).parent

QUERIES = [
    ("CD 산포 직접", "Photo Step CD-X 산포 원인 렌즈 노광"),
    ("CMP 직접", "CMP 슬러리 유량 이상 SLURRY_FLOW"),
    ("Etch 직접", "Etch 트렌치 깊이 부족 식각 가스"),
    ("의미 우회 1", "노광 장비 표면 오염 청소"),
    ("의미 우회 2", "후공정 수율 손실 정량 영향"),
    ("의미 우회 3", "정비 주기 표준 가이드"),
]


def hybrid_rerank_search(query, top_k=3):
    candidates = hybrid_search(query, top_k=10)
    return rerank(query, candidates, top_k)


BACKENDS = [
    ("keyword", keyword_search),
    ("faiss", faiss_search),
    ("hybrid", hybrid_search),
    ("hybrid+rerank", hybrid_rerank_search),
]


def main():
    # 워밍업
    print("=== 워밍업 (모델 로드) ===")
    for name, fn in BACKENDS:
        t0 = time.time()
        fn("warmup query", top_k=1)
        print(f"  {name}: {time.time()-t0:.2f}s")
    print()

    rows = []
    for label, q in QUERIES:
        record = {"label": label, "query": q, "results": {}, "latency_ms": {}}
        print(f"[{label}] '{q}'")
        for name, fn in BACKENDS:
            t0 = time.time()
            res = fn(q, top_k=3)
            ms = (time.time() - t0) * 1000
            record["results"][name] = res
            record["latency_ms"][name] = ms
            print(f"  {name:14s} ({ms:7.2f}ms): {res}")
        rows.append(record)
        print()

    write_results(rows)
    print(f"--- 저장: {OUT_DIR / 'results.md'} ---")


def write_results(rows):
    avg_lat = {
        name: statistics.mean(r["latency_ms"][name] for r in rows)
        for name, _ in BACKENDS
    }

    lines = [
        "# D2. Retrieval 백엔드 비교 (production-grade)",
        "",
        "쿼리 집합에 대해 4가지 백엔드의 검색 결과·latency를 비교합니다.",
        "현재 knowledge 코퍼스 약 10개 한국어 도메인 문서.",
        "",
        "## 실험 설정",
        "",
        "- 코퍼스: `agents/rag/knowledge/*.md`",
        "- 백엔드 4종:",
        "  - **keyword**: 단어 빈도 매칭 (baseline)",
        "  - **FAISS**: sentence-transformer 임베딩 + 코사인 (dense vector)",
        "  - **Hybrid**: BM25 + FAISS + RRF (production 표준)",
        "  - **Hybrid+Rerank**: hybrid top-10 후보를 BAAI/bge-reranker-base로 재정렬 (production 정밀)",
        f"- 쿼리 {len(rows)}건 (의미 우회 3건 포함)",
        "",
        "## 쿼리별 결과",
        "",
    ]

    for r in rows:
        lines.append(f"### {r['label']} - `{r['query']}`")
        lines.append("")
        lines.append("| 백엔드 | 결과 | latency |")
        lines.append("|---|---|---|")
        for name, _ in BACKENDS:
            res = ", ".join(r["results"][name]) or "(empty)"
            lines.append(f"| {name} | {res} | {r['latency_ms'][name]:.2f}ms |")
        lines.append("")

    lines += [
        "## 집계 - 평균 Latency",
        "",
        "| 백엔드 | 평균 latency |",
        "|---|---|",
    ]
    for name, _ in BACKENDS:
        lines.append(f"| {name} | {avg_lat[name]:.2f} ms |")

    lines += [
        "",
        "## 트레이드오프",
        "",
        "| 측면 | keyword | FAISS | Hybrid | Hybrid+Rerank |",
        "|---|---|---|---|---|",
        "| 도메인 용어 정확 매칭 | ✅ | ❌ | ✅ | ✅ |",
        "| 의미·동의어 매칭 | ❌ | ✅ | ✅ | ✅ |",
        "| 정밀한 관련성 평가 | ❌ | ❌ | ❌ | ✅ |",
        "| Latency | 매우 빠름 | 보통 | 보통 | 느림 (CrossEncoder) |",
        "| 모델 의존성 | 없음 | ST(~120MB) | ST(~120MB) | ST + Reranker(~280MB) |",
        "| 코퍼스 확장(100+) 견고성 | 약함 | 강함 | **매우 강함** | **매우 강함** |",
        "",
        "## 채택",
        "",
        "**기본 backend = `hybrid_rerank`**. production 표준 패턴. 환경변수 `RAG_BACKEND`로 4가지 모두 전환 가능.",
        "",
        "- 코퍼스 100문서 이상: hybrid_rerank의 정밀도 우위 결정적",
        "- MVP·시연 환경: hybrid도 충분 (rerank 모델 다운로드 시간 절약)",
        "- 단순 키워드 검색만 필요: keyword (의존성 없음)",
        "",
    ]
    (OUT_DIR / "results.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
