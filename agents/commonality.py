"""커몬낼리티 엔진 - 불량 웨이퍼의 '공통 분모'를 통계로 찾는다

현장 엔지니어가 매일 하는 가장 가치 높은 RCA 기법을 자동화한다:
불량(fail) 웨이퍼들이 어떤 장비·챔버·슬러리 lot·작업자를 비정상적으로 많이
거쳤는지(over-representation)를 통계적으로 찾아낸다

지금까지 cause 에이전트는 RAG(정성적 지식)만 봤다. 여기에 genealogy 기반
정량 용의자(lift·p-value)를 더하면, "유사 사례가 있다"를 넘어
"이 불량들의 89%가 챔버 C를 거쳤고 정상은 12%뿐(lift 7.4x, p<0.001)"을 댈 수 있다

방법: 각 genealogy 차원에 대해 fail vs pass 2x2 분할표 -> χ²(1 dof) + lift
의존성 없이 math.erfc로 p-value 산출 (scipy 불필요)
"""
import math
from collections import defaultdict

from data.mes.genealogy import load_genealogy

# 분석 대상 차원 (genealogy 필드명 -> 표시 라벨)
DIMENSIONS = {
    "tool": "장비",
    "chamber": "챔버",
    "recipe": "recipe",
    "slurry_lot": "슬러리 lot",
    "operator": "작업자",
    "pm_state": "PM 상태",
}
MIN_SUPPORT = 6      # 엔티티를 거친 웨이퍼 최소 수 (통계 신뢰)
MIN_LIFT = 1.3       # 이만큼 이상 과대표현일 때만 용의자
TOP_SUSPECTS = 5


def _chi2_p(a: int, b: int, c: int, d: int) -> tuple[float, float]:
    """2x2 분할표 χ²(1 dof) 통계량과 p-value

    a=엔티티&fail, b=엔티티&pass, c=비엔티티&fail, d=비엔티티&pass
    p = erfc(sqrt(chi2/2))  (1 자유도 카이제곱 생존함수)
    """
    n = a + b + c + d
    denom = (a + b) * (c + d) * (a + c) * (b + d)
    if denom == 0 or n == 0:
        return 0.0, 1.0
    chi2 = n * (a * d - b * c) ** 2 / denom
    p = math.erfc(math.sqrt(chi2 / 2.0))
    return chi2, p


def _entity_value(w: dict, dim: str) -> str | None:
    if dim == "chamber":
        return f"{w['tool']}::{w['chamber']}"
    return w.get(dim)


def analyze_commonality(
    process: str,
    scope_tool: str | None = None,
    scope_recipe: str | None = None,
) -> dict:
    """process(+선택 scope) 웨이퍼 집단에서 fail을 과대표현하는 엔티티 랭킹

    scope_tool/scope_recipe로 모집단을 좁히면(엔지니어가 용의 범위를 좁히듯)
    동시 발생한 다른 incident의 신호와 분리할 수 있다
    """
    pop = load_genealogy(process)
    if scope_tool:
        pop = [w for w in pop if w["tool"] == scope_tool]
    if scope_recipe:
        pop = [w for w in pop if w["recipe"] == scope_recipe]

    total = len(pop)
    total_fail = sum(1 for w in pop if w["outcome"] == "fail")
    if total == 0 or total_fail == 0:
        return {"process": process, "population": total, "overall_fail_rate": 0.0, "suspects": []}

    overall_rate = total_fail / total
    suspects = []
    for dim in DIMENSIONS:
        # scope로 고정된 차원은 변별력 없음 -> 건너뜀
        if (dim == "tool" and scope_tool) or (dim == "recipe" and scope_recipe):
            continue
        buckets: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # value -> [fail, pass]
        for w in pop:
            val = _entity_value(w, dim)
            if val is None:
                continue
            buckets[val][0 if w["outcome"] == "fail" else 1] += 1

        for val, (a, b) in buckets.items():
            support = a + b
            if support < MIN_SUPPORT:
                continue
            c = total_fail - a
            d = (total - total_fail) - b
            entity_rate = a / support
            lift = entity_rate / overall_rate
            if lift < MIN_LIFT:
                continue
            chi2, p = _chi2_p(a, b, c, d)
            suspects.append({
                "dim": dim,
                "dim_label": DIMENSIONS[dim],
                "value": val,
                "fail_in_entity": a,
                "entity_total": support,
                "entity_fail_rate": round(entity_rate, 3),
                "baseline_fail_rate": round(overall_rate, 3),
                "lift": round(lift, 2),
                "chi2": round(chi2, 1),
                "p_value": float(f"{p:.2e}"),
            })

    # 유의성(χ²) 우선 랭킹 - 효과크기(lift)와 표본수를 동시에 반영한다
    # lift 단독 랭킹은 소표본 우연(작은 챔버·작업자)을 과대평가하므로 피한다
    suspects.sort(key=lambda s: (-s["chi2"], -s["lift"]))
    return {
        "process": process,
        "scope": {"tool": scope_tool, "recipe": scope_recipe},
        "population": total,
        "overall_fail_rate": round(overall_rate, 3),
        "suspects": suspects[:TOP_SUSPECTS],
    }


