"""Tier 0 트리아지 엔진 - 알람 폭주를 incident로 압축

현장 1순위 고통(알람 피로)을 정면으로 푼다. FDC가 쏟아내는 수백 건의 알람 중
대부분은 nuisance(단발·경계선 이탈)다. 트리아지는:
  1. 시공간 클러스터링: 같은 (tool,param) 또는 (recipe,param)에 단시간 집중된 알람을 묶음
  2. nuisance 억제: 어떤 cluster에도 속하지 못한 산발 알람을 제거
  3. 리스크 × 신뢰도 랭킹: 수율 민감도·이탈 강도·확산 범위·신뢰도로 점수화
  -> 운영자는 수백 알람이 아니라 상위 N개 incident만 본다

[설계 원칙] 랭킹은 전적으로 결정론(규칙·통계)이다
현장 엔지니어는 black box를 신뢰하지 않으므로, 왜 이 incident가 위로 왔는지
모든 항(severity/spread/confidence)을 감사할 수 있게 노출한다
LLM은 명명·요약(name_incident_llm)에만 선택적으로 쓴다
"""
from datetime import datetime
from itertools import groupby

from data.synth_scenario import PARAMS

# 클러스터 판정 파라미터
MIN_CLUSTER_ALARMS = 5     # cluster로 인정할 최소 알람 수
WINDOW_MIN = 90            # 집중 판정 시간창(분)
MIN_MEAN_SIGMA = 3.6       # cluster 평균 이탈 강도 하한 (nuisance 평균보다 높게)

_PARAM_WEIGHT = {p: w for params in PARAMS.values() for (p, w) in params}


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _densest_window(alarms: list[dict]) -> list[dict]:
    """시간순 알람에서 WINDOW_MIN 안에 가장 많이 모인 구간의 알람들 반환

    sliding window (two-pointer) - 가장 응집된 부분만 추출해 산발 꼬리를 배제
    """
    alarms = sorted(alarms, key=lambda a: _parse_ts(a["ts"]))
    best: list[dict] = []
    left = 0
    for right in range(len(alarms)):
        t_right = _parse_ts(alarms[right]["ts"])
        while (t_right - _parse_ts(alarms[left]["ts"])).total_seconds() > WINDOW_MIN * 60:
            left += 1
        window = alarms[left:right + 1]
        if len(window) > len(best):
            best = window
    return best


def _make_incident(idx: int, alarms: list[dict], kind: str) -> dict:
    sigmas = [a["sigma"] for a in alarms]
    tools = sorted({a["tool_id"] for a in alarms})
    recipes = sorted({a["recipe"] for a in alarms})
    chambers = sorted({a["chamber"] for a in alarms})
    ts_sorted = sorted(_parse_ts(a["ts"]) for a in alarms)
    span_min = (ts_sorted[-1] - ts_sorted[0]).total_seconds() / 60.0

    process = alarms[0]["process"]
    param = alarms[0]["param"]
    mean_sigma = sum(sigmas) / len(sigmas)
    max_sigma = max(sigmas)
    yield_w = _PARAM_WEIGHT.get(param, 0.5)

    # severity(0~1): 이탈 강도 × 수율 민감도
    severity = min(1.0, (max_sigma / 8.0)) * (0.5 + 0.5 * yield_w)
    # spread(0~1): 알람 수 + 다장비 확산 (systemic은 가중)
    spread = min(1.0, len(alarms) / 16.0) * (1.0 + 0.25 * (len(tools) - 1))
    spread = min(1.0, spread)
    # confidence(0~1): 응집도(알람수/시간창) - 짧은 시간에 많이 모일수록 진짜
    density = len(alarms) / max(span_min, 1.0)            # 알람/분
    confidence = min(1.0, density / (MIN_CLUSTER_ALARMS / WINDOW_MIN) / 3.0)

    risk_score = round(100.0 * (0.55 * severity + 0.30 * spread + 0.15 * confidence), 1)

    dominant_tool = max(tools, key=lambda t: sum(1 for a in alarms if a["tool_id"] == t))
    dominant_recipe = max(recipes, key=lambda r: sum(1 for a in alarms if a["recipe"] == r))
    dominant_chamber = max(chambers, key=lambda c: sum(1 for a in alarms if a["chamber"] == c))

    kind_label = "systemic(다장비)" if kind == "systemic" else "tool-localized"
    title = f"{process} {param} 이상 - {dominant_tool}" + (f" 외 {len(tools)-1}대" if len(tools) > 1 else "")

    return {
        "incident_id": f"TRIAGE-{idx:04d}",
        "title": title,
        "process": process,
        "param": param,
        "kind": kind,
        "kind_label": kind_label,
        "tools": tools,
        "dominant_tool": dominant_tool,
        "dominant_recipe": dominant_recipe,
        "dominant_chamber": dominant_chamber,
        "n_alarms": len(alarms),
        "max_sigma": round(max_sigma, 1),
        "mean_sigma": round(mean_sigma, 2),
        "span_min": round(span_min, 1),
        "window_start": ts_sorted[0].isoformat(),
        "window_end": ts_sorted[-1].isoformat(),
        # 감사용 점수 분해
        "score_breakdown": {
            "severity": round(severity, 3),
            "spread": round(spread, 3),
            "confidence": round(confidence, 3),
            "yield_weight": yield_w,
        },
        "risk_score": risk_score,
        "confidence": round(confidence, 3),
        "alarm_ids": [a["alarm_id"] for a in alarms],
    }


