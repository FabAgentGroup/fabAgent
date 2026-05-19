---
title: FabAgent
emoji: 🟦
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.36.0
app_file: app.py
pinned: false
license: mit
short_description: 반도체 공정 이상의 탐지·원인·영향·대응을 잇는 멀티 에이전트 운영 플랫폼
---

# FabAgent

반도체 공정 이상의 **탐지 → 원인 분석 → 영향 평가 → 대응 권고**를 하나의 멀티 에이전트
파이프라인으로 통합하는 운영 플랫폼입니다.

각 Tier가 **자율 도구 호출(tool calling)** 과 **조건부 라우팅** 을 통해 의사결정을 진행하는
진짜 LLM agent로 구성되어, 단일 LLM 챗봇과 달리 추적 가능하고 모듈화된 의사결정 흐름과
auditable한 reasoning trace를 제공합니다.

## 핵심 특징

- **4-Tier multi-agent system** - 탐지(ML) · 원인(agentic RAG) · 영향(tool-using) · 대응(tool-using)
- **Tool-using agent** - 7개 도메인 도구를 LLM이 자율 선택·반복 호출 (OpenAI function calling)
- **Supervisor agent** - LLM이 Tier 2 결과를 보고 후속 workflow path(proceed_full / fast_track / escalate) 동적 결정
- **조건부 라우팅** - LangGraph에서 severity gate + cause confidence retry + supervisor 분기 (3단계)
- **CRAG self-correction** - retrieval grader가 검색 품질 평가, 임계치 미달 시 쿼리 자동 재작성
- **LangSmith observability** - 모든 LLM·tool·agent 호출 자동 트레이스 (production-grade)
- **Production RAG** - BM25 + FAISS + Reciprocal Rank Fusion (5단계 paradigm ablation으로 검증)
- **실데이터 기반** - UCI SECOM (590 익명 센서) + PHM 2016 CMP (25개 명명 센서, 실측)
- **자가 학습 루프** - 운영자 승인 시 분석 결과가 인시던트 DB(.md)에 자동 기록 → 다음 RAG에 즉시 반영
- **정량 근거** - 핵심 의사결정마다 ablation/벤치마크/차트 (`experiments/*/results.md`)

## 아키텍처

### 4-Tier Multi-Agent Pipeline

```
┌──────────────┐
│ 알람 인박스  │  사이드바에서 알람 선택
└──────┬───────┘
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ agents/orchestrator.py - LangGraph StateGraph (조건부 + LLM-driven 라우팅)  │
│                                                                             │
│   START → [detect] ──── score < 0.30 ──→ [noise] → END    (severity gate)   │
│              │                                                              │
│              └── score ≥ 0.30 ──→ [cause]                                   │
│                                     │                                       │
│                  ┌──── max pct < 40% ─────→ [cause_retry] ──┐               │
│                  │ (output threshold)                       │               │
│                  └──── max pct ≥ 40% ──→ [supervisor] ←─────┘               │
│                                              │                              │
│                       ┌─── LLM 결정 ────────┤                              │
│                       │ proceed_full        │                              │
│                       │ escalate            ▼                              │
│                       │                  [impact] ──┐                       │
│                       │                              ▼                      │
│                       │ fast_track ──→ [fast_impact] → [response] → END    │
│                       │                              ▲                      │
│                       │                              │                      │
│                       └──────────────────────────────┘                      │
│                                                                             │
│   Tier 1: IsolationForest (ML) - SECOM/PHM 데이터 분기                       │
│   Tier 2: agentic RAG (tools: search_knowledge, lookup_incident, get_pm)    │
│   Supervisor (gpt-4o-mini): action·severity·reasoning을 LLM이 결정          │
│   Tier 3: tool-using (query_wip, get_downstream, get_yield_baseline, pm)    │
│   fast_impact: LLM 호출 없는 deterministic 경량 처리 (fast_track 전용)      │
│   Tier 4: tool-using (search, lookup_incident, get_pm, check_pm_schedule)   │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          ▼
              ┌────────────────────────┐
              │ TierData (단일 계약)   │
              └──────────┬─────────────┘
                         ▼
              ┌────────────────────────┐
              │ Streamlit UI (cascade) │
              │ Tier 4 승인 → 작업지시 │
              │   + 자가 학습 루프     │
              └────────────────────────┘
```

