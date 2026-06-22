"""신뢰도 캘리브레이션 - 시스템 confidence를 믿을 수 있게

시스템이 내는 confidence(원인 기여도, 디스포지션 신뢰도 등)가 실제 적중률과
일치해야 운영자가 신뢰한다. '70% 확신'이 실제로 70% 맞아야 한다
ECE(Expected Calibration Error)로 어긋남을 측정하고, isotonic regression으로 보정한다

[설계 원칙] 보정은 라벨링된 (confidence, outcome) 이력에서 학습한 결정론 매핑
"""
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
