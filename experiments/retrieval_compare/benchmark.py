"""D2: FAISS 벡터 검색 vs 키워드 매칭 비교

같은 쿼리 집합에 대해
- keyword_search: 단순 단어 빈도 매칭
- faiss_search: sentence-transformer 임베딩 + FAISS 코사인 유사도

으로 검색해 결과·latency·의미 매칭 능력을 비교

실행: python -m experiments.retrieval_compare.benchmark
결과: results.md
"""
import statistics
import time
from pathlib import Path

from agents.rag.faiss_store import faiss_search
from agents.rag.store import keyword_search

OUT_DIR = Path(__file__).parent

# 키워드가 직접 일치하지 않아도 의미적으로 가까운 쿼리들 포함
QUERIES = [
    ("CD 산포 직접", "Photo Step CD-X 산포 원인 렌즈 노광"),
    ("CMP 직접", "CMP 슬러리 유량 이상 SLURRY_FLOW"),
    ("Etch 직접", "Etch 트렌치 깊이 부족 식각 가스"),
    ("의미 우회 1", "노광 장비 표면 오염 청소"),  # PM/clean이라는 단어 없이
    ("의미 우회 2", "후공정 수율 손실 정량 영향"),  # 직접 단어 매칭 약함
    ("의미 우회 3", "정비 주기 표준 가이드"),  # SOP 찾기, 직접 단어 없음
]


def main():
    # 사전 호출로 모델 로딩 시간 측정 분리
    print("=== FAISS 인덱스 빌드 (모델 다운로드 포함, 첫 호출만) ===")
    t0 = time.time()
    _ = faiss_search("warmup query", top_k=1)
    print(f"  build time: {time.time()-t0:.1f}s\n")

    rows = []
    for label, q in QUERIES:
        kw_t0 = time.time()
        kw_res = keyword_search(q, top_k=3)
        kw_ms = (time.time() - kw_t0) * 1000

        fs_t0 = time.time()
        fs_res = faiss_search(q, top_k=3)
        fs_ms = (time.time() - fs_t0) * 1000

        overlap = len(set(kw_res) & set(fs_res))
        rows.append({
            "label": label, "query": q,
            "kw": kw_res, "fs": fs_res,
            "kw_ms": kw_ms, "fs_ms": fs_ms,
            "overlap": overlap,
        })
        print(f"[{label}] '{q}'")
        print(f"  keyword ({kw_ms:.2f}ms): {kw_res}")
        print(f"  faiss   ({fs_ms:.2f}ms): {fs_res}")
        print(f"  overlap: {overlap}/3\n")

    write_results(rows)
    print(f"--- 저장: {OUT_DIR / 'results.md'} ---")


def write_results(rows):
    avg_kw = statistics.mean(r["kw_ms"] for r in rows)
    avg_fs = statistics.mean(r["fs_ms"] for r in rows)
    avg_overlap = statistics.mean(r["overlap"] for r in rows)

    lines = [
        "# D2. FAISS vs 키워드 매칭 검색 비교",
        "",
        "동일 쿼리 집합에 대해 두 백엔드의 검색 결과·latency를 비교합니다.",
        "현재 knowledge 코퍼스 규모(약 10개 문서)에서의 결과입니다.",
        "",
        "## 실험 설정",
        "",
        "- 코퍼스: agents/rag/knowledge/*.md (현재 약 10개 한국어 도메인 문서)",
        "- 키워드: 단어 빈도 합계 랭킹 (`agents.rag.store.keyword_search`)",
        "- FAISS: sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` 임베딩 + IndexFlatIP (코사인)",
        f"- 쿼리 {len(rows)}건 (의미 우회 쿼리 3건 포함, 키워드 직접 매칭이 약한 경우)",
        "",
        "## 쿼리별 결과",
        "",
        "| 쿼리 | 키워드 결과 | FAISS 결과 | 겹침 | kw(ms) | fs(ms) |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        kw = ", ".join(r["kw"]) or "(empty)"
        fs = ", ".join(r["fs"]) or "(empty)"
        lines.append(
            f"| {r['label']} | {kw} | {fs} | {r['overlap']}/3 | {r['kw_ms']:.2f} | {r['fs_ms']:.2f} |"
        )

    lines += [
        "",
        "## 집계",
        "",
        "| 지표 | 키워드 | FAISS |",
        "|---|---|---|",
        f"| 평균 latency | {avg_kw:.2f} ms | {avg_fs:.2f} ms |",
        f"| 결과 겹침 평균 (top-3 기준) | {avg_overlap:.1f}/3 | - |",
        "",
        "## 트레이드오프",
        "",
        "| 측면 | 키워드 매칭 | FAISS 벡터 |",
        "|---|---|---|",
        "| 의미·동의어 매칭 | 직접 어휘 일치만 | ✅ 임베딩 기반 의미 유사도 |",
        "| Latency (10문서) | ✅ 극소 (1ms 미만 가능) | ~ms (인덱스 검색 + 임베딩) |",
        "| 콜드 스타트 | ✅ 없음 | 모델 로딩 ~수초 (캐시 후 즉시) |",
        "| 메모리 | ✅ 거의 0 | ~120MB (multilingual ST 모델) |",
        "| 코퍼스 확장(100+ 문서) | 어휘 못 잡으면 무력 | ✅ 의미로 잡음 |",
        "| 의존성 | 표준 라이브러리만 | sentence-transformers + faiss-cpu |",
        "",
        "## 채택",
        "",
        "**두 백엔드 모두 유지, 환경변수 `RAG_BACKEND=faiss`로 전환**. 현 코퍼스 규모에서는 키워드 매칭이 충분히 정확하고 빠르며 의존성이 적어 기본값. ",
        "코퍼스가 50~100개 이상으로 확장되거나 의미 우회 쿼리 비율이 높아지면 FAISS로 전환 권장. 동일 인터페이스라 코드 변경 없이 전환 가능.",
        "",
    ]
    (OUT_DIR / "results.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
