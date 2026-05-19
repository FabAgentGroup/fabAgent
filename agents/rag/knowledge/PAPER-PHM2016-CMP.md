# PAPER-PHM2016-CMP - PHM Society 2016 Data Challenge (CMP)

## 챌린지 개요

PHM Society의 2016 데이터 챌린지는 **화학기계 연마(CMP) 공정에서 재료 제거율 예측**을 목표로 합니다. 참가팀은 물리 기반 모델링과 통계적 접근법을 결합하여 폴리싱 성능을 추정해야 합니다.

## 시스템 구성 및 센서

CMP 공정은 다음 주요 구성요소로 이루어집니다:

- 회전하는 테이블과 폴리싱 패드
- 웨이퍼 캐리어
- **슬러리 분사기 (`SLURRY_FLOW` 등 센서 포함)**
- 패드 컨디셔닝용 드레서

데이터셋은 **25개 센서 변수(x1~x25)** 를 포함하며, 웨이퍼 식별자, 공정 단계(A·B·C), 평균 제거율(MRR)로 구성됩니다.

### 주요 명명 센서 (FabAgent에서 활용)
- `SLURRY_FLOW_LINE_A/B/C`: 슬러리 라인별 유량
- `USAGE_OF_BACKING_FILM`: backing film 마모도
- `USAGE_OF_DRESSER`: 컨디셔너 사용량
- `USAGE_OF_DRESSER_TABLE`: 드레서 테이블 마모
- `USAGE_OF_POLISHING_TABLE`: 폴리싱 테이블 마모
- `PRESSURIZED_CHAMBER_PRESSURE`: 챔버 압력
- `EDGE_AIR_KINEMATIC_VISCOSITY` 등

## 핵심 평가 지표

최종 점수는 다음으로 산정됩니다:

- **MSE 정확도: 90%** - 평균 제곱 오차 기반 예측 성능
- **물리 기반 모델링: 10%**
  - 드레서 상태 추정 (3%)
  - 폴리싱 패드 상태 추정 (3%)
  - 기타 매개변수 영향 (4%)

## 챌린지 결과

- 2016년 9월 8일 종료
- 상위 3팀이 각각 $600, $400, $200의 상금 수여
- **최고 점수**: Apocalypse 팀의 90.05

## FabAgent에서의 활용

본 데이터셋은 FabAgent의 A3 (CMP Step 이상) 알람의 실측 데이터 소스로 활용됩니다.
Tier 1 이상 탐지에서 IsolationForest가 wafer_id=2058207580, stage=A를 분석하여
SLURRY_FLOW_LINE_A·USAGE_OF_DRESSER·PRESSURIZED_CHAMBER_PRESSURE 등의 기여 센서를 식별합니다.

## 출처
- [PHM Society 2016 Data Challenge](https://phmsociety.org/conference/annual-conference-of-the-phm-society/annual-conference-of-the-prognostics-and-health-management-society-2016/phm-data-challenge-4/)
- 본 문서는 PHM Society 공개 자료를 발췌·요약한 것입니다
