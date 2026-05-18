# RAG Eval (RAGAS) - 백엔드별 답 품질 정량 비교

같은 알람(A3, CMP)에 대해 두 retrieval 백엔드의 Tier 2(원인 분석) 결과를 RAGAS로 평가합니다.

## 설정

- 평가 LLM: gpt-5-mini
- 평가 임베딩: text-embedding-3-small
- Metric:
  - **Faithfulness**: 답이 검색된 context에 충실한가 (환각 측정)
  - **Response Relevancy**: 답이 질문에 관련 있는가
  - **LLM Context Precision (no ref)**: 검색된 context 중 관련된 것의 비율

## 결과

| Backend | user_input | retrieved_contexts | response | faithfulness | answer_relevancy | llm_context_precision_without_reference |
|---|---|---|---|---|---|---|
| hybrid | CMP Step 이상 재료 제거율(MRR) SLURRY_FLOW_LINE_B SLURRY_FLOW_LINE_A SLURRY_FLOW_LINE_C 원인 분석 공정 이상 | ['# SOP-CMP-SLURRY-001 - CMP 슬러리 관리 표준 절차\n\n## 목적\n\nCMP 공정의 슬러리 공급 시스템 점검과 이상 발생 시 대응 절차를 표준화합니다.\n\n## 적용 범위\n\n전 사업부 CMP 설비의 SLURRY_FLOW_LINE_A/B/C 공급 시스템.\n\n## 정기 점검 주기\n\n- 슬러리 유량 캘리브레이션: 7일\n- 펌프 동작 점검: 14일\n- 슬러리 농도 측정: 매 로트\n\n## 이상 발생 시 대응 절차\n\n1. 챔버 정지 및 후공정 진입 차단\n2. SLURRY_FLOW_LINE_A/B/C 측정값 확인 후 정상 범위 이탈 여부 판단\n3. 펌프 제어 신호 점검 및 펌웨어 버전 확인\n4. 필요 시 펌프 교체 (예상 3시간)\n5. 시험 wafer로 MRR 정상 범위 재현 확인\n6. 챔버 재가동 및 로트 진입 재개\n\n## 기록\n\n이상 사례는 인시던트 DB에 기록하며, 슬러리 유량 추세는 일일 SPC 리포트에\n포함합니다.\n', '# FMEA-CMP-003 - CMP 공정 실패 모드 분석\n\n## 대상\n\nCMP(Chemical Mechanical Planarization) 공정의 주요 실패 모드와 원인, 영향, 검출\n방법을 정리합니다.\n\n## 실패 모드\n\n### 1. 재료 제거율(MRR) 폭주 또는 부족\n\n- 잠재 원인: 슬러리 유량 이상, 패드 마모, 압력 설정 오류\n- 영향: 두께 편차 → 후공정 패턴 결함, 수율 손실\n- 검출: AVG_REMOVAL_RATE 모니터링, SLURRY_FLOW_LINE 유량 SPC\n\n### 2. 표면 균일도 저하\n\n- 잠재 원인: RETAINER_RING_PRESSURE 편차, MAIN_OUTER_AIR_BAG_PRESSURE 불균형\n- 영향: 후공정 Photo 단계의 포커스 편차 유발\n- 검출: 두께 매핑, 압력 센서 SPC\n\n### 3. 패드 컨디션 악화\n\n- 잠재 원인: 드레서 사용량(USAGE_OF_DRESSER) 한계 초과, DRESSING_WATER_STATUS 비정상\n- 영향: MRR 변동성 증가, 스크래치 발생\n- 검출: 드레서 사용량 추적, 시각 검사\n\n## 우선순위\n\nMRR 폭주는 즉시 후공정 영향이 크고 회수가 어려워 최우선 관리 대상입니다. 원인\n중 슬러리 라인 이상은 펌프 제어와 직접 연관되어 자동 인터록 적용이 효과적입니다.\n', '# FLOW-CMP-DOWN-001 - CMP 하류 공정 의존성과 수율 영향\n\n## 공정 흐름\n\nCMP (현재) → Diffusion → Implant → Metal Deposition\n\n## CMP 이상이 하류에 미치는 영향\n\nCMP의 재료 제거율(MRR) 이상은 wafer 두께 편차로 직결되며 후공정 전반에 영향을\n미칩니다. 일반적으로:\n\n- **Diffusion**: 두께 편차에 따라 도핑 깊이 균일도 저하, 약 10~15% 변동\n- **Implant**: 표면 위치 오차로 도핑 농도 편차 발생, 약 5~10% 변동\n- **Metal Deposition**: 표면 평탄도 손상 시 단차 피복성 저하\n\n## 수율 영향\n\nCMP MRR 이탈이 1σ 이상 발생할 때 수율 손실은 통상 1.5~3.0 %p로 보고됩니다.\n특히 동일 chamber 처리 로트 전체에 영향이 미치므로 후공정 진입 보류 후 두께\n재측정이 우선 조치입니다.\n\n## 의존성 분류 기준\n\n- current: 이상이 발생한 현재 공정\n- impacted: 직접 영향을 받는 후공정 (delta 두 자리수 이상)\n- minor: 영향이 경미한 후공정 (delta 한 자리수)\n'] | - 슬러리 유량 과다 — 펌프 제어/캘리브레이션 또는 밸브 이상 (65%): Tier‑1 탐지에서 상위 기여 센서가 SLURRY_FLOW_LINE_A/B/C로 모두 보고되었고(이상 점수 0.95), 이는 유량 자체의 이상이 MRR 상승을 직접적으로 유발할 가능성이 가장 높음. SOP-CMP-SLURRY-001은 SLURRY_FLOW_LINE_A/B/C 공급 시스템의 점검 절차(펌프 제어 신호, 펌웨어 확인, 유량 캘리브레이션 주기)를 명시하여 펌프 제어/캘리브레이션 오류가 유력한 원인임을 뒷받침한다. 또한 FMEA-CMP-003은 MRR 폭주(또는 부족)의 잠재 원인으로 '슬러리 유량 이상'을 명시하고 있어 유량 관련 하드웨어/제어 이상이 MRR 급증을 초래할 가능성이 크다.
- 슬러리 농도/품질 변화(농도 상승 또는 오염으로 인한 연마력 증가) (25%): SOP-CMP-SLURRY-001은 슬러리 농도를 '매 로트' 측정하도록 규정하고 있어 로트별 농도 변화가 즉시 MRR에 영향을 줄 수 있음. 유량 센서 이상과 동반되지 않더라도 농도(연마제 농도) 상승은 동일 조건에서 MRR을 증가시킬 수 있으므로, 로트별 슬러리 농도 측정값 및 최근 슬러리 배치(혼합/교체) 기록 확인이 필요하다.
- 패드/드레서 상태 이상(패드 컨디션 변화로 인한 연삭성 증가) (10%): FMEA-CMP-003은 패드 컨디션 악화(드레서 사용량 초과, DRESSING_WATER_STATUS 비정상 등)가 MRR 변동성 증가를 유발한다고 명시함. 비록 현재 상위 기여 센서가 슬러리 유량이지만, 패드가 과도하게 컨디셔닝되었거나 드레싱 동작 이상으로 표면 거칠기가 증가하면 MRR이 상승할 수 있으므로 패드/드레서 사용 기록 및 시각 검사 결과를 병행 점검할 필요가 있다. | 0.800 | 0.456 | 1.000 |
| hybrid_rerank | CMP Step 이상 재료 제거율(MRR) SLURRY_FLOW_LINE_B SLURRY_FLOW_LINE_A SLURRY_FLOW_LINE_C 원인 분석 공정 이상 | ['# INC-CMP-2025-0142 - CMP 슬러리 유량 이상에 의한 재료 제거율 폭주\n\n## 분류\n\n- 유형: 공정 인시던트\n- 공정: CMP (Chemical Mechanical Planarization)\n- 사업부: 메모리 1동\n- 발생일: 2025-01-14\n\n## 증상\n\nCMP 공정에서 평균 재료 제거율(AVG_REMOVAL_RATE)이 정상 범위(70~90 nm/min)를 크게\n벗어나 4,000 nm/min 이상으로 측정되었습니다. 동일 chamber에서 처리된 연속 로트\n대부분이 영향을 받았습니다.\n\n## 원인\n\n슬러리 공급 라인(SLURRY_FLOW_LINE_A/B/C) 유량이 정상치 대비 비정상적으로 높게\n유지되었음이 확인되었습니다. 정확히는 슬러리 공급 펌프 제어 신호 오류로 인해\n세 라인 모두 동시에 과공급된 사례입니다.\n\n## 조치\n\n- 슬러리 공급 펌프 즉시 정지 및 교체\n- 영향 로트 후공정 진입 보류 및 두께 계측으로 재작업 여부 판단\n- 펌프 제어 로직 펌웨어 업데이트\n\n## 재발 방지\n\n슬러리 유량 임계값을 신설하고, 임계 초과 시 자동 알람 + 챔버 인터록이 작동하도록\n모니터링 체계를 강화하였습니다.\n', '# FMEA-CMP-003 - CMP 공정 실패 모드 분석\n\n## 대상\n\nCMP(Chemical Mechanical Planarization) 공정의 주요 실패 모드와 원인, 영향, 검출\n방법을 정리합니다.\n\n## 실패 모드\n\n### 1. 재료 제거율(MRR) 폭주 또는 부족\n\n- 잠재 원인: 슬러리 유량 이상, 패드 마모, 압력 설정 오류\n- 영향: 두께 편차 → 후공정 패턴 결함, 수율 손실\n- 검출: AVG_REMOVAL_RATE 모니터링, SLURRY_FLOW_LINE 유량 SPC\n\n### 2. 표면 균일도 저하\n\n- 잠재 원인: RETAINER_RING_PRESSURE 편차, MAIN_OUTER_AIR_BAG_PRESSURE 불균형\n- 영향: 후공정 Photo 단계의 포커스 편차 유발\n- 검출: 두께 매핑, 압력 센서 SPC\n\n### 3. 패드 컨디션 악화\n\n- 잠재 원인: 드레서 사용량(USAGE_OF_DRESSER) 한계 초과, DRESSING_WATER_STATUS 비정상\n- 영향: MRR 변동성 증가, 스크래치 발생\n- 검출: 드레서 사용량 추적, 시각 검사\n\n## 우선순위\n\nMRR 폭주는 즉시 후공정 영향이 크고 회수가 어려워 최우선 관리 대상입니다. 원인\n중 슬러리 라인 이상은 펌프 제어와 직접 연관되어 자동 인터록 적용이 효과적입니다.\n', '# FLOW-CMP-DOWN-001 - CMP 하류 공정 의존성과 수율 영향\n\n## 공정 흐름\n\nCMP (현재) → Diffusion → Implant → Metal Deposition\n\n## CMP 이상이 하류에 미치는 영향\n\nCMP의 재료 제거율(MRR) 이상은 wafer 두께 편차로 직결되며 후공정 전반에 영향을\n미칩니다. 일반적으로:\n\n- **Diffusion**: 두께 편차에 따라 도핑 깊이 균일도 저하, 약 10~15% 변동\n- **Implant**: 표면 위치 오차로 도핑 농도 편차 발생, 약 5~10% 변동\n- **Metal Deposition**: 표면 평탄도 손상 시 단차 피복성 저하\n\n## 수율 영향\n\nCMP MRR 이탈이 1σ 이상 발생할 때 수율 손실은 통상 1.5~3.0 %p로 보고됩니다.\n특히 동일 chamber 처리 로트 전체에 영향이 미치므로 후공정 진입 보류 후 두께\n재측정이 우선 조치입니다.\n\n## 의존성 분류 기준\n\n- current: 이상이 발생한 현재 공정\n- impacted: 직접 영향을 받는 후공정 (delta 두 자리수 이상)\n- minor: 영향이 경미한 후공정 (delta 한 자리수)\n'] | - 슬러리 공급 펌프 제어 오류 → SLURRY 라인 과공급 (75%): Tier‑1 탐지에서 상위 기여 센서가 SLURRY_FLOW_LINE_B/A/C로 동일하게 나타나고(이상 점수 0.95), INC‑CMP‑2025‑0142 사례는 슬러리 공급 펌프 제어 신호 오류로 세 라인이 동시에 과공급되어 AVG_REMOVAL_RATE가 정상(70~90 nm/min)을 크게 초과(4,000 nm/min 이상)한 동일 증상을 보고합니다. FMEA‑CMP‑003도 MRR 폭주 주요 잠재 원인으로 슬러리 유량 이상을 명시하고 SLURRY_FLOW_LINE 유량 SPC로 검출 가능하다고 기술하고 있어, 현재 탐지 결과와 문서 사례가 직접적으로 일치합니다. 영향 범위가 동일 챔버의 연속 로트로 확대될 수 있음도 문서에 명시되어 있어 즉각적 원인으로 가장 유력합니다.
- 패드 상태(드레서 사용량 과다) 또는 압력 설정 오류에 따른 MRR 증가 (25%): FMEA‑CMP‑003에서 MRR 폭주의 다른 잠재 원인으로 패드 마모(드레서 사용량 초과) 및 압력 설정 오류를 명시하고 있으며, 이들 원인은 패드 컨디션 악화로 MRR이 증가하거나 균일도가 저하되는 경로를 설명합니다. 현재 슬러리 라인 신호가 주요 기여를 보인다는 점에서 2차 가능성으로 판단되며, 드레서 사용량·패드 컨디션 및 리테이너/에어백 압력 로그 검증이 필요합니다. | 0.588 | 0.000 | 1.000 |

## 해석

- **Faithfulness 높음** = LLM이 검색된 문서에 충실히 근거 (환각 적음)
- **Response Relevancy 높음** = 답이 질문에 정확히 답함
- **Context Precision 높음** = 검색된 문서가 답 생성에 실제로 기여

## 채택

정량 차이를 보고 적합한 backend 채택. 일반적으로 Hybrid+Rerank가 정밀도에서 우위.
