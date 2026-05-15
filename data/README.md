# 데이터

## SECOM (Tier 1 이상 탐지용)

UCI SECOM 반도체 제조 공정 센서 데이터셋을 사용합니다.

- 규모: 1,567 row × 590 sensor feature, pass/fail 라벨
- 출처: https://archive.ics.uci.edu/dataset/179/secom
- Tier 1 이상 탐지 에이전트가 이 데이터로 이상 점수와 기여 피처를 계산합니다.

### 준비 방법

`secom.data`, `secom_labels.data` 두 파일을 `data/secom/raw/` 에 둡니다.
raw 데이터는 git에 포함하지 않으므로(`.gitignore`) 각자 내려받아야 합니다.

로드는 `data/secom/loader.py`의 `load_secom()`을 사용합니다.

### 알람 매핑

SECOM은 익명화된 데이터라 lot ID·공정 step 정보가 없습니다. MVP에서는 fail 라벨이
붙은 특정 row 하나를 알람 A1(Photo Step 이상)의 대상 웨이퍼로 지정해 사용합니다.

## demo.py (A2·A3용)

A2·A3는 실제 데이터 대신 시연용 하드코딩 데이터를 사용합니다 (`data/demo.py`).
