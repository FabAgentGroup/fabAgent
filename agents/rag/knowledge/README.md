# RAG 지식 베이스

원인 분석(Tier 2)·영향 평가(Tier 3)·대응 권고(Tier 4) 에이전트가 검색하는 도메인 문서.
파일명 = citation ID. 예: `INC-2024-0312.md` → 코드에서 `load_document("INC-2024-0312")`.

## 문서 유형 (prefix별)

| Prefix | 유형 | 출처 | 갯수 |
|---|---|---|---|
| `INC-*` | 과거 인시던트 사례 | 시연용 합성 + 자가학습 자동기록 | 5 |
| `FMEA-*` | 실패 모드 분석 | 시연용 합성 | 3 |
| `SOP-*` | 표준 운영 절차 | 시연용 합성 | 2 |
| `FLOW-*` | 공정 흐름·downstream 의존성 | 시연용 합성 | 2 |
| `WIKI-*` | 한국어 위키백과 발췌 | CC BY-SA 4.0 | 12 |
| `IND-*` | 산업 자료 (SK하이닉스/삼성/SKC 뉴스룸·공식) | 각 사 공개 자료 | 9 |
| `PAPER-*` | 학회 자료 발췌 (PHM Society 등) | 학회 공개 | 1 |

**총 34개** (+ README, INC-AUTO-*는 자가학습 자동 생성)

## 문서 확장 이력

- **M2** (초기): A1 Photo 시나리오용 INC/FMEA/SOP 4개 합성
- **M3**: A2/A3 (Etch/CMP) 추가 - INC/FMEA/SOP/FLOW 8개로 확장 (총 12개)
- **D9 후속**: 합성 코퍼스의 한계가 D6/D9 실험에서 확인됨 → 공개 자료로 3배 확장
  - 한국어 위키백과 12개 (반도체 공정 전반)
  - SK하이닉스 뉴스룸 6개 (Photo/Etch/CMP 운영 관점)
  - 삼성반도체 공식 3개 (8대 공정·용어집)
  - SKC 소재 1개, PHM Society 2016 챌린지 1개
  - 총 12 → 34개로 확장

## 라이센스 주의

- `WIKI-*` 파일은 한국어 위키백과(CC BY-SA 4.0) 발췌이며 출처 명시 필수
- `IND-*` 파일은 SK하이닉스·삼성·SKC 공개 뉴스룸 자료 발췌로, 시연·교육 목적 사용
- 영리적 배포 시 각 출처의 라이센스·이용 약관 재확인 필요
- 각 파일 하단 `## 출처` 섹션 참고

## 검색 흐름

```
Tier 2/3/4 agent → search_knowledge(query) tool 호출
  → agents/rag/store.search() [RAG_BACKEND 환경변수로 dispatch]
  → 기본: hybrid (BM25 + FAISS + RRF)
  → CRAG_ENABLED=true 면 grader가 관련성 채점 + 미달 시 query refinement
  → top-K doc_id + snippet + relevance_score 반환
```

상세 비교 실험은 [experiments/README.md](../../experiments/README.md) 참고.