### 7개 Agent Tools

| 도구 | 반환 | 사용 Tier |
|---|---|---|
| `search_knowledge` | INC/FMEA/SOP/FLOW 문서 hybrid 검색 결과 | 2, 4 |
| `lookup_incident_history` | 과거 incident 구조화 레코드 (원인·해결책·yield 회복률) | 2, 4 |
| `get_pm_history` | 장비 마지막 PM 일자·경과일·overdue 여부 | 2, 3, 4 |
| `check_pm_schedule` | 다음 7일 가용 PM 윈도우 | 4 |
| `query_wip_status` | 영향 받는 WIP lot/wafer 수 | 3 |
| `get_downstream_steps` | 후공정 의존성 (typical delta·severity) | 3 |
| `get_yield_baseline` | 공정 최근 30일 yield 기준선 (%) | 3 |

LLM이 어떤 도구를 언제 호출할지 자율 결정합니다. 호출 로그가 reasoning trace = production audit trail.

## 데이터 & 모델

| 알람 | 공정 step | 데이터 | 모델 / 기술 |
|---|---|---|---|
| A1 | Photo (노광) | UCI SECOM (590 익명 센서) | IsolationForest + gpt-5-mini agent + Hybrid RAG |
| A2 | Etch (식각) | UCI SECOM (다른 fail row) | IsolationForest + gpt-5-mini agent + Hybrid RAG |
| A3 | CMP (연마) | **PHM 2016 CMP** (25개 명명 센서, SLURRY_FLOW 등) | IsolationForest + gpt-5-mini agent + Hybrid RAG |

SECOM은 익명 처리된 표준 벤치마크라 공정 step 라벨이 narrative입니다 (한계 명시).
PHM 2016 CMP는 실제 CMP 공정 센서 데이터로 step-specific 추론이 가능합니다.

## 정량 평가 요약

핵심 의사결정마다 ablation 실험을 수행하고 결과·차트·시행착오를 기록했습니다.
상세는 [experiments/README.md](experiments/README.md).

| ID | 실험 | 결정 | 핵심 수치 |
|---|---|---|---|
| **D1** | Tier 1 모델 비교 | IsolationForest | PR-AUC 0.129 (LOF 0.089, OC-SVM 0.098, baseline 0.119) |
| **D2** | Retrieval 백엔드 latency | 4 backend 검증 | keyword 0.5ms / faiss 60ms / **hybrid 54ms** / +rerank 326ms |
| **D5** | Multi vs Single LLM | Multi-Agent | 비용 $0.018 vs $0.008 (2.2x), 권고 깊이 1.6~1.9배, 모듈화 결정적 |
| **D6** | RAG paradigm 5단계 ablation | **Hybrid** 채택 | faithfulness: No RAG 0.32 → Hybrid 0.82 (2.5x). Hybrid가 모든 지표 1위 |
| **D7** | Workflow vs Agentic 비교 | **Agentic** 채택 | tool 0→13, 인용 깊이 +25%, 비용 2.6x, latency 2.3x, reasoning trace 확보 |
| **D8** | CRAG (Self-correction) ON vs OFF | CRAG **활성 유지** (관측 가치) | 품질 변화 -0.1%p (동급), refinement 발동률 20%, relevance_score 노출, 비용 +31% |
| **D9** | 한국어 reranker (Dongjin-kr/ko-reranker) vs 영어(BAAI) vs hybrid (12 docs) | 둘 다 hybrid에 미달 | hybrid 0.734 / BAAI 0.714 / ko 0.703 |
| **D10** | **D9 후속**: 코퍼스 12→34 확장 후 reranker 재평가 | **가설 검증 - 효과 완전 반전** | hybrid **0.592** / BAAI **0.709 (+0.117)** / ko **0.675 (+0.083)** |

