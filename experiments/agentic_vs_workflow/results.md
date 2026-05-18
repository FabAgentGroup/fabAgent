# Workflow vs Agentic - 정량 비교

동일한 4-Tier pipeline을 두 가지 패턴으로 실행해 정량 비교합니다.
- **Workflow**: Tier 2/3/4 각 단계가 사전 RAG 1회 + LLM 1회 (구버전)
- **Agentic**: Tier 2/3/4 각 단계가 LLM tool calling 루프 (현재 채택)

알람: A1, A2, A3 (총 3건, SECOM + PHM CMP)

## 결과 요약 (3 알람 평균)

| 지표 | Workflow | Agentic | 배수 |
|---|---|---|---|
| LLM 호출 / 알람 | 3.0 | 9.0 | x3.0 |
| Tool 호출 / 알람 | 0.0 | 13.0 | - |
| 유니크 인용 / 알람 | 4.0 | 5.0 | x1.2 |
| 입력 토큰 / 알람 | 5890 | 20474 | x3.5 |
| 출력 토큰 / 알람 | 5174 | 12574 | x2.4 |
| Latency / 알람 (Tier 2~4) | 83474 ms | 194066 ms | x2.3 |
| 비용 / 알람 (USD) | $0.01182 | $0.03027 | x2.6 |

## 시각화

### 호출 횟수·인용 깊이
![Calls](charts/calls_citations.png)

### Tier별 Latency
![Latency](charts/latency_per_tier.png)

### 비용
![Cost](charts/cost.png)

## 알람별 상세

### A1

| 패턴 | Tier | LLM | Tools | Latency(ms) |
|---|---|---|---|---|
| workflow | tier2 | 1 | 0 | 29758 |
| workflow | tier3 | 1 | 0 | 7819 |
| workflow | tier4 | 1 | 0 | 35569 |
| agentic | tier2 | 3 | 3 | 58921 |
| agentic | tier3 | 3 | 4 | 48383 |
| agentic | tier4 | 3 | 7 | 74462 |

- Workflow 인용: ['FMEA-PH-007', 'INC-2024-0312', 'INC-AUTO-2026-05-18-A1', 'SOP-PH-LENS-002']
- Agentic 인용: ['ASML-PH-01', 'FMEA-PH-007', 'INC-2024-0289', 'INC-2024-0312', 'INC-AUTO-2026-05-18-A1']

### A2

| 패턴 | Tier | LLM | Tools | Latency(ms) |
|---|---|---|---|---|
| workflow | tier2 | 1 | 0 | 34208 |
| workflow | tier3 | 1 | 0 | 21659 |
| workflow | tier4 | 1 | 0 | 30072 |
| agentic | tier2 | 3 | 3 | 82107 |
| agentic | tier3 | 3 | 4 | 47700 |
| agentic | tier4 | 3 | 7 | 84102 |

- Workflow 인용: ['FMEA-CMP-003', 'FMEA-ET-004', 'INC-ET-2024-0301', 'SOP-PH-LENS-002']
- Agentic 인용: ['FLOW-PH-DOWN-001', 'FMEA-ET-004', 'INC-2024-0312', 'INC-CMP-2025-0142', 'INC-ET-2024-0301', 'SOP-PH-LENS-002']

### A3

| 패턴 | Tier | LLM | Tools | Latency(ms) |
|---|---|---|---|---|
| workflow | tier2 | 1 | 0 | 20936 |
| workflow | tier3 | 1 | 0 | 25591 |
| workflow | tier4 | 1 | 0 | 44811 |
| agentic | tier2 | 3 | 3 | 69289 |
| agentic | tier3 | 3 | 4 | 48960 |
| agentic | tier4 | 3 | 4 | 68274 |

- Workflow 인용: ['FMEA-CMP-003', 'INC-CMP-2025-0142', 'INC-ET-2024-0301', 'SOP-CMP-SLURRY-001']
- Agentic 인용: ['FLOW-CMP-DOWN-001', 'FMEA-CMP-003', 'INC-CMP-2025-0142', 'SOP-CMP-SLURRY-001']

## 핵심 인사이트

1. **인용 깊이 1.2배** - agentic은 도구를 자율 호출해 다양한 소스(INC/FMEA/SOP/incident DB)를 결합
2. **호출 비용 2.6배** - LLM 호출이 평균 3회 → 9회, 입력 토큰도 3.5배
3. **Latency 2.3배** - tool calling 루프 + synthesis 추가 호출의 자연스러운 비용
4. **agentic만의 정성 신호**: tool 호출 패턴 자체가 reasoning trace - 어떤 정보를 왜 찾았는지 감사·재현 가능

## 채택 결론

**현재 채택: Agentic**
- 인용 깊이·근거 다양성이 결정적 - 반도체 fab 도메인에선 multi-source 근거가 안전성·신뢰성 결정
- 비용 2.6배 증가는 알람당 $18.45/1000회 수준으로 사업적 영향 무시 가능
- Tool 호출 로그가 자체적인 audit trail이 되어 production observability에 유리

Latency가 critical한 시나리오에선 Workflow로 환경변수 토글 추가 검토 가능 (현재 미구현).
