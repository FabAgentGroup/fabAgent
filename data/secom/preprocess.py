"""SECOM 전처리

이상 탐지 모델에 넣기 전 공통 전처리
- 전부 결측이거나 분산이 0(상수)인 컬럼 제거
- 남은 결측치는 중앙값으로 임퓨테이션
- StandardScaler로 스케일링

agents/detection.py와 experiments/ 양쪽에서 공용으로 사용
fit은 train 데이터에만, transform은 train/test 공통으로 적용
"""
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler


class SecomPreprocessor:
    """SECOM 센서 데이터 전처리, sklearn 스타일 fit/transform"""

    def __init__(self, var_threshold: float = 0.0):
        self.var_threshold = var_threshold
        self.keep_cols: list[str] = []
        self.imputer = SimpleImputer(strategy="median")
        self.scaler = StandardScaler()

    def fit(self, X: pd.DataFrame) -> "SecomPreprocessor":
        # 전부 결측인 컬럼 제거 후, 분산이 임계 이하(거의 상수)인 컬럼도 제거
        non_empty = X.columns[X.notna().any()]
        variances = X[non_empty].var()
        self.keep_cols = list(variances[variances > self.var_threshold].index)

        kept = X[self.keep_cols]
        self.imputer.fit(kept)
        self.scaler.fit(self.imputer.transform(kept))
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        kept = X[self.keep_cols]
        return self.scaler.transform(self.imputer.transform(kept))

    def fit_transform(self, X: pd.DataFrame) -> np.ndarray:
        return self.fit(X).transform(X)
