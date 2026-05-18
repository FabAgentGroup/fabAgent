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
# 사전 집계 캐시 (배포용, ~400KB) - raw 없이도 동작
CACHED_FEATURES = Path(__file__).parent / "phm_cmp_features.csv"

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
    """캐시 CSV가 있으면 그걸 사용, 없으면 raw trajectory 집계 후 캐시 저장

    features: (N, 19) - 센서 평균값
    labels: (N,) - AVG_REMOVAL_RATE
    index: MultiIndex (WAFER_ID, STAGE)
    """
    if CACHED_FEATURES.exists():
        return _load_cached()
    return _build_and_cache()


def _load_cached() -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(CACHED_FEATURES, index_col=["WAFER_ID", "STAGE"])
    labels = df["AVG_REMOVAL_RATE"]
    features = df.drop(columns=["AVG_REMOVAL_RATE"])
    return features, labels


def _build_and_cache() -> tuple[pd.DataFrame, pd.Series]:
    """raw trajectory에서 wafer-stage 단위로 평균 집계, 결과를 캐시 CSV로 저장"""
    if not TRAIN_TRAJ_DIR.exists() or not TRAIN_LABEL.exists():
        raise FileNotFoundError(
            f"PHM 2016 CMP 데이터가 없음, {RAW_DIR}에 데이터셋을 두거나 "
            f"{CACHED_FEATURES} 캐시 파일이 필요합니다 (data/phm2016/README.md 참고)"
        )

    frames = []
    for path in sorted(TRAIN_TRAJ_DIR.glob("CMP-training-*.csv")):
        df = pd.read_csv(path, usecols=["WAFER_ID", "STAGE"] + SENSOR_COLS)
        frames.append(df)
    all_traj = pd.concat(frames, ignore_index=True)
    features = all_traj.groupby(["WAFER_ID", "STAGE"])[SENSOR_COLS].mean()

    labels_df = pd.read_csv(TRAIN_LABEL)
    labels_df = labels_df.set_index(["WAFER_ID", "STAGE"])["AVG_REMOVAL_RATE"]

    common = features.index.intersection(labels_df.index)
    features = features.loc[common]
    labels = labels_df.loc[common]

    # 캐시 저장 (배포 시 raw 없이도 동작하도록)
    combined = features.copy()
    combined["AVG_REMOVAL_RATE"] = labels
    combined.to_csv(CACHED_FEATURES)

    return features, labels
