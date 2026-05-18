"""D6 후속: 한국어 reranker(dongjin-kr/ko-reranker) 효과 평가

D6에서 BAAI/bge-reranker-base가 Hybrid 대비 효과 없음이 확인됨 (영어 학습 모델 + 한국어 코퍼스 mismatch).
한국어 특화 reranker로 결과가 뒤집히는지 검증.

평가 방법:
- D2의 6개 대표 쿼리(직접 + 의미 우회) 사용
- 3개 모드 × 6 쿼리 = 18 조합
  - hybrid (no rerank, baseline)
  - hybrid + BAAI/bge-reranker-base (영어 reranker)
  - hybrid + Dongjin-kr/ko-reranker (한국어 reranker)
- 각 모드의 top-3 결과를 CRAG grader(gpt-4o-mini)로 0~1 점수
- avg score / 모드별 비교 → 한국어 reranker가 의미 있는 개선 가져오는지 판단

실행: python -m experiments.reranker_compare.benchmark
"""
import os
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from agents.rag.crag import grade_retrieval
from agents.rag.hybrid_store import hybrid_search
from agents.rag.store import load_document

plt.rcParams["font.family"] = ["Apple SD Gothic Neo", "AppleGothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = Path(__file__).parent
CHART_DIR = OUT_DIR / "charts"

QUERIES = [
    ("CD 산포 직접", "Photo Step CD-X 산포 원인 렌즈 노광"),
    ("CMP 직접", "CMP 슬러리 유량 이상 SLURRY_FLOW"),
    ("Etch 직접", "Etch 트렌치 깊이 부족 식각 가스"),
    ("의미 우회 1", "노광 장비 표면 오염 청소"),
    ("의미 우회 2", "후공정 수율 손실 정량 영향"),
    ("의미 우회 3", "정비 주기 표준 가이드"),
]

MODES = [
    ("hybrid (no rerank)", None),
    ("BAAI/bge-reranker-base (영어)", "BAAI/bge-reranker-base"),
    ("Dongjin-kr/ko-reranker (한국어)", "Dongjin-kr/ko-reranker"),
]

TOP_K = 3
CANDIDATES = 10


def _rerank_with_model(query: str, candidates: list[str], model_name: str, top_k: int) -> list[str]:
    """모델 명시적 지정한 cross-encoder rerank"""
    os.environ["RERANK_MODEL"] = model_name
    # cache invalidation을 위해 rerank 모듈 함수 직접 호출
    from agents.rag.rerank import _build_reranker

    docs = [load_document(d) for d in candidates]
    pairs = [[query, doc] for doc in docs]
    scores = _build_reranker(model_name).predict(pairs)
    ranked = sorted(zip(candidates, scores), key=lambda x: -x[1])
    return [doc_id for doc_id, _ in ranked[:top_k]]


def collect():
    print("=== 워밍업 (BAAI + ko-reranker 로드) ===")
    t0 = time.time(); _rerank_with_model("warmup", ["FMEA-PH-007"], "BAAI/bge-reranker-base", 1); print(f"  BAAI: {time.time()-t0:.1f}s")
    t0 = time.time(); _rerank_with_model("warmup", ["FMEA-PH-007"], "Dongjin-kr/ko-reranker", 1); print(f"  ko-reranker: {time.time()-t0:.1f}s")

    rows = []
    for label, query in QUERIES:
        print(f"\n[{label}] '{query}'")
        # hybrid top-10 candidates 한 번 산출 (모든 모드 공통)
        candidates = hybrid_search(query, top_k=CANDIDATES)
        result_row = {"label": label, "query": query, "modes": {}}
        for mode_name, model in MODES:
            if model is None:
                # no rerank: hybrid top-3 그대로
                doc_ids = candidates[:TOP_K]
                rerank_ms = 0.0
            else:
                t0 = time.time()
                doc_ids = _rerank_with_model(query, candidates, model, TOP_K)
                rerank_ms = (time.time() - t0) * 1000
            docs = [{"doc_id": d, "snippet": load_document(d)[:600]} for d in doc_ids if load_document(d)]
            grades = grade_retrieval(query, docs)
            avg_score = sum(g.get("score", 0.0) for g in grades) / max(len(grades), 1)
            result_row["modes"][mode_name] = {
                "doc_ids": doc_ids,
                "avg_score": round(avg_score, 3),
                "rerank_ms": rerank_ms,
                "grades": grades,
            }
            print(f"  {mode_name:38s} avg={avg_score:.3f} ms={rerank_ms:.0f}  docs={doc_ids}")
        rows.append(result_row)
    return rows


def aggregate(rows):
    return {
        mode_name: {
            "avg_score": np.mean([r["modes"][mode_name]["avg_score"] for r in rows]),
            "rerank_ms": np.mean([r["modes"][mode_name]["rerank_ms"] for r in rows]),
        }
        for mode_name, _ in MODES
    }


def make_chart(agg, rows):
    CHART_DIR.mkdir(exist_ok=True)
    mode_names = [n for n, _ in MODES]
    short_names = ["No Rerank", "BAAI (EN)", "ko-reranker"]
    avg_scores = [agg[n]["avg_score"] for n in mode_names]
    colors = ["#94a3b8", "#3b82f6", "#ef4444"]

    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    bars = ax.bar(short_names, avg_scores, color=colors)
    for b, v in zip(bars, avg_scores):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.3f}",
                ha="center", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("평균 LLM relevance score (6 쿼리 평균)")
    ax.set_title("Reranker 비교 - 한국어 reranker가 D6 결과를 뒤집나?")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "reranker_comparison.png", dpi=150)
    plt.close(fig)