### D6 핵심 그래프

![RAG Paradigm Evolution](experiments/rag_paradigm/charts/ragas_comparison.png)

![Quality vs Latency Trade-off](experiments/rag_paradigm/charts/tradeoff.png)

### D7 핵심 그래프

![Workflow vs Agentic - 호출 횟수](experiments/agentic_vs_workflow/charts/calls_citations.png)

![Tier별 Latency](experiments/agentic_vs_workflow/charts/latency_per_tier.png)

### D8 핵심 그래프

![CRAG 자가 정정 활동](experiments/crag_eval/charts/crag_activity.png)

![CRAG 효과 - 답변 품질](experiments/crag_eval/charts/quality.png)

## 시행착오 (Journey)

이 시스템이 처음부터 이 모양이었던 건 아닙니다. 실제로 다음 다섯 번의 큰 방향 전환을 거쳤습니다.

### 1. 더미 데이터 → 실데이터 (M1~M3)

- **시작**: `data/demo.TIER_DATA`에 하드코딩된 Tier 1~4 결과로 UI만 시연
- **문제**: 데이터 기반 의사결정이 아니라 "시나리오 영상"에 가까움. 인터뷰 부적합
- **해결**: SECOM(A1·A2) + PHM 2016 CMP(A3) 실데이터 로더 구축, Tier 1을 IsolationForest로 실제 추론

### 2. 키워드 RAG → Hybrid → +Rerank → **다시 Hybrid** (D2, D6)

- **시작**: 코퍼스가 작아서(~10문서) 단순 키워드 매칭으로 충분
- **추가**: BM25(sparse) + FAISS(dense) + Reciprocal Rank Fusion 결합. Anthropic Contextual Retrieval 패턴 적용
- **욕심**: Cross-encoder rerank(`BAAI/bge-reranker-base`)까지 추가, "production 정밀" 어필 시도
- **반전**: 5단계 paradigm ablation (D6) 결과 `Hybrid + Rerank`가 `Hybrid`보다 오히려 못함
  - `Hybrid` faithfulness 0.821, answer_relevancy 0.394
  - `Hybrid + Rerank` faithfulness 0.819, answer_relevancy **0.167** (낙폭 큼)
- **원인 분석**: ① 코퍼스가 ~10문서로 작아 Hybrid top-3이 이미 정답에 근접 ② `bge-reranker-base`가 영어 학습 모델이라 한국어 도메인 텍스트에서 점수 신호가 잡음
- **교훈**: production 패턴을 블라인드 적용하면 역효과. **정량 평가(RAGAS) 없이 'rerank가 좋다'는 통념을 그대로 끌고 갈 뻔함**
- **결정**: 기본 backend를 `hybrid_rerank` → `hybrid`로 변경. `Hybrid + Rerank`는 환경변수 옵션으로 유지 (코퍼스 100+ 확장 시 재평가 권장)

### 3. "이게 진짜 agent인가?" 자기 검증 (M5)