def _cluster(alarms: list[dict], key_fn, kind: str, min_tools: int = 1) -> list[dict]:
    """key_fn으로 그룹핑 후 각 그룹의 densest window가 임계 통과하면 incident 후보 생성"""
    out = []
    keyed = sorted(alarms, key=key_fn)
    for _key, grp in groupby(keyed, key=key_fn):
        grp = list(grp)
        window = _densest_window(grp)
        if len(window) < MIN_CLUSTER_ALARMS:
            continue
        if len({a["tool_id"] for a in window}) < min_tools:
            continue
        mean_sigma = sum(a["sigma"] for a in window) / len(window)
        if mean_sigma < MIN_MEAN_SIGMA:
            continue
        out.append((window, kind))
    return out


def _merge_adjacent(chosen: list[tuple]) -> list[tuple]:
    """같은 (process,param)이고 시간창이 WINDOW_MIN 이내로 인접·중첩한 cluster를 병합

    하나의 물리적 excursion이 densest-window 추출로 쪼개진 경우를 복원한다
    systemic kind가 섞이면 systemic을 유지 (다장비 신호 보존)
    """
    def bounds(window):
        ts = sorted(_parse_ts(a["ts"]) for a in window)
        return ts[0], ts[-1]

    merged: list[tuple] = []
    for window, kind in sorted(chosen, key=lambda c: _parse_ts(min(a["ts"] for a in c[0]))):
        p_key = (window[0]["process"], window[0]["param"])
        w_start, w_end = bounds(window)
        for i, (mw, mk) in enumerate(merged):
            if (mw[0]["process"], mw[0]["param"]) != p_key:
                continue
            m_start, m_end = bounds(mw)
            gap = (w_start - m_end).total_seconds() / 60.0
            if gap <= WINDOW_MIN:  # 중첩하거나 WINDOW_MIN 이내 인접
                ids = {a["alarm_id"] for a in mw}
                union = mw + [a for a in window if a["alarm_id"] not in ids]
                merged[i] = (union, "systemic" if "systemic" in (mk, kind) else kind)
                break
        else:
            merged.append((window, kind))
    return merged


def triage(alarms: list[dict], top_k: int | None = None) -> dict:
    """FDC 알람 스트림 -> 랭킹된 incident 목록

    반환:
      {
        "incidents": [Incident, ...],         # risk_score 내림차순
        "n_total": int, "n_clustered": int,
        "n_suppressed": int,                  # nuisance로 억제된 알람 수
        "compression_ratio": float,           # n_total / len(incidents)
      }
    """
    # 1) tool-localized cluster: (tool_id, process, param)
    candidates = _cluster(
        alarms, key_fn=lambda a: (a["tool_id"], a["process"], a["param"]), kind="tool"
    )
    # 2) systemic cluster: (process, recipe, param), 2개 이상 장비에 걸친 것만
    candidates += _cluster(
        alarms, key_fn=lambda a: (a["process"], a["recipe"], a["param"]),
        kind="systemic", min_tools=2,
    )

    # 3) 알람 집합이 크게 겹치는 후보 dedupe (더 많은 알람을 묶은 쪽 우선)
    candidates.sort(key=lambda c: -len(c[0]))
    chosen: list[tuple] = []
    used_ids: set[str] = set()
    for window, kind in candidates:
        ids = {a["alarm_id"] for a in window}
        overlap = len(ids & used_ids) / len(ids)
        if overlap > 0.5:
            continue
        chosen.append((window, kind))
        used_ids |= ids

    # 4) 같은 (process,param)에서 시간창이 WINDOW_MIN 이내로 인접한 후보 병합
    #    densest-window 추출이 긴 incident를 시간 분할한 경우 하나로 합친다
    chosen = _merge_adjacent(chosen)

    incidents = [_make_incident(i + 1, w, k) for i, (w, k) in enumerate(chosen)]
    incidents.sort(key=lambda inc: -inc["risk_score"])
    # rank 재부여
    for rank, inc in enumerate(incidents, 1):
        inc["rank"] = rank

    clustered_ids = used_ids
    result = {
        "incidents": incidents[:top_k] if top_k else incidents,
        "n_total": len(alarms),
        "n_clustered": len(clustered_ids),
        "n_suppressed": len(alarms) - len(clustered_ids),
        "n_incidents": len(incidents),
        "compression_ratio": round(len(alarms) / max(len(incidents), 1), 1),
    }
    return result
