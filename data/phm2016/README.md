# PHM 2016 CMP Dataset

CMP(Chemical Mechanical Planarization, 화학 기계적 연마) 공정 실측 데이터셋입니다.
A3 알람(CMP Step 이상)의 Tier 1 이상 탐지에서 사용합니다.

## 개요

- 출처: PHM Society Data Challenge 2016
- 1,981 wafer × 2 stage(A/B), 25개 센서 실측값 + 평균 재료 제거율(MRR) 라벨
- 센서 이름이 모두 공개되어 있어 도메인 해석이 가능합니다 (SECOM의 익명성과 대조)

## 주요 센서

- 압력: `PRESSURIZED_CHAMBER_PRESSURE`, `RETAINER_RING_PRESSURE`, `MAIN_OUTER_AIR_BAG_PRESSURE` 등
- 회전: `WAFER_ROTATION`, `STAGE_ROTATION`, `HEAD_ROTATION`
- 슬러리 유량: `SLURRY_FLOW_LINE_A/B/C`
- 사용량: `USAGE_OF_BACKING_FILM`, `USAGE_OF_DRESSER`, `USAGE_OF_POLISHING_TABLE` 등

## 준비 방법

원본 ZIP을 `data/phm2016/raw/`에 풀어두세요. 압축 해제 후 다음 구조가 되어야 합니다.

```
data/phm2016/raw/
├── CMP-training-removalrate.csv       # 학습용 정답 라벨
├── CMP-test-removalrate.csv
└── CMP-data/
    ├── training/CMP-training-NNN.csv  # trajectory 시계열 (185개)
    └── test/CMP-test-NNN.csv
```

raw 데이터는 약 160MB로 git에 포함되지 않습니다(`.gitignore`).

## 로더 사용

```python
from data.phm2016.loader import load_phm_cmp

features, labels = load_phm_cmp()
# features: (N, 19) — wafer-stage 단위 센서 평균
# labels: (N,) — AVG_REMOVAL_RATE
# index: MultiIndex (WAFER_ID, STAGE)
```

trajectory 전체를 (WAFER_ID, STAGE)별로 평균 집계하여 wafer-stage 단위 feature
vector를 만듭니다. 첫 호출 시 약 10~30초가 소요되며 이후는 `lru_cache`로 즉시
응답합니다.

## 알람 매핑

A3(CMP Step 이상) 알람이 이 데이터의 특정 wafer에 매핑됩니다 (`agents/detection.py`의
`ALARM_WAFER`). MRR이 평균에서 크게 벗어난 wafer를 선택하여 이상 시나리오로
사용합니다.
