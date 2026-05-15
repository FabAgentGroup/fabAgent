"""UCI SECOM 데이터셋 로더

반도체 제조 공정 센서 데이터 (1567 row x 590 feature, pass/fail 라벨)
출처: https://archive.ics.uci.edu/dataset/179/secom
raw/ 에 secom.data, secom_labels.data 를 두면 로드됨 (data/README.md 참고)

Tier 1 이상 탐지 에이전트가 이 데이터로 이상 점수와 기여 피처를 계산
"""
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "raw"


def load_secom() -> tuple[pd.DataFrame, pd.Series]:
    """SECOM 센서 피처와 pass/fail 라벨을 반환

    features: 1567 x 590 (결측치 포함), 컬럼명 sensor_000 ~ sensor_589
    labels: 1=fail(이상), -1=pass(정상)
    """
    data_path = RAW_DIR / "secom.data"
    label_path = RAW_DIR / "secom_labels.data"
    if not data_path.exists() or not label_path.exists():
        raise FileNotFoundError(
            f"SECOM 데이터가 없음, {RAW_DIR}에 secom.data / secom_labels.data 를 두세요 "
            "(data/README.md 참고)"
        )

    features = pd.read_csv(data_path, sep=r"\s+", header=None)
    features.columns = [f"sensor_{i:03d}" for i in range(features.shape[1])]
    labels = pd.read_csv(label_path, sep=r"\s+", header=None, usecols=[0])[0]
    return features, labels
