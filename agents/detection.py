"""Tier 1 이상 탐지 에이전트

알람을 데이터셋의 특정 wafer에 매핑해 이상 점수와 기여 피처를 계산
- A1, A2: SECOM 공개 데이터셋 (다른 fail row 매핑)
- A3: PHM 2016 CMP 공개 데이터셋 (CMP step 실측, 25개 명명 센서)

모델: IsolationForest (벤치마크에서 PR-AUC 우수)
이상 점수: 학습 분포 대비 백분위로 0~1 정규화
기여 피처: 표준화 값의 절대크기 Top-N (정상 분포에서 가장 벗어난 센서)
"""
from functools import lru_cache

import numpy as np
from sklearn.ensemble import IsolationForest

from core.schema import Tier1
from data.phm2016.loader import load_phm_cmp
from data.secom.loader import load_secom
from data.secom.preprocess import SecomPreprocessor

RANDOM_STATE = 42
TOP_N_FEATURES = 3

# 알람 -> 데이터 소스 매핑
# wafers: 데모 컨텍스트상 영향 웨이퍼 수
ALARM_WAFER = {
    "A1": {"source": "secom", "row": 2, "wafers": 25},
    "A2": {"source": "secom", "row": 10, "wafers": 18},
    "A3": {"source": "phm_cmp", "wafer_id": 2058207580, "stage": "A", "wafers": 30},
}


@lru_cache(maxsize=1)
def _fit_secom():
    """SECOM 전체로 전처리기와 IsolationForest 학습, 첫 호출 시 1회"""
    X, _ = load_secom()
    pre = SecomPreprocessor().fit(X)
    Xz = pre.transform(X)
    model = IsolationForest(n_estimators=200, random_state=RANDOM_STATE)
    model.fit(Xz)
    train_scores = -model.score_samples(Xz)
    return X, pre, model, train_scores


@lru_cache(maxsize=1)
def _fit_phm_cmp():
    """PHM CMP 전체로 표준화 + IsolationForest 학습, 첫 호출 시 1회"""
    from sklearn.preprocessing import StandardScaler

    features, _ = load_phm_cmp()
    scaler = StandardScaler().fit(features.values)
    Xz = scaler.transform(features.values)
    model = IsolationForest(n_estimators=200, random_state=RANDOM_STATE)
    model.fit(Xz)
    train_scores = -model.score_samples(Xz)
    return features, scaler, model, train_scores


def _detect_secom(alarm: dict, mapping: dict) -> Tier1:
    X, pre, model, train_scores = _fit_secom()
    Xz = pre.transform(X.iloc[[mapping["row"]]])

    raw_score = float(-model.score_samples(Xz)[0])
    score = float((train_scores < raw_score).mean())

    deviations = np.abs(Xz[0])
    top_idx = np.argsort(deviations)[::-1][:TOP_N_FEATURES]
    features = [
        {"name": pre.keep_cols[i], "value": round(float(deviations[i]), 2)}
        for i in top_idx
    ]
    return {
        "score": round(score, 2),
        "features": features,
        "lot": {"id": alarm["lot_id"], "wafers": mapping["wafers"]},
    }


def _detect_phm_cmp(alarm: dict, mapping: dict) -> Tier1:
    features, scaler, model, train_scores = _fit_phm_cmp()
    key = (mapping["wafer_id"], mapping["stage"])
    if key not in features.index:
        raise KeyError(f"PHM CMP에 없는 wafer/stage: {key}")

    row = features.loc[[key]].values
    Xz = scaler.transform(row)

    raw_score = float(-model.score_samples(Xz)[0])
    score = float((train_scores < raw_score).mean())

    deviations = np.abs(Xz[0])
    top_idx = np.argsort(deviations)[::-1][:TOP_N_FEATURES]
    col_names = list(features.columns)
    out_features = [
        {"name": col_names[i], "value": round(float(deviations[i]), 2)}
        for i in top_idx
    ]
    return {
        "score": round(score, 2),
        "features": out_features,
        "lot": {"id": alarm["lot_id"], "wafers": mapping["wafers"]},
    }


def run_detection(alarm: dict) -> Tier1:
    mapping = ALARM_WAFER.get(alarm["id"])
    if mapping is None:
        raise ValueError(f"매핑 없는 알람: {alarm['id']}")

    source = mapping["source"]
    if source == "secom":
        return _detect_secom(alarm, mapping)
    if source == "phm_cmp":
        return _detect_phm_cmp(alarm, mapping)
    raise ValueError(f"알 수 없는 데이터 소스: {source}")
