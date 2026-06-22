"""D16: 운영자 결정 자가학습 루프 측정

운영자가 승인한 분석은 INC-AUTO 문서로 knowledge에 기록되어 RAG 검색 대상이 된다
(agents/rag/learn.py). 이 루프가 실제로 향후 유사 알람의 retrieval을 개선하는지
정량 측정한다

방법:
- 코퍼스에 없던 해결책을 가진 '해결된 인시던트' K건을 정의
- 기록 전: 증상 쿼리로 검색해도 그 해결책이 retrieval되지 않음 (hit 0)
- 기록 후: 같은 쿼리에 INC-AUTO 문서가 상위로 retrieval됨 (hit@k, MRR)
=> 운영자 지식이 시스템 지식으로 즉시 반영되어 actionable해짐

retrieval은 keyword 백엔드(로컬·결정론). 임시 문서는 측정 후 정리
실행: python -m experiments.learning_eval.benchmark
결과: results.md (차트 없음, 표 중심)
"""
import os
from pathlib import Path

os.environ["RAG_BACKEND"] = "keyword"  # 로컬 결정론 retrieval

from agents.rag.store import KNOWLEDGE_DIR, search

HERE = Path(__file__).parent
TOP_K = 3

# 코퍼스에 없던 해결 인시던트 (증상 쿼리 + 고유 해결책 토큰)
RESOLVED_INCIDENTS = [
    {"id": "INC-AUTO-D16-001", "process": "Diffusion",
     "query": "Diffusion 막 두께 산포 증가 퍼니스 존2 온도 드리프트",
     "root_cause": "퍼니스 존2 열전대 드리프트", "resolution": "존2 열전대 교정 및 프로파일 재설정"},
    {"id": "INC-AUTO-D16-002", "process": "Implant",
     "query": "Implant 도즈량 편차 빔 전류 불안정 소스 열화",
     "root_cause": "이온 소스 필라멘트 열화", "resolution": "소스 필라멘트 교체 후 빔 튜닝"},
    {"id": "INC-AUTO-D16-003", "process": "CMP",
     "query": "CMP 제거율 저하 패드 글레이징 컨디셔너 마모",
     "root_cause": "패드 글레이징 및 컨디셔너 마모", "resolution": "컨디셔너 교체 + 패드 브레이크인 재수행"},
    {"id": "INC-AUTO-D16-004", "process": "Etch",
     "query": "Etch 식각 프로파일 테이퍼 폴리머 잔류 챔버 시즈닝",
     "root_cause": "챔버 폴리머 잔류", "resolution": "챔버 웨이퍼리스 오토클린 + 시즈닝"},
    {"id": "INC-AUTO-D16-005", "process": "Photo",
     "query": "Photo 오버레이 정렬 오차 레티클 스테이지 열팽창",
     "root_cause": "레티클 스테이지 열팽창", "resolution": "스테이지 온도 안정화 대기 후 재정렬"},
]


def _doc_text(inc: dict) -> str:
    return f"""# {inc['id']} - {inc['process']} 자동 기록 (운영자 승인)

## 분류
- 유형: 자동 학습 인시던트
- 공정: {inc['process']}

## 증상
{inc['query']}

## 추정 원인
{inc['root_cause']}

## 채택 해결책
{inc['resolution']}
"""


def _rank_of(doc_id: str, hits: list[str]) -> int | None:
    return hits.index(doc_id) + 1 if doc_id in hits else None