def commonality_analysis(
    process: str,
    scope_tool: str | None = None,
    scope_recipe: str | None = None,
) -> dict:
    """[tool] 불량 웨이퍼의 공통 엔티티(장비·챔버·슬러리·작업자)를 통계로 추출

    cause 에이전트가 정량적 용의자를 확보할 때 호출한다
    """
    result = analyze_commonality(process, scope_tool, scope_recipe)
    # LLM 친화적 요약 문장 추가
    lines = []
    for s in result["suspects"]:
        lines.append(
            f"{s['dim_label']} '{s['value']}': 불량률 {s['entity_fail_rate']:.0%} "
            f"vs 전체 {s['baseline_fail_rate']:.0%} (lift {s['lift']}x, p={s['p_value']:.1e}, "
            f"n={s['entity_total']})"
        )
    result["summary"] = lines
    return result


def scope_for_incident(incident: dict) -> dict:
    """트리아지 incident -> 커몬낼리티 모집단 scope (kind별 핸드오프)

    systemic(다장비) incident는 원인이 장비를 가로지르므로 recipe로만 좁힌다
    tool-localized는 장비+recipe로 좁혀 동시 발생한 다른 이상과 분리한다
    """
    if incident.get("kind") == "systemic":
        return {"process": incident["process"], "scope_recipe": incident.get("dominant_recipe")}
    return {
        "process": incident["process"],
        "scope_tool": incident.get("dominant_tool"),
        "scope_recipe": incident.get("dominant_recipe"),
    }


def commonality_for_incident(incident: dict) -> dict:
    """트리아지 incident를 받아 적절히 scope된 커몬낼리티 결과 반환"""
    return commonality_analysis(**scope_for_incident(incident))


SCHEMA = {
    "type": "function",
    "function": {
        "name": "commonality_analysis",
        "description": (
            "불량 웨이퍼들이 공통으로 거친 장비·챔버·슬러리 lot·작업자를 MES genealogy에서 "
            "통계적으로(lift·p-value) 추출합니다. 과대표현된 엔티티가 물리적 원인 후보입니다. "
            "RAG 지식 검색과 함께 쓰면 정성적 사례 + 정량적 용의자를 모두 확보할 수 있습니다. "
            "scope_tool/scope_recipe로 용의 범위를 좁히면 동시 발생한 다른 이상과 분리됩니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "process": {
                    "type": "string",
                    "description": "공정 (Photo, Etch, CMP, Diffusion, Implant)",
                },
                "scope_tool": {
                    "type": "string",
                    "description": "용의 장비로 모집단 한정 (선택, 예: 'AMAT-CMP-02')",
                },
                "scope_recipe": {
                    "type": "string",
                    "description": "용의 recipe로 모집단 한정 (선택, 예: 'CMP-CU-LOW')",
                },
            },
            "required": ["process"],
        },
    },
}
