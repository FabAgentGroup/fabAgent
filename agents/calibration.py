"""신뢰도 캘리브레이션 - 시스템 confidence를 믿을 수 있게

시스템이 내는 confidence(원인 기여도, 디스포지션 신뢰도 등)가 실제 적중률과
일치해야 운영자가 신뢰한다. '70% 확신'이 실제로 70% 맞아야 한다
ECE(Expected Calibration Error)로 어긋남을 측정하고, isotonic regression으로 보정한다

[설계 원칙] 보정은 라벨링된 (confidence, outcome) 이력에서 학습한 결정론 매핑
"""
import math
from functools import lru_cache

from sklearn.isotonic import IsotonicRegression


def expected_calibration_error(confidences: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    """ECE - 신뢰도 구간별 |평균신뢰도 - 실제적중률| 가중평균

    confidences: 0~1 예측 확률, outcomes: 0/1 실제 결과
    """
    n = len(confidences)
    if n == 0:
        return 0.0
    ece = 0.0
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        idx = [i for i, c in enumerate(confidences) if (lo < c <= hi) or (b == 0 and c <= hi)]
        if not idx:
            continue
        avg_conf = sum(confidences[i] for i in idx) / len(idx)
        acc = sum(outcomes[i] for i in idx) / len(idx)
        ece += abs(acc - avg_conf) * len(idx) / n
    return ece


def reliability_curve(confidences: list[float], outcomes: list[int], n_bins: int = 10) -> list[dict]:
    """신뢰도 구간별 (평균신뢰도, 실제적중률, 건수) - reliability diagram용"""
    out = []
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        idx = [i for i, c in enumerate(confidences) if (lo < c <= hi) or (b == 0 and c <= hi)]
        if not idx:
            continue
        out.append({
            "bin_center": (lo + hi) / 2,
            "avg_conf": sum(confidences[i] for i in idx) / len(idx),
            "accuracy": sum(outcomes[i] for i in idx) / len(idx),
            "count": len(idx),
        })
    return out


def brier_score(confidences: list[float], outcomes: list[int]) -> float:
    """Brier score - 확률 예측의 평균제곱오차 (낮을수록 좋음)"""
    n = len(confidences)
    if n == 0:
        return 0.0
    return sum((c - o) ** 2 for c, o in zip(confidences, outcomes)) / n


class IsotonicCalibrator:
    """isotonic regression 기반 단조 보정기

    raw confidence를 실제 적중률에 맞게 단조 재매핑한다
    """

    def __init__(self):
        self._iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self._fitted = False

    def fit(self, confidences: list[float], outcomes: list[int]) -> "IsotonicCalibrator":
        self._iso.fit(confidences, outcomes)
        self._fitted = True
        return self

    def transform(self, confidences: list[float]) -> list[float]:
        if not self._fitted:
            return list(confidences)
        return [float(v) for v in self._iso.predict(confidences)]

    def calibrate(self, confidence: float) -> float:
        """단일 confidence 보정 (런타임 표시용)"""
        return self.transform([confidence])[0]


# ==================== 런타임 보정기 (UI 신뢰도 표시용) ====================
# 이상 강도(sigma) -> '진짜 이상' 확률의 naive 추정을 라벨링된 이력으로 보정
# D15와 동일한 모델, 런타임에 1회 fit 후 캐시

_RAW_K = 1.5
_RAW_S0 = 3.5


def _raw_is_real(sigma: float) -> float:
    return 1.0 / (1.0 + math.exp(-_RAW_K * (sigma - _RAW_S0)))


@lru_cache(maxsize=1)
def runtime_calibrator() -> dict:
    """FDC 라벨 이력으로 isotonic 보정기를 1회 학습, 보정 전/후 ECE 포함 반환"""
    from data.fdc.stream import load_alarm_stream

    alarms = load_alarm_stream(with_truth=True)
    conf = [_raw_is_real(a["sigma"]) for a in alarms]
    out = [1 if a["_truth"]["klass"] == "excursion" else 0 for a in alarms]
    cal = IsotonicCalibrator().fit(conf, out)
    return {
        "calibrator": cal,
        "ece_before": expected_calibration_error(conf, out),
        "ece_after": expected_calibration_error(cal.transform(conf), out),
        "n": len(alarms),
    }


def calibrated_is_real(sigma: float) -> float:
    """이상 강도(sigma)의 '진짜 이상' 확률을 보정해 반환 (0~1)"""
    rc = runtime_calibrator()
    return rc["calibrator"].calibrate(_raw_is_real(sigma))
