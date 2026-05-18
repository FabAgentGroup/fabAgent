"""PHM 2016 Data Challenge CMP 데이터셋 로더

CMP(Chemical Mechanical Planarization) 공정 센서 데이터, 25개 실 센서 이름 공개
- 1981 wafer × 2 stage(A/B)
- target: 평균 재료 제거율(AVG_REMOVAL_RATE)
출처: https://phmsociety.org PHM Data Challenge 2016

raw/CMP-data/training/CMP-training-NNN.csv: trajectory 시계열 (wafer 다수)
raw/CMP-training-removalrate.csv: (WAFER_ID, STAGE, AVG_REMOVAL_RATE) 라벨

per-wafer feature vector를 만들기 위해 trajectory를 평균으로 집계
A3 알람(CMP step 이상)이 이 데이터로 Tier 1 이상 탐지 수행
"""
from functools import lru_cache
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "raw"
TRAIN_TRAJ_DIR = RAW_DIR / "CMP-data" / "training"
TRAIN_LABEL = RAW_DIR / "CMP-training-removalrate.csv"

# 집계 대상 센서 컬럼, 진짜 의미 있는 이름들
SENSOR_COLS = [
    "USAGE_OF_BACKING_FILM",
    "USAGE_OF_DRESSER",
    "USAGE_OF_POLISHING_TABLE",
    "USAGE_OF_DRESSER_TABLE",
    "PRESSURIZED_CHAMBER_PRESSURE",
    "MAIN_OUTER_AIR_BAG_PRESSURE",
    "CENTER_AIR_BAG_PRESSURE",
    "RETAINER_RING_PRESSURE",
    "RIPPLE_AIR_BAG_PRESSURE",
    "USAGE_OF_MEMBRANE",
    "USAGE_OF_PRESSURIZED_SHEET",
    "SLURRY_FLOW_LINE_A",
    "SLURRY_FLOW_LINE_B",
    "SLURRY_FLOW_LINE_C",
    "WAFER_ROTATION",
    "STAGE_ROTATION",
    "HEAD_ROTATION",
    "DRESSING_WATER_STATUS",
    "EDGE_AIR_BAG_PRESSURE",
]


@lru_cache(maxsize=1)
def load_phm_cmp() -> tuple[pd.DataFrame, pd.Series]:
    """trajectory 전체를 (WAFER_ID, STAGE)별로 평균 집계해 wafer-stage 단위 feature 반환

    features: (N, 19) - 센서 평균값
    labels: (N,) - AVG_REMOVAL_RATE
    index: MultiIndex (WAFER_ID, STAGE)
    """
    if not TRAIN_TRAJ_DIR.exists() or not TRAIN_LABEL.exists():
        raise FileNotFoundError(
            f"PHM 2016 CMP 데이터가 없음, {RAW_DIR}에 데이터셋을 두세요 "
            "(data/phm2016/README.md 참고)"
        )

    # trajectory 파일 전체 로드 후 (WAFER_ID, STAGE)별 평균
    frames = []
    for path in sorted(TRAIN_TRAJ_DIR.glob("CMP-training-*.csv")):
        df = pd.read_csv(path, usecols=["WAFER_ID", "STAGE"] + SENSOR_COLS)
        frames.append(df)
    all_traj = pd.concat(frames, ignore_index=True)
    features = all_traj.groupby(["WAFER_ID", "STAGE"])[SENSOR_COLS].mean()

    labels_df = pd.read_csv(TRAIN_LABEL)
    labels_df = labels_df.set_index(["WAFER_ID", "STAGE"])["AVG_REMOVAL_RATE"]

    # feature와 label 인덱스 정합
    common = features.index.intersection(labels_df.index)
    return features.loc[common], labels_df.loc[common]
