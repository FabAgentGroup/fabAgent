"""Tier 1 이상 탐지 에이전트

알람을 SECOM 웨이퍼 row에 매핑해 이상 점수와 기여 피처를 계산
모델: IsolationForest (experiments/tier1_detection 벤치마크에서 PR-AUC 가장 우수)
이상 점수는 학습 분포 대비 백분위로 0~1 정규화
기여 피처는 표준화 값의 절대크기 Top-N (정상 분포에서 가장 벗어난 센서)
"""
from functools import lru_cache

import numpy as np
from sklearn.ensemble import IsolationForest

from core.schema import Tier1
from data.secom.loader import load_secom
from data.secom.preprocess import SecomPreprocessor

RANDOM_STATE = 42
TOP_N_FEATURES = 3

# SECOM은 익명화 데이터라 lot/step이 없음, MVP에선 알람을 특정 웨이퍼 row에 수동 매핑
# secom_row: fail 라벨 row 인덱스, wafers: 데모 컨텍스트상 영향 웨이퍼 수
ALARM_WAFER = {
    "A1": {"secom_row": 2, "wafers": 25},
}


@lru_cache(maxsize=1)
def _fit_model():
    """SECOM 전체로 전처리기와 IsolationForest를 학습, 첫 호출 시 1회만"""
    X, _ = load_secom()
    pre = SecomPreprocessor().fit(X)
    Xz = pre.transform(X)
    model = IsolationForest(n_estimators=200, random_state=RANDOM_STATE)
    model.fit(Xz)
    train_scores = -model.score_samples(Xz)
    return X, pre, model, train_scores


def run_detection(alarm: dict) -> Tier1:
    mapping = ALARM_WAFER.get(alarm["id"])
    if mapping is None:
        raise ValueError(f"SECOM 매핑이 없는 알람: {alarm['id']}")

    X, pre, model, train_scores = _fit_model()
    Xz = pre.transform(X.iloc[[mapping["secom_row"]]])

    raw_score = float(-model.score_samples(Xz)[0])
    # 학습 분포 대비 백분위, 높을수록 이상
    score = float((train_scores < raw_score).mean())

    # 표준화 값의 절대크기 = 정상 분포에서 벗어난 정도, Top-N
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
