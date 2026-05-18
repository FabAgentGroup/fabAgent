# FLOW-CMP-DOWN-001 - CMP 하류 공정 의존성과 수율 영향

## 공정 흐름

CMP (현재) → Diffusion → Implant → Metal Deposition

## CMP 이상이 하류에 미치는 영향

CMP의 재료 제거율(MRR) 이상은 wafer 두께 편차로 직결되며 후공정 전반에 영향을
미칩니다. 일반적으로:

- **Diffusion**: 두께 편차에 따라 도핑 깊이 균일도 저하, 약 10~15% 변동
- **Implant**: 표면 위치 오차로 도핑 농도 편차 발생, 약 5~10% 변동
- **Metal Deposition**: 표면 평탄도 손상 시 단차 피복성 저하

## 수율 영향

CMP MRR 이탈이 1σ 이상 발생할 때 수율 손실은 통상 1.5~3.0 %p로 보고됩니다.
특히 동일 chamber 처리 로트 전체에 영향이 미치므로 후공정 진입 보류 후 두께
재측정이 우선 조치입니다.

## 의존성 분류 기준

- current: 이상이 발생한 현재 공정
- impacted: 직접 영향을 받는 후공정 (delta 두 자리수 이상)
- minor: 영향이 경미한 후공정 (delta 한 자리수)
