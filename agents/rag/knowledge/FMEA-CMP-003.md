# FMEA-CMP-003 — CMP 공정 실패 모드 분석

## 대상

CMP(Chemical Mechanical Planarization) 공정의 주요 실패 모드와 원인, 영향, 검출
방법을 정리합니다.

## 실패 모드

### 1. 재료 제거율(MRR) 폭주 또는 부족

- 잠재 원인: 슬러리 유량 이상, 패드 마모, 압력 설정 오류
- 영향: 두께 편차 → 후공정 패턴 결함, 수율 손실
- 검출: AVG_REMOVAL_RATE 모니터링, SLURRY_FLOW_LINE 유량 SPC

### 2. 표면 균일도 저하

- 잠재 원인: RETAINER_RING_PRESSURE 편차, MAIN_OUTER_AIR_BAG_PRESSURE 불균형
- 영향: 후공정 Photo 단계의 포커스 편차 유발
- 검출: 두께 매핑, 압력 센서 SPC

### 3. 패드 컨디션 악화

- 잠재 원인: 드레서 사용량(USAGE_OF_DRESSER) 한계 초과, DRESSING_WATER_STATUS 비정상
- 영향: MRR 변동성 증가, 스크래치 발생
- 검출: 드레서 사용량 추적, 시각 검사

## 우선순위

MRR 폭주는 즉시 후공정 영향이 크고 회수가 어려워 최우선 관리 대상입니다. 원인
중 슬러리 라인 이상은 펌프 제어와 직접 연관되어 자동 인터록 적용이 효과적입니다.