def write_results(rows, agg):
    base_score = agg["hybrid (no rerank)"]["avg_score"]
    en_score = agg["BAAI/bge-reranker-base (영어)"]["avg_score"]
    ko_score = agg["Dongjin-kr/ko-reranker (한국어)"]["avg_score"]

    lines = [
        "# D9 (D6 후속): 한국어 reranker 평가",
        "",
        "D6에서 `BAAI/bge-reranker-base`(영어 학습)가 Hybrid 대비 효과 없음이 확인되어,",
        "한국어 특화 reranker `Dongjin-kr/ko-reranker`로 재평가합니다.",
        "",
        "## 실험 설정",
        "",
        "- 쿼리: D2의 6개 대표 쿼리 (직접 3, 의미 우회 3)",
        "- 백엔드: hybrid (BM25+FAISS+RRF) top-10 후보를 두 reranker로 재정렬",
        "- 채점: CRAG grader (gpt-4o-mini)가 top-3 결과를 0~1로 평가",
        "- 비교: hybrid (no rerank) / BAAI (영어) / ko-reranker (한국어)",
        "",
        "## 결과 요약 (6 쿼리 평균)",
        "",
        "| 모드 | 평균 relevance | rerank 평균 latency | vs No Rerank |",
        "|---|---|---|---|",
        f"| hybrid (no rerank) | {base_score:.3f} | 0 ms | baseline |",
        f"| BAAI/bge-reranker-base (영어) | {en_score:.3f} | {agg['BAAI/bge-reranker-base (영어)']['rerank_ms']:.0f} ms | {(en_score - base_score):+.3f} |",
        f"| Dongjin-kr/ko-reranker (한국어) | {ko_score:.3f} | {agg['Dongjin-kr/ko-reranker (한국어)']['rerank_ms']:.0f} ms | {(ko_score - base_score):+.3f} |",
        "",
        "## 시각화",
        "",
        "![Reranker 비교](charts/reranker_comparison.png)",
        "",
        "## 쿼리별 상세",
        "",
        "| 쿼리 | hybrid | BAAI (EN) | ko-reranker (KO) |",
        "|---|---|---|---|",
    ]
    for r in rows:
        cells = [f"{r['modes'][n]['avg_score']:.2f}" for n, _ in MODES]
        lines.append(f"| {r['label']} | " + " | ".join(cells) + " |")

    # 채택 결론 - 데이터 기반 자동 판단
    ko_wins = ko_score > en_score and ko_score > base_score
    ko_helps = ko_score > base_score
    decision = "ko-reranker 채택" if ko_wins else ("ko-reranker 검토 가능 (no rerank보단 우위)" if ko_helps else "두 reranker 모두 본 코퍼스에선 hybrid에 미달")

    lines += [
        "",
        "## 핵심 인사이트",
        "",
        f"1. **No Rerank baseline**: {base_score:.3f}",
        f"2. **영어 reranker (BAAI)**: {en_score:.3f} (vs baseline {(en_score - base_score):+.3f}) - D6에서 본 패턴 재확인",
        f"3. **한국어 reranker (Dongjin-kr)**: {ko_score:.3f} (vs baseline {(ko_score - base_score):+.3f})",
        f"4. **결론**: {decision}",
        "",
        "## 채택",
        "",
    ]
    if ko_wins:
        lines += [
            f"**기본 reranker를 `Dongjin-kr/ko-reranker`로 권장** (`RERANK_MODEL` 환경변수).",
            f"한국어 도메인에서 영어 reranker 대비 +{(ko_score - en_score):.3f} 점수 우위, baseline 대비 +{(ko_score - base_score):.3f} 우위.",
        ]
    elif ko_helps:
        lines += [
            "**ko-reranker는 영어 reranker보단 의미 있는 개선** (baseline 대비 양수).",
            "하지만 hybrid 단독 대비 우위가 결정적이지 않아 기본 backend는 hybrid 유지.",
            "코퍼스 100+ 확장 시 ko-reranker로 재평가 권장 (환경변수 `RAG_BACKEND=hybrid_rerank` + `RERANK_MODEL=Dongjin-kr/ko-reranker`).",
        ]
    else:
        lines += [
            f"**두 reranker 모두 본 코퍼스에선 hybrid 단독에 미달** (BAAI {(en_score - base_score):+.3f}, ko-reranker {(ko_score - base_score):+.3f}).",
            "근본 원인: 코퍼스가 ~10문서로 작아 hybrid top-3이 이미 정답에 근접 → reranker가 더 좋게 정렬할 여지 부족.",
            "**D6 결론 (코퍼스 확장이 reranker 효용의 선결 조건) 재확인**. 코퍼스 100+ 시 재평가.",
        ]
    lines.append("")
    (OUT_DIR / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"--- 저장: {OUT_DIR / 'results.md'} ---")


def main():
    rows = collect()
    print("\n--- 집계 ---")
    agg = aggregate(rows)
    for n, v in agg.items():
        print(f"  {n}: avg={v['avg_score']:.3f}, ms={v['rerank_ms']:.0f}")
    make_chart(agg, rows)
    write_results(rows, agg)


if __name__ == "__main__":
    main()
