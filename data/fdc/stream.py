"""합성 FDC 알람 스트림

실 fab의 FDC 시스템은 한 교대에 수백~수천 건의 파라미터 관리한계 위반 알람을
쏟아낸다. 대부분(>90%)은 nuisance(단발·경계선 이탈)이고, 소수가 진짜 excursion이다
이 모듈은 그 흐름을 재현 가능(seed 고정)하게 합성한다

알람 레코드(트리아지 입력):
    {
      "alarm_id": "FDC-...-0001",
      "ts": "2026-05-18T01:12:00",   # ISO timestamp
      "process": "CMP",
      "tool_id": "AMAT-CMP-02",
      "chamber": "C",
      "recipe": "CMP-STI-STD",
      "param": "MRR",
      "value": 318.4,
      "limit": 300.0,
      "sigma": 5.2,                  # 관리한계 이탈 강도 (|z|)
      "lot_id": "L20260518-...",
    }

ground-truth(_truth)는 평가 전용이며 트리아지 엔진에 넘기지 않는다
    "_truth": {"klass": "excursion"|"nuisance", "incident_id": str|None,
               "root_cause": {"dim","value"}|None}
"""
import random
from datetime import timedelta
from functools import lru_cache

from data.synth_scenario import (
    CHAMBERS,
    N_NUISANCE,
    NUISANCE_SIGMA,
    PARAMS,
    PLANTED_INCIDENTS,
    RECIPES,
    SEED,
    SHIFT_HOURS,
    SHIFT_START,
    SLURRY_LOTS,
    TOOLS,
)


def _lot_id(rng: random.Random) -> str:
    return f"L20260518-N-{rng.randint(1, 80):02d}"


def _baseline_for(param: str, process: str) -> float:
    # 파라미터별 대략적 관리한계 값 (표시용, 절대값 자체는 트리아지에 안 쓰임)
    base = {
        "MRR": 300.0, "제거 균일도": 95.0, "슬러리 유량": 200.0, "패드 압력": 5.0,
        "CD-X 산포": 3.0, "Focus 편차": 40.0, "노광 에너지": 25.0, "Overlay": 4.0,
        "Trench Depth": 120.0, "식각 균일도": 96.0, "가스 유량": 80.0, "챔버 압력": 10.0,
        "막 두께": 50.0, "온도 균일도": 98.0, "도즈량": 1e13, "빔 전류": 2.0,
    }
    return base.get(param, 100.0)


def _make_excursion_alarms(inc: dict, rng: random.Random, counter: list) -> list[dict]:
    out = []
    lo, hi = inc["sigma_range"]
    for _ in range(inc["n_alarms"]):
        tool = rng.choice(inc["tools"])
        chamber = inc["chamber"] or rng.choice(CHAMBERS)
        offset = rng.uniform(0, inc["window_min"])
        ts = SHIFT_START + timedelta(minutes=inc["start_min"] + offset)
        sigma = round(rng.uniform(lo, hi), 1)
        limit = _baseline_for(inc["param"], inc["process"])
        counter[0] += 1
        out.append({
            "alarm_id": f"FDC-20260518-{counter[0]:04d}",
            "ts": ts.isoformat(),
            "process": inc["process"],
            "tool_id": tool,
            "chamber": chamber,
            "recipe": inc["recipe"],
            "param": inc["param"],
            "value": round(limit * (1 + sigma / 100.0), 2),
            "limit": limit,
            "sigma": sigma,
            "lot_id": _lot_id(rng),
            "_truth": {
                "klass": "excursion",
                "incident_id": inc["id"],
                "root_cause": inc["root_cause"],
            },
        })
    return out


def _make_nuisance_alarms(rng: random.Random, counter: list) -> list[dict]:
    out = []
    lo, hi = NUISANCE_SIGMA
    processes = list(TOOLS.keys())
    for _ in range(N_NUISANCE):
        process = rng.choice(processes)
        tool = rng.choice(TOOLS[process])
        chamber = rng.choice(CHAMBERS)
        recipe = rng.choice(RECIPES[process])
        param, _w = rng.choice(PARAMS[process])
        ts = SHIFT_START + timedelta(minutes=rng.uniform(0, SHIFT_HOURS * 60))
        sigma = round(rng.uniform(lo, hi), 1)
        limit = _baseline_for(param, process)
        counter[0] += 1
        out.append({
            "alarm_id": f"FDC-20260518-{counter[0]:04d}",
            "ts": ts.isoformat(),
            "process": process,
            "tool_id": tool,
            "chamber": chamber,
            "recipe": recipe,
            "param": param,
            "value": round(limit * (1 + sigma / 100.0), 2),
            "limit": limit,
            "sigma": sigma,
            "lot_id": _lot_id(rng),
            "_truth": {"klass": "nuisance", "incident_id": None, "root_cause": None},
        })
    return out


@lru_cache(maxsize=1)
def _generate() -> tuple:
    rng = random.Random(SEED)
    counter = [0]
    alarms: list[dict] = []
    for inc in PLANTED_INCIDENTS:
        alarms.extend(_make_excursion_alarms(inc, rng, counter))
    alarms.extend(_make_nuisance_alarms(rng, counter))
    alarms.sort(key=lambda a: a["ts"])
    return tuple(alarms)


def load_alarm_stream(with_truth: bool = False) -> list[dict]:
    """한 교대치 FDC 알람 스트림 반환 (시간순 정렬)

    with_truth=False(기본): 트리아지 입력용, _truth 필드 제거
    with_truth=True: 평가용, _truth 포함
    """
    alarms = _generate()
    if with_truth:
        return [dict(a) for a in alarms]
    return [{k: v for k, v in a.items() if k != "_truth"} for a in alarms]


def stream_stats() -> dict:
    alarms = _generate()
    n_exc = sum(1 for a in alarms if a["_truth"]["klass"] == "excursion")
    return {
        "total": len(alarms),
        "excursion": n_exc,
        "nuisance": len(alarms) - n_exc,
        "incidents": len(PLANTED_INCIDENTS),
    }
