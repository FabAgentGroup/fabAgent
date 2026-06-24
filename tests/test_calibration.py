"""신뢰도 캘리브레이션 회귀 테스트

ECE/Brier 지표의 수학적 불변식과 isotonic 보정의 개선 효과,
그리고 D15 공표값(런타임 ECE 0.43->~0)을 회귀로 잠근다
"""
from agents.calibration import (
    IsotonicCalibrator,
    brier_score,
    calibrated_is_real,
    expected_calibration_error,
    runtime_calibrator,
)


def test_ece_perfectly_calibrated_is_zero():
    conf = [0.0, 0.0, 1.0, 1.0]
    out = [0, 0, 1, 1]
    assert expected_calibration_error(conf, out) == 0.0


def test_ece_fully_miscalibrated():
    # 확신 0.9인데 전부 틀림 -> ECE 0.9
    assert expected_calibration_error([0.9, 0.9], [0, 0]) == 0.9


def test_ece_empty_is_zero():
    assert expected_calibration_error([], []) == 0.0


def test_brier_perfect_is_zero():
    assert brier_score([1.0, 0.0, 1.0], [1, 0, 1]) == 0.0


def test_brier_worst_is_one():
    assert brier_score([1.0, 0.0], [0, 1]) == 1.0


def test_isotonic_improves_miscalibrated():
    # 단조 오보정 데이터를 보정하면 ECE가 줄어든다
    conf = [0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9]
    out = [0, 0, 0, 0, 1, 1, 1, 1]
    cal = IsotonicCalibrator().fit(conf, out)
    before = expected_calibration_error(conf, out)
    after = expected_calibration_error(cal.transform(conf), out)
    assert after <= before


def test_isotonic_unfitted_is_identity():
    cal = IsotonicCalibrator()
    assert cal.transform([0.3, 0.7]) == [0.3, 0.7]


def test_isotonic_output_clipped_to_unit():
    cal = IsotonicCalibrator().fit([0.0, 0.5, 1.0], [0, 0, 1])
    for v in cal.transform([-0.5, 0.5, 1.5]):
        assert 0.0 <= v <= 1.0


# D15 공표값 - 런타임 보정이 ECE를 0.43에서 거의 0으로 낮춤
def test_runtime_calibrator_d15_anchor():
    rc = runtime_calibrator()
    assert rc["ece_before"] > 0.3
    assert rc["ece_after"] < 0.05
    assert rc["ece_after"] <= rc["ece_before"]


def test_calibrated_is_real_in_unit_interval():
    for sigma in (2.0, 3.5, 5.0, 8.0):
        assert 0.0 <= calibrated_is_real(sigma) <= 1.0


def test_calibrated_is_monotonic_in_sigma():
    # 이탈 강도가 클수록 '진짜 이상' 확률이 단조 증가
    vals = [calibrated_is_real(s) for s in (2.0, 3.5, 5.0, 7.0)]
    assert vals == sorted(vals)
