# FabAgent Experiments

핵심 의사결정마다 정량 비교 실험 + 트레이드오프 표를 남겨, 발표 시 "왜 이 선택을 했는가"를 측정된 근거로 설명할 수 있도록 합니다.

## 실험 목록

| ID | 실험 | 비교 | 결과 |
|---|---|---|---|
| **D1** | Tier 1 이상 탐지 모델 비교 | IsoForest / LOF / OC-SVM / baseline | [tier1_detection/results.md](tier1_detection/results.md) |
| **D2** | RAG 검색 방식 비교 | 키워드 매칭 vs FAISS 벡터 | [retrieval_compare/results.md](retrieval_compare/results.md) |
| **D5** | 멀티 에이전트 vs Single LLM | 분리·전문화 vs 통합 호출 | [multi_vs_single/results.md](multi_vs_single/results.md) |

## 핵심 결정 요약

각 실험에서 채택된 결정과 트레이드오프:

### D1. 이상 탐지 모델 → **IsolationForest 채택**

- PR-AUC 0.129로 비교 모델 중 최고
- SECOM은 비지도 이상 탐지가 어려운 표준 벤치마크 (문헌 ROC-AUC ~0.6 범위)
- 트레이드오프: Autoencoder/LSTM은 더 복잡한 패턴 가능하지만 학습 데이터·시간 비용 큼

### D2. RAG 검색 → **키워드 매칭 기본, FAISS 옵션 제공**

- 현 코퍼스(약 10문서)에서는 키워드가 빠르고 정확하며 의존성 적음
- FAISS는 의미 우회 쿼리에서 유리, 코퍼스 확장(50+) 시 채택 권장
- 환경변수 `RAG_BACKEND=faiss`로 즉시 전환 가능 (동일 인터페이스)

### D5. 멀티 에이전트 vs Single LLM → **멀티 에이전트 채택**

| 영역 | 우위 |
|---|---|
| 속도·비용 | Single (2.6배 빠름, 2.2배 저렴) |
| 응답 깊이 (조치 권고 수) | Multi (1.6~1.9배 detailed) |
| 모듈화·확장성·자가학습 | Multi |
| schema·citation 정확도 | 동등 (양쪽 strict JSON 100%) |

- 비용 절대값이 두 방식 모두 $0.01~0.02로 미미해 cost-aware할 필요는 없음
- 운영 환경(사업부별 Tier 책임자 분리, 새 step 확장)에서는 Multi의 모듈화·확장성이 결정적

## 실행 방법

```bash
# Tier 1 모델 벤치마크
.venv/bin/python -m experiments.tier1_detection.benchmark

# RAG 검색 비교
.venv/bin/python -m experiments.retrieval_compare.benchmark

# 멀티 에이전트 vs Single LLM
.venv/bin/python -m experiments.multi_vs_single.benchmark
```