- **상황**: 4-Tier가 LLM 호출하니 multi-agent라고 주장하고 있었음
- **냉정한 점검**: Anthropic의 ["Building Effective Agents"](https://www.anthropic.com/engineering/building-effective-agents) 정의 기준으로 보면 현재는 **workflow** (각 Tier가 사전 정의된 RAG 한 번 + LLM 한 번)
- **agent의 정의**: LLM이 도구를 자율 선택·반복 호출, 조건부 분기, reasoning loop
- **갭**: 도구 호출 없음 / 루프 없음 / 조건부 라우팅 없음

### 4. Workflow → Agentic 전환 (현재)

- **구현**: 7개 도메인 도구 정의 (`agents/tools/`), Tier 2/3/4를 tool-calling loop + synthesis 호출 패턴으로 재작성
- **conditional routing**: LangGraph에 severity gate (Tier 1 score < 0.3 → noise) + cause confidence retry (max pct < 40 → 한 번 재시도) 분기 추가
- **정량 검증 (D7)**: workflow vs agentic 3 알람 비교
  - LLM 호출: 3 → 9 (x3.0)
  - Tool 호출: 0 → 13 (agentic의 reasoning trace)
  - 유니크 인용: 4 → 5 (+25%, 솔직히 적당한 수준)
  - 비용: $0.012 → $0.030 / 알람 (x2.6)
  - Latency: 83s → 194s (x2.3)
- **솔직한 trade-off**: 비용 2.6배가 정당화되는 이유는 인용 +25%가 아니라 **tool 호출 로그 자체가 production audit trail**. fab 환경에서 "이 권고가 왜 나왔는가"의 감사 추적이 결정적

### 5. LangGraph 도입 (M4)

- **이전**: orchestrator가 결정론적 함수 호출 시퀀스
- **현재**: LangGraph StateGraph + `lru_cache`로 컴파일된 그래프
- **이득**: ① mermaid 다이어그램 자동 추출 → 분기 시각화 ② 향후 동적 라우팅·재시도·인터럽트 확장 시 동일 구조 위에서 점진 가능

### 6. CRAG (Self-correction) 도입 - 두 번째 "정량으로 통념 반박" 사례 (D8)

- **시작**: Anthropic·LangChain이 자주 언급하는 CRAG (Corrective RAG) 패턴 도입. retrieval grader가 검색 결과를 자체 평가하고, 임계치 미달 시 쿼리를 재작성해 재검색
- **구현**: `agents/rag/crag.py` - gpt-4o-mini 기반 grader/refiner, `search_knowledge` 도구에 transparent 통합 (환경변수 `CRAG_ENABLED` 토글)
- **smoke test 결과 인상적**: gibberish 쿼리(`알수없음 xyzzy foobar`)에 대해 grader가 avg score 0.0 부여 → LLM이 `CMP 공정 실패 모드 분석 및 슬러리 관리 절차 관련 정보` 로 자동 재작성 → avg score 0.68 회복. 진짜 자가 정정 메커니즘 작동
- **반전**: 3 알람 정량 비교(D8)에서 품질 차이 사실상 없음 (faithfulness -0.1%p, relevancy -3.3%p)
- **원인 분석**:
  1. 코퍼스가 ~10문서로 작아 hybrid 검색이 이미 잘 작동
  2. agentic loop 자체가 이미 self-correction 일부 수행 (LLM이 첫 검색 결과가 부족하면 다른 쿼리로 다시 호출). CRAG와 부분 중복
  3. Refinement 발동률 20% (5번 중 1번) - 정상 쿼리에선 무발동
- **교훈**: **D6 (Rerank) 시행착오와 같은 패턴** - production 패턴을 작은 도메인 코퍼스에 블라인드 적용하면 ROI 낮음. 정량 평가 없이는 "CRAG 도입했음" 마케팅으로 끝났을 것
- **결정**: CRAG **활성 유지** (`CRAG_ENABLED=true`).
  - 품질 향상 미미하지만 인용 신뢰도(0~1 relevance_score) 가시화가 production observability에 가치
  - 비용 +31% 절대값 미미 (1000 알람당 +$2.90)
  - 코퍼스 100+ 확장 또는 한국어 reranker 도입 시 재평가 권장

### 7. 한국어 reranker 후속 평가 - D6 가설 검증 (D9)

- **시작**: D6에서 "영어 학습 reranker가 한국어 코퍼스에서 효과 없음" 가설 제시. `Dongjin-kr/ko-reranker`로 검증
- **방법**: `rerank.py`에 `RERANK_MODEL` 환경변수 추가, 6개 대표 쿼리 × 3 모드(hybrid / BAAI / ko-reranker)로 CRAG grader 채점
- **결과**: hybrid 0.734 (baseline), BAAI 0.714 (-0.020), **ko-reranker 0.703 (-0.031)**
- **반전 안에 반전**: 쿼리별로 보면 ko-reranker가 CMP(+0.10), 의미 우회 1(+0.083)에선 우위. Etch(-0.18), 의미 우회 2(-0.20)에선 손실. 전체 평균은 무승부
- **해석**: 한국어 reranker가 영어보단 도메인 적합성 약간 우위지만, **본 코퍼스 규모(~10문서)에선 hybrid top-3이 이미 충분히 정밀해 어떤 reranker도 의미 있는 이득 없음**
- **결론(잠정)**: D6 가설 부분적 재확인 - 코퍼스 규모가 진짜 원인이라는 더 큰 가설을 제시

### 10. 코퍼스 12 → 34 확장 + D10으로 가설 검증

- **시작**: D9까지 누적된 가설 "코퍼스 규모가 reranker 효용의 선결조건". 이를 정량 검증하려면 코퍼스 확장 필수
- **방법**: 합법적 공개 자료로 12개 → 34개 확장
  - 한국어 위키백과 12개 (반도체 공정 전반: Photo/Etch/CMP/이온주입/박막/포토레지스트/EUV 등)
  - SK하이닉스 뉴스룸 6개 (실제 산업 운영 관점: 식각·포토·CMP·세정)
  - 삼성반도체 공식 3개 (8대 공정·용어집·EUV)
  - SKC 소재 1개, PHM Society 2016 챌린지 1개
  - 모든 출처는 CC BY-SA 또는 공개 자료, 파일별 attribution 명시
- **D10 결과 (re-run D9 with 34 docs)**:
  - hybrid: 0.734 → **0.592** (-0.142, noise 증가)
  - BAAI: -0.020 → **+0.117** (반전!)
  - ko-reranker: -0.031 → **+0.083** (반전!)
- **검증 완료**: 가설 정확히 입증. 확장 코퍼스에서는 BM25/FAISS가 일반 자료 noise를 흡수하지만 cross-encoder가 그중에서 정답을 골라냄
- **결정**: 코퍼스 30+ 환경에서는 `RAG_BACKEND=hybrid_rerank` 권장. 데모용 12개에선 hybrid 유지
- **시리즈 의의**: D6 → D9 → D10이 portfolio narrative로 완성. "통념 → 정량 반박 → 가설 → 정량 검증"의 사이클이 정량 평가의 가치 자체를 증명

### 8. Supervisor agent - LLM-driven 동적 workflow routing

- **시작**: 기존 conditional edge는 threshold 기반(`score < 0.3` → skip, `max pct < 40` → retry). "진짜 agent라면 LLM이 맥락을 보고 결정해야 한다"
- **구현**: `agents/supervisor.py` - Tier 2 결과를 받아 3가지 action 결정
  - `proceed_full` (표준): Tier 3 → Tier 4
  - `fast_track` (단일 원인 우세): Tier 3 LLM skip, deterministic 경량 처리로 비용 절감
  - `escalate` (고위험): 정상 진행 + human review 플래그 (Tier 4 immediate 첫 항목에 🚨 prepend)
- **모델**: gpt-4o-mini (의사결정 소작업, 비용 절감)
- **LangGraph 시각화**: 3개 분기 노드 (detect, cause, supervisor) - 정적 + LLM-driven 라우팅의 조합
- **smoke test**: A1 (medium severity, 3 causes) → proceed_full, A2/A3 (high severity) → proceed_full. 현 데이터에선 모두 표준 경로 선택 (안전한 기본)

### 9. LangSmith observability 통합

- **목적**: production-grade 트레이스 대시보드. 알람별 LLM 호출 트리, tool 호출 시퀀스, latency·token 분석
- **구현**: `wrap_openai`로 모든 chat.completions.create 자동 트레이스, `@traceable` 데코레이터로 4-Tier agent + Supervisor + tool dispatcher를 nested run으로 시각화
- **토글**: 환경변수 `LANGSMITH_TRACING=true/false`로 on/off, 비활성 시 no-op (성능·기능 영향 없음)
- **포트폴리오 가치**: 인터뷰에서 "각 LLM 호출·tool 호출·token·latency 다 보입니다" 한 줄로 production-grade 인상

## 실행

### 로컬

```bash
pip install -r requirements.txt
cp .env.example .env           # OPENAI_API_KEY 입력
streamlit run app.py --server.port 8501
```

PHM 2016 CMP 캐시(`data/phm2016/phm_cmp_features.csv`)는 저장소에 포함되어 별도 다운로드가 필요 없습니다.
raw trajectory 데이터를 직접 다루려면 `data/phm2016/README.md` 참고.

### RAG 백엔드 전환

```bash
RAG_BACKEND=hybrid streamlit run app.py        # 기본값 (실측 데이터 근거 채택)
RAG_BACKEND=hybrid_rerank streamlit run app.py # 옵션: 코퍼스 확장 시
RAG_BACKEND=faiss streamlit run app.py         # 옵션: 의미 위주
RAG_BACKEND=keyword streamlit run app.py       # 옵션: 의존성 최소
```

### CRAG (Self-correction) 토글

```bash
CRAG_ENABLED=true streamlit run app.py    # 기본값 - retrieval grader + 자동 refinement
CRAG_ENABLED=false streamlit run app.py   # 비활성 - latency critical 시나리오
```

### LangSmith Observability (선택)

모든 LLM·tool·agent 호출이 [LangSmith](https://smith.langchain.com) 대시보드로 자동 전송됩니다.

```bash
# .env 에 추가 (https://smith.langchain.com 에서 API 키 발급)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=fabagent
```

활성 시:
- `wrap_openai`가 모든 `chat.completions.create` 호출을 자동 트레이스 (Tier 2/3/4 agent, CRAG grader, RAGAS 평가 등)
- `@traceable` 데코레이터로 4-Tier orchestrator·각 agent·tool dispatcher를 nested run으로 시각화
- production observability: 알람별 latency / 비용 / tool 호출 트리 / error 추적

### Hugging Face Spaces 배포

1. HF Space 생성 (SDK: Streamlit)
2. 본 저장소 연결 (또는 push)
3. Space settings → Variables and secrets → `OPENAI_API_KEY` 추가
4. 자동 빌드·배포

상단 frontmatter가 HF Space 설정으로 자동 인식됩니다.

## 파일 구조

```
fabagent/
├── app.py                       # Streamlit 엔트리포인트
├── components/                  # UI 컴포넌트 (사이드바·헤더·Tier 카드·cascade)
├── core/
│   ├── schema.py                # Tier1~4 TypedDict 계약
│   └── pipeline.py              # 알람 → Tier 데이터 라우터
├── agents/
│   ├── orchestrator.py          # LangGraph StateGraph + 조건부 라우팅
│   ├── detection.py             # Tier 1 IsolationForest (SECOM/PHM 디스패치)
│   ├── cause.py                 # Tier 2 agentic RAG (tool-calling loop)
│   ├── impact.py                # Tier 3 tool-using agent
│   ├── response.py              # Tier 4 tool-using agent
│   ├── supervisor.py            # LLM-driven dynamic workflow router (proceed_full/fast_track/escalate)
│   ├── llm.py                   # OpenAI 클라이언트 + LangSmith wrap_openai 통합
│   ├── tools/                   # 7개 agent 도구
│   │   ├── knowledge.py         #   search_knowledge (RAG 검색)
│   │   ├── incident.py          #   lookup_incident_history
│   │   ├── equipment.py         #   get_pm_history, check_pm_schedule
│   │   └── process.py           #   query_wip_status, get_downstream_steps, get_yield_baseline
│   └── rag/
│       ├── store.py             # 백엔드 dispatch (keyword/faiss/hybrid/hybrid_rerank)
│       ├── faiss_store.py       # FAISS 벡터 검색
│       ├── hybrid_store.py      # BM25 + FAISS + Reciprocal Rank Fusion
│       ├── rerank.py            # Cross-encoder 재정렬 (BAAI/bge-reranker-base)
│       ├── crag.py              # CRAG self-correction (grader + query refiner)
│       ├── learn.py             # 자가 학습 루프 (INC-AUTO-*.md 자동 기록)
│       └── knowledge/           # 도메인 문서 (INC/FMEA/SOP/FLOW)
├── data/
│   ├── demo.py                  # 알람 정의
│   ├── wip.py                   # 영향 WIP 결정론 데이터
│   ├── secom/                   # SECOM 로더 + 전처리 + raw .data
│   └── phm2016/                 # PHM 2016 CMP 로더 + 사전 집계 CSV
├── experiments/                 # 정량 비교 실험 + 차트
│   ├── tier1_detection/         # D1: IsoForest / LOF / OC-SVM
│   ├── retrieval_compare/       # D2: keyword / FAISS / hybrid / +rerank
│   ├── multi_vs_single/         # D5: multi-agent vs single LLM
│   ├── rag_eval/                # RAGAS 평가 (hybrid vs hybrid_rerank)
│   ├── rag_paradigm/            # D6: 5단계 paradigm ablation
│   ├── agentic_vs_workflow/     # D7: workflow vs agentic 비교
│   ├── crag_eval/               # D8: CRAG self-correction 효과 평가
│   └── reranker_compare/        # D9: 한국어 reranker(Dongjin-kr/ko-reranker) 평가
├── docs/orchestrator_graph.mmd  # LangGraph 자동 추출 mermaid
├── styles/main.css              # 디자인 시스템
└── tests/
```

## 기술 스택

- **프론트**: Streamlit 1.36+
- **백엔드**: OpenAI SDK (`gpt-5-mini`, structured output + function calling)
- **Orchestration**: LangGraph StateGraph (조건부 + LLM-driven 라우팅, mermaid 추출)
- **Observability**: LangSmith (`wrap_openai` + `@traceable`, 옵션)
- **ML**: scikit-learn (IsolationForest, LOF, OC-SVM)
- **RAG**: rank-bm25 + sentence-transformers + FAISS + RRF (옵션: cross-encoder rerank)
- **평가**: RAGAS (faithfulness, answer_relevancy, context_precision) with gpt-4o-mini
- **데이터**: pandas, UCI SECOM, PHM 2016 CMP Data Challenge
- **Python**: 3.11+

## 한계와 향후 확장

- **SECOM의 익명성**: 590개 센서가 어느 공정·물리량인지 비공개라 A1/A2의 step 라벨은 시연용 narrative
- **knowledge 문서**: 합성 12개 + 공개 자료(위키/SK하이닉스/삼성/SKC/PHM) 22개 = **총 34개**. 실 fab 수천 문서 대비 여전히 작지만, D10에서 코퍼스 규모와 reranker 효용의 관계는 정량 검증됨
- **도구 mock data**: PM 이력·yield baseline·downstream 의존성은 in-memory mock (실 fab은 MES/EAP/YMS 어댑터로 교체)
- **한국어 reranker 검증 완료(D9)**: hybrid 단독에 미달, 코퍼스 확장이 reranker 효용의 선결조건임을 확인
- **Supervisor fast_track 시연 부재**: 현 3개 데모 알람은 모두 proceed_full 선택 - fast_track/escalate 시연을 위해선 더 다양한 알람 시나리오 필요
- **고도화 방향**: GraphRAG(공정 의존성 노드 그래프) · 실 MES/EAP/YMS 어댑터 · 한국어 reranker 전용 fine-tuning · 멀티 에이전트 negotiation (현재는 supervisor가 일방향 라우팅)