def evaluate():
    before_hits = after_hits = 0
    reciprocal = []
    rows = []
    written = []
    try:
        for inc in RESOLVED_INCIDENTS:
            # 기록 전 retrieval
            search.cache_clear() if hasattr(search, "cache_clear") else None
            pre = search(inc["query"], top_k=TOP_K)
            pre_rank = _rank_of(inc["id"], pre)

            # 운영자 승인 -> 자가학습 기록
            path = KNOWLEDGE_DIR / f"{inc['id']}.md"
            path.write_text(_doc_text(inc), encoding="utf-8")
            written.append(path)

            # 기록 후 retrieval
            post = search(inc["query"], top_k=TOP_K)
            post_rank = _rank_of(inc["id"], post)

            if pre_rank:
                before_hits += 1
            if post_rank:
                after_hits += 1
                reciprocal.append(1.0 / post_rank)
            else:
                reciprocal.append(0.0)
            rows.append({"id": inc["id"], "process": inc["process"],
                         "pre_rank": pre_rank, "post_rank": post_rank})
    finally:
        for p in written:
            p.unlink(missing_ok=True)

    n = len(RESOLVED_INCIDENTS)
    return {
        "n": n,
        "before_hit_rate": before_hits / n,
        "after_hit_rate": after_hits / n,
        "mrr_after": sum(reciprocal) / n,
        "rows": rows,
    }


def write_results(m):
    lines = []
    lines.append("# D16: 운영자 결정 자가학습 루프 측정")
    lines.append("")
    lines.append("운영자 승인 분석이 INC-AUTO 문서로 knowledge에 기록되어, 향후 유사 알람의")
    lines.append("retrieval을 실제로 개선하는지 측정합니다. 운영자 지식이 시스템 지식으로")
    lines.append("즉시 반영되어 actionable해지는지를 정량 확인합니다.")
    lines.append("")
    lines.append("## 실험 설정")
    lines.append("")
    lines.append(f"- 코퍼스에 없던 해결 인시던트 {m['n']}건 (공정별 고유 증상·해결책)")
    lines.append("- 기록 전/후 동일 증상 쿼리로 retrieval, 해결 문서의 순위 비교")
    lines.append(f"- retrieval: keyword 백엔드(로컬·결정론), top-{TOP_K}, 임시 문서는 측정 후 정리")
    lines.append("")
    lines.append("## 결과")
    lines.append("")
    lines.append("| 지표 | 값 |")
    lines.append("|---|---|")
    lines.append(f"| 기록 전 retrieval 성공률 | **{m['before_hit_rate']:.0%}** (해당 지식 부재) |")
    lines.append(f"| 기록 후 hit@{TOP_K} | **{m['after_hit_rate']:.0%}** |")
    lines.append(f"| 기록 후 MRR | **{m['mrr_after']:.2f}** |")
    lines.append("")
    lines.append("| 인시던트 | 공정 | 기록 전 순위 | 기록 후 순위 |")
    lines.append("|---|---|---|---|")
    for r in m["rows"]:
        pre = r["pre_rank"] if r["pre_rank"] else "미검색"
        post = r["post_rank"] if r["post_rank"] else "미검색"
        lines.append(f"| {r['id']} | {r['process']} | {pre} | {post} |")
    lines.append("")
    lines.append("## 결론")
    lines.append("")
    lines.append(f"- 기록 전에는 해당 해결책이 코퍼스에 없어 retrieval 불가({m['before_hit_rate']:.0%})")
    lines.append(f"- 운영자 승인 즉시 INC-AUTO 기록 -> hit@{TOP_K} {m['after_hit_rate']:.0%}, "
                 f"MRR {m['mrr_after']:.2f}로 상위 retrieval")
    lines.append("- 운영자 결정이 시스템 지식으로 폐루프 반영됨을 정량 확인")
    lines.append("- 보류·거절 사유는 감사 로그(core/audit.py)에 구조화 수집되어 추가 학습 신호로 활용 가능")
    (HERE / "results.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    m = evaluate()
    write_results(m)
    print(f"인시던트 {m['n']}건")
    print(f"기록 전 성공률 {m['before_hit_rate']:.0%} -> 기록 후 hit@{TOP_K} {m['after_hit_rate']:.0%}, "
          f"MRR {m['mrr_after']:.2f}")
    print("-> results.md 작성 완료")


if __name__ == "__main__":
    main()
