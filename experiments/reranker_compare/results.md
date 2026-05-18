# D9 (D6 후속): 한국어 reranker 평가

D6에서 `BAAI/bge-reranker-base`(영어 학습)가 Hybrid 대비 효과 없음이 확인되어,
한국어 특화 reranker `Dongjin-kr/ko-reranker`로 재평가합니다.

## 실험 설정

- 쿼리: D2의 6개 대표 쿼리 (직접 3, 의미 우회 3)
- 백엔드: hybrid (BM25+FAISS+RRF) top-10 후보를 두 reranker로 재정렬
- 채점: CRAG grader (gpt-4o-mini)가 top-3 결과를 0~1로 평가
- 비교: hybrid (no rerank) / BAAI (영어) / ko-reranker (한국어)

## 결과 요약 (6 쿼리 평균)

| 모드 | 평균 relevance | rerank 평균 latency | vs No Rerank |
|---|---|---|---|
| hybrid (no rerank) | 0.734 | 0 ms | baseline |
| BAAI/bge-reranker-base (영어) | 0.714 | 315 ms | -0.020 |
| Dongjin-kr/ko-reranker (한국어) | 0.703 | 826 ms | -0.031 |

## 시각화

![Reranker 비교](charts/reranker_comparison.png)

## 쿼리별 상세

| 쿼리 | hybrid | BAAI (EN) | ko-reranker (KO) |
|---|---|---|---|
| CD 산포 직접 | 0.87 | 0.82 | 0.87 |
| CMP 직접 | 0.75 | 0.77 | 0.85 |
| Etch 직접 | 0.75 | 0.65 | 0.57 |
| 의미 우회 1 | 0.70 | 0.63 | 0.78 |
| 의미 우회 2 | 0.82 | 0.87 | 0.62 |
| 의미 우회 3 | 0.52 | 0.55 | 0.53 |

## 핵심 인사이트

1. **No Rerank baseline**: 0.734
2. **영어 reranker (BAAI)**: 0.714 (vs baseline -0.020) - D6에서 본 패턴 재확인
3. **한국어 reranker (Dongjin-kr)**: 0.703 (vs baseline -0.031)
4. **결론**: 두 reranker 모두 본 코퍼스에선 hybrid에 미달

## 채택

**두 reranker 모두 본 코퍼스에선 hybrid 단독에 미달** (BAAI -0.020, ko-reranker -0.031).
근본 원인: 코퍼스가 ~10문서로 작아 hybrid top-3이 이미 정답에 근접 → reranker가 더 좋게 정렬할 여지 부족.
**D6 결론 (코퍼스 확장이 reranker 효용의 선결 조건) 재확인**. 코퍼스 100+ 시 재평가.
