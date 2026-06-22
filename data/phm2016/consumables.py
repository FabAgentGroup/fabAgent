"""CMP 소모품 수명 모델 (PHM 2016 데이터 기반)

CMP 장비의 소모품(패드·드레서·멤브레인)은 wafer를 처리할수록 마모되고,
사용량이 수명한계에 도달하면 교체(PM)가 필요하다. 마모가 진행되면 MRR(제거율)이
떨어져 결국 spec을 벗어난다. RUL(잔여수명)은 이 한계까지 남은 lot 수다

수명한계와 열화율은 PHM 2016 CMP 데이터의 USAGE_OF_* 카운터 분포에서 도출:
- USAGE_OF_*는 0에서 시작해 교체 직전 max까지 단조 증가 (data/phm2016/loader.py)
- 실측 p98을 실용 교체 임계로 사용 (절대 max 직전)
- 고사용량 구간에서 MRR이 약 10% 하락하는 실제 열화 신호 관측
  (USAGE_OF_POLISHING_TABLE 저사용 MRR 95.7 -> 고사용 86.1)

per-lot 사용 증가율은 소모품별 대표 수명(lot)을 맞추도록 보정한 값이며,
수명한계(life_limit)와 MRR 열화 기울기는 실데이터에서 도출한 값이다
"""
import random

# 소모품별 수명 모델
#   life_limit: 교체 임계 사용량 (PHM 2016 USAGE_OF_* 실측 p98)
#   rate_per_lot: lot당 사용량 증가 (대표 수명 lot에 맞춰 보정)
#   mrr_drop_pct: 신품 대비 수명한계 도달 시 MRR 하락폭 (실측 ~10%)
CONSUMABLES = {
    "polishing_pad": {
        "label": "연마 패드",
        "sensor": "USAGE_OF_POLISHING_TABLE",
        "life_limit": 334.0,    # PHM 2016 실측 p98
        "rate_per_lot": 11.0,   # 대표 수명 ~30 lot
        "mrr_drop_pct": 0.10,   # 마모 시 MRR 약 10% 하락 (실측)
    },
    "dresser": {
        "label": "드레서",
        "sensor": "USAGE_OF_DRESSER",
        "life_limit": 755.0,    # PHM 2016 실측 p98
        "rate_per_lot": 13.0,   # 대표 수명 ~58 lot
        "mrr_drop_pct": 0.07,
    },
    "membrane": {
        "label": "멤브레인",
        "sensor": "USAGE_OF_MEMBRANE",
        "life_limit": 119.0,    # PHM 2016 실측 p98
        "rate_per_lot": 8.0,    # 대표 수명 ~15 lot (가장 빨리 마모)
        "mrr_drop_pct": 0.05,
    },
}

MRR_NOMINAL = 96.0     # 신품 소모품 MRR (실측 저사용 평균)
MRR_SPEC_LOW = 80.0    # MRR 하한 spec (이 아래로 떨어지면 불량)


def consumable_ids() -> list[str]:
    return list(CONSUMABLES.keys())


def nominal_life_lots(consumable: str) -> float:
    c = CONSUMABLES[consumable]
    return c["life_limit"] / c["rate_per_lot"]


# 장비별 현재 소모품 생애 진행도 (데모용, 실 fab에선 FDC/EAP에서 실시간 조회)
#   각 값은 수명 대비 현재 사용 비율 (0=신품, 1=수명한계)
EQUIPMENT_STATE = {
    "AMAT-CMP-02": {"polishing_pad": 0.46, "dresser": 0.31, "membrane": 0.87},  # 멤브레인 임박
    "AMAT-CMP-05": {"polishing_pad": 0.74, "dresser": 0.42, "membrane": 0.28},  # 패드 주의
}


def equipment_usage_snapshot(equipment_id: str, history_lots: int = 6) -> dict[str, list[float]]:
    """장비의 현재 소모품 사용량 이력 스냅샷 (소모품별 최근 history_lots lot)

    현재 생애 진행도에서 nominal rate로 역산한 직선 이력을 반환한다
    """
    state = EQUIPMENT_STATE.get(equipment_id)
    if not state:
        return {}
    out: dict[str, list[float]] = {}
    for cid, frac in state.items():
        c = CONSUMABLES[cid]
        current = frac * c["life_limit"]
        rate = c["rate_per_lot"]
        hist = [max(0.0, current - rate * (history_lots - 1 - k)) for k in range(history_lots)]
        out[cid] = hist
    return out


def make_rtf_trajectory(consumable: str, seed: int, rate_jitter: float = 0.18) -> list[dict]:
    """run-to-failure 사용량 궤적 생성 (RUL 평가용 ground-truth)

    lot마다 rate_per_lot에 잡음을 더해 사용량을 누적, life_limit 도달 시 종료
    실데이터 수명한계·열화율에 보정된 합성 궤적이며 true RUL을 알 수 있다

    각 step: {lot, usage, hi(health index), mrr, true_rul}
    """
    c = CONSUMABLES[consumable]
    rng = random.Random(seed)
    L = c["life_limit"]
    usage = 0.0
    traj = []
    lot = 0
    while usage < L and lot < 1000:
        traj.append({"lot": lot, "usage": usage})
        step = c["rate_per_lot"] * (1.0 + rng.gauss(0, rate_jitter))
        usage += max(1.0, step)
        lot += 1
    fail_lot = traj[-1]["lot"] + 1  # life_limit 돌파 시점

    for step in traj:
        hi = step["usage"] / L
        step["hi"] = round(hi, 4)
        step["mrr"] = round(MRR_NOMINAL * (1.0 - c["mrr_drop_pct"] * hi), 2)
        step["true_rul"] = fail_lot - step["lot"]
    return traj
