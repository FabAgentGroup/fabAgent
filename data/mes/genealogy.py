"""합성 웨이퍼 genealogy (lot 이력)

커몬낼리티 분석의 입력이다. 실 fab에선 MES가 모든 웨이퍼의 공정 이력
(어느 장비·챔버·recipe·소모품 lot·작업자를 거쳤는지)과 최종 metrology/bin 결과를
보관한다. 엔지니어는 불량 웨이퍼들의 '공통 분모'를 찾아 원인을 좁힌다

이 모듈은 GENEALOGY_WAFERS개의 웨이퍼를 합성하되,
PLANTED_INCIDENTS의 root-cause 엔티티를 거친 웨이퍼는 fail 확률을 높인다
-> 커몬낼리티 엔진이 그 엔티티를 과대표현으로 탐지할 수 있어야 한다

웨이퍼 레코드:
    {
      "wafer_id": "W26051800001",
      "lot_id": "L20260518-N-12",
      "process": "CMP",
      "tool": "AMAT-CMP-02", "chamber": "C", "recipe": "CMP-STI-STD",
      "slurry_lot": "SL-2261", "operator": "OP-A", "pm_state": "ok"|"overdue",
      "outcome": "pass"|"fail",
    }
"""
import random
from functools import lru_cache

from data.synth_scenario import (
    AFFECTED_FAIL_BOOST,
    BASE_FAIL_RATE,
    CHAMBERS,
    GENEALOGY_WAFERS,
    OPERATORS,
    PLANTED_INCIDENTS,
    RECIPES,
    SEED,
    SLURRY_LOTS,
    TOOLS,
)

# 공정별 처리 비중 (CMP·Photo에 웨이퍼를 많이 배치해 통계력 확보)
_PROCESS_WEIGHTS = {"CMP": 0.4, "Photo": 0.3, "Etch": 0.2, "Diffusion": 0.06, "Implant": 0.04}


def _route_entities(process: str, rng: random.Random) -> dict:
    tool = rng.choice(TOOLS[process])
    return {
        "tool": tool,
        "chamber": rng.choice(CHAMBERS),
        "recipe": rng.choice(RECIPES[process]),
        "slurry_lot": rng.choice(SLURRY_LOTS) if process == "CMP" else None,
        "operator": rng.choice(OPERATORS),
        "pm_state": "overdue" if rng.random() < 0.15 else "ok",
    }


def _entity_value(route: dict, dim: str) -> str:
    if dim == "chamber":
        return f"{route['tool']}::{route['chamber']}"
    return route.get(dim)


def _matches_root_cause(route: dict, process: str) -> dict | None:
    """이 웨이퍼 경로가 어떤 planted incident의 root-cause 엔티티와 일치하면 그 incident 반환"""
    for inc in PLANTED_INCIDENTS:
        if inc["process"] != process:
            continue
        dim = inc["root_cause"]["dim"]
        if _entity_value(route, dim) == inc["root_cause"]["value"]:
            return inc
    return None


@lru_cache(maxsize=1)
def _generate() -> tuple:
    rng = random.Random(SEED + 1)
    processes = list(_PROCESS_WEIGHTS.keys())
    weights = list(_PROCESS_WEIGHTS.values())
    wafers = []
    for i in range(GENEALOGY_WAFERS):
        process = rng.choices(processes, weights=weights)[0]
        route = _route_entities(process, rng)
        hit = _matches_root_cause(route, process)
        fail_p = BASE_FAIL_RATE + (AFFECTED_FAIL_BOOST if hit else 0.0)
        # PM overdue는 약한 일반 위험요인으로 추가 (교란변수)
        if route["pm_state"] == "overdue":
            fail_p += 0.05
        outcome = "fail" if rng.random() < fail_p else "pass"
        wafers.append({
            "wafer_id": f"W2605180{i:04d}",
            "lot_id": f"L20260518-N-{rng.randint(1, 80):02d}",
            "process": process,
            **route,
            "outcome": outcome,
            "_incident_id": hit["id"] if hit else None,
        })
    return tuple(wafers)


def load_genealogy(process: str | None = None) -> list[dict]:
    """웨이퍼 genealogy 반환, process 지정 시 해당 공정만 필터"""
    wafers = _generate()
    if process:
        return [dict(w) for w in wafers if w["process"] == process]
    return [dict(w) for w in wafers]


def affected_wafers(incident_id: str) -> list[dict]:
    """planted incident에 실제로 영향받은(원인 엔티티를 거친) 웨이퍼 목록 (평가용)"""
    return [dict(w) for w in _generate() if w["_incident_id"] == incident_id]
