# D2. Retrieval 백엔드 비교 (production-grade)

쿼리 집합에 대해 4가지 백엔드의 검색 결과·latency를 비교합니다.
현재 knowledge 코퍼스 약 10개 한국어 도메인 문서.

## 실험 설정

- 코퍼스: `agents/rag/knowledge/*.md`
- 백엔드 4종:
  - **keyword**: 단어 빈도 매칭 (baseline)
  - **FAISS**: sentence-transformer 임베딩 + 코사인 (dense vector)
  - **Hybrid**: BM25 + FAISS + RRF (production 표준)
  - **Hybrid+Rerank**: hybrid top-10 후보를 BAAI/bge-reranker-base로 재정렬 (production 정밀)
- 쿼리 6건 (의미 우회 3건 포함)

## 쿼리별 결과

### CD 산포 직접 - `Photo Step CD-X 산포 원인 렌즈 노광`

| 백엔드 | 결과 | latency |
|---|---|---|
| keyword | INC-AUTO-2026-05-18-A1, FMEA-PH-007, FLOW-PH-DOWN-001 | 3.00ms |
| faiss | FLOW-PH-DOWN-001, INC-2024-0312, INC-AUTO-2026-05-18-A1 | 29.77ms |
| hybrid | INC-AUTO-2026-05-18-A1, INC-2024-0312, FMEA-PH-007 | 7.14ms |
| hybrid+rerank | INC-2024-0312, INC-AUTO-2026-05-18-A1, FMEA-PH-007 | 243.38ms |

### CMP 직접 - `CMP 슬러리 유량 이상 SLURRY_FLOW`

| 백엔드 | 결과 | latency |
|---|---|---|
| keyword | SOP-CMP-SLURRY-001, INC-CMP-2025-0142, INC-AUTO-2026-05-18-A1 | 0.51ms |
| faiss | SOP-CMP-SLURRY-001, FLOW-CMP-DOWN-001, INC-ET-2024-0301 | 21.59ms |
| hybrid | SOP-CMP-SLURRY-001, FLOW-CMP-DOWN-001, INC-CMP-2025-0142 | 5.80ms |
| hybrid+rerank | INC-CMP-2025-0142, SOP-CMP-SLURRY-001, FMEA-CMP-003 | 240.45ms |

### Etch 직접 - `Etch 트렌치 깊이 부족 식각 가스`

| 백엔드 | 결과 | latency |
|---|---|---|
| keyword | FMEA-ET-004, INC-ET-2024-0301, INC-AUTO-2026-05-18-A1 | 0.52ms |
| faiss | INC-ET-2024-0301, FMEA-ET-004, FLOW-PH-DOWN-001 | 6.83ms |
| hybrid | FMEA-ET-004, INC-ET-2024-0301, FLOW-PH-DOWN-001 | 5.71ms |
| hybrid+rerank | INC-ET-2024-0301, FMEA-ET-004, FMEA-PH-007 | 239.85ms |

### 의미 우회 1 - `노광 장비 표면 오염 청소`

| 백엔드 | 결과 | latency |
|---|---|---|
| keyword | INC-AUTO-2026-05-18-A1, SOP-PH-LENS-002, INC-2024-0312 | 0.47ms |
| faiss | SOP-PH-LENS-002, INC-2024-0312, FMEA-ET-004 | 25.10ms |
| hybrid | FMEA-ET-004, INC-2024-0312, FMEA-PH-007 | 5.99ms |
| hybrid+rerank | INC-2024-0289, INC-2024-0312, SOP-PH-LENS-002 | 244.07ms |

### 의미 우회 2 - `후공정 수율 손실 정량 영향`

| 백엔드 | 결과 | latency |
|---|---|---|
| keyword | FLOW-PH-DOWN-001, INC-AUTO-2026-05-18-A1, FLOW-CMP-DOWN-001 | 0.53ms |
| faiss | FMEA-ET-004, INC-CMP-2025-0142, INC-ET-2024-0301 | 24.72ms |
| hybrid | FMEA-ET-004, FMEA-CMP-003, FMEA-PH-007 | 7.10ms |
| hybrid+rerank | FMEA-PH-007, FMEA-ET-004, FLOW-PH-DOWN-001 | 243.45ms |

### 의미 우회 3 - `정비 주기 표준 가이드`

| 백엔드 | 결과 | latency |
|---|---|---|
| keyword | INC-AUTO-2026-05-18-A1, SOP-PH-LENS-002, SOP-CMP-SLURRY-001 | 0.52ms |
| faiss | SOP-PH-LENS-002, SOP-CMP-SLURRY-001, INC-CMP-2025-0142 | 25.06ms |
| hybrid | SOP-PH-LENS-002, SOP-CMP-SLURRY-001, INC-AUTO-2026-05-18-A1 | 5.89ms |
| hybrid+rerank | SOP-PH-LENS-002, FMEA-CMP-003, FMEA-PH-007 | 242.87ms |

## 집계 - 평균 Latency

| 백엔드 | 평균 latency |
|---|---|
| keyword | 0.93 ms |
| faiss | 22.18 ms |
| hybrid | 6.27 ms |
| hybrid+rerank | 242.35 ms |

## 트레이드오프

| 측면 | keyword | FAISS | Hybrid | Hybrid+Rerank |
|---|---|---|---|---|
| 도메인 용어 정확 매칭 | ✅ | ❌ | ✅ | ✅ |
| 의미·동의어 매칭 | ❌ | ✅ | ✅ | ✅ |
| 정밀한 관련성 평가 | ❌ | ❌ | ❌ | ✅ |
| Latency | 매우 빠름 | 보통 | 보통 | 느림 (CrossEncoder) |
| 모델 의존성 | 없음 | ST(~120MB) | ST(~120MB) | ST + Reranker(~280MB) |
| 코퍼스 확장(100+) 견고성 | 약함 | 강함 | **매우 강함** | **매우 강함** |

## 채택

**기본 backend = `hybrid_rerank`**. production 표준 패턴. 환경변수 `RAG_BACKEND`로 4가지 모두 전환 가능.

- 코퍼스 100문서 이상: hybrid_rerank의 정밀도 우위 결정적
- MVP·시연 환경: hybrid도 충분 (rerank 모델 다운로드 시간 절약)
- 단순 키워드 검색만 필요: keyword (의존성 없음)
