# D2. FAISS vs 키워드 매칭 검색 비교

동일 쿼리 집합에 대해 두 백엔드의 검색 결과·latency를 비교합니다.
현재 knowledge 코퍼스 규모(약 10개 문서)에서의 결과입니다.

## 실험 설정

- 코퍼스: agents/rag/knowledge/*.md (현재 약 10개 한국어 도메인 문서)
- 키워드: 단어 빈도 합계 랭킹 (`agents.rag.store.keyword_search`)
- FAISS: sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` 임베딩 + IndexFlatIP (코사인)
- 쿼리 6건 (의미 우회 쿼리 3건 포함, 키워드 직접 매칭이 약한 경우)

## 쿼리별 결과

| 쿼리 | 키워드 결과 | FAISS 결과 | 겹침 | kw(ms) | fs(ms) |
|---|---|---|---|---|---|
| CD 산포 직접 | INC-AUTO-2026-05-18-A1, FMEA-PH-007, FLOW-PH-DOWN-001 | FLOW-PH-DOWN-001, INC-2024-0312, FMEA-PH-007 | 2/3 | 0.56 | 287.15 |
| CMP 직접 | SOP-CMP-SLURRY-001, INC-CMP-2025-0142, FLOW-CMP-DOWN-001 | SOP-CMP-SLURRY-001, FLOW-CMP-DOWN-001, INC-ET-2024-0301 | 2/3 | 0.48 | 97.23 |
| Etch 직접 | FMEA-ET-004, INC-ET-2024-0301, INC-AUTO-2026-05-18-A1 | INC-ET-2024-0301, FMEA-ET-004, FLOW-PH-DOWN-001 | 2/3 | 0.53 | 10.69 |
| 의미 우회 1 | INC-AUTO-2026-05-18-A1, SOP-PH-LENS-002, INC-2024-0312 | SOP-PH-LENS-002, INC-2024-0312, FMEA-ET-004 | 2/3 | 0.55 | 259.00 |
| 의미 우회 2 | INC-AUTO-2026-05-18-A1, FLOW-PH-DOWN-001, FLOW-CMP-DOWN-001 | FMEA-ET-004, INC-CMP-2025-0142, INC-ET-2024-0301 | 0/3 | 0.51 | 215.09 |
| 의미 우회 3 | INC-AUTO-2026-05-18-A1, SOP-PH-LENS-002, SOP-CMP-SLURRY-001 | SOP-PH-LENS-002, SOP-CMP-SLURRY-001, INC-CMP-2025-0142 | 2/3 | 0.48 | 313.42 |

## 집계

| 지표 | 키워드 | FAISS |
|---|---|---|
| 평균 latency | 0.52 ms | 197.10 ms |
| 결과 겹침 평균 (top-3 기준) | 1.7/3 | - |

## 트레이드오프

| 측면 | 키워드 매칭 | FAISS 벡터 |
|---|---|---|
| 의미·동의어 매칭 | 직접 어휘 일치만 | ✅ 임베딩 기반 의미 유사도 |
| Latency (10문서) | ✅ 극소 (1ms 미만 가능) | ~ms (인덱스 검색 + 임베딩) |
| 콜드 스타트 | ✅ 없음 | 모델 로딩 ~수초 (캐시 후 즉시) |
| 메모리 | ✅ 거의 0 | ~120MB (multilingual ST 모델) |
| 코퍼스 확장(100+ 문서) | 어휘 못 잡으면 무력 | ✅ 의미로 잡음 |
| 의존성 | 표준 라이브러리만 | sentence-transformers + faiss-cpu |

## 채택

**두 백엔드 모두 유지, 환경변수 `RAG_BACKEND=faiss`로 전환**. 현 코퍼스 규모에서는 키워드 매칭이 충분히 정확하고 빠르며 의존성이 적어 기본값. 
코퍼스가 50~100개 이상으로 확장되거나 의미 우회 쿼리 비율이 높아지면 FAISS로 전환 권장. 동일 인터페이스라 코드 변경 없이 전환 가능.
