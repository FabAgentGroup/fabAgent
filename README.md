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
파이프라인으로 통합하는 운영 플랫폼 MVP입니다.

각 단계가 자기 역할에 특화된 ML 모델/RAG/도메인 지식 도구를 호출하는 Tool-using Agent로
구성되어, 단일 LLM 챗봇과 달리 추적 가능하고 모듈화된 의사결정 흐름을 제공합니다.

## 핵심 특징

- **4-Tier 멀티 에이전트** — 탐지(ML)·원인(LLM+RAG)·영향(LLM+RAG+WIP)·대응(LLM+RAG)
- **실데이터 기반** — UCI SECOM(범용) + PHM 2016 CMP(공정 특화 실측 25개 명명 센서)
- **자가 학습 루프** — 운영자 승인 시 분석 결과가 인시던트 DB(.md)에 자동 기록되어 다음 RAG 검색에 즉시 반영
- **이중 RAG 백엔드** — 키워드 매칭(기본) / FAISS 벡터 검색(환경변수로 전환)
- **확장 인터페이스** — `core/pipeline.REAL_AGENT_ALARMS`에 알람 ID 추가만으로 새 공정 확장

## 아키텍처

```
┌─────────────────┐
│  알람 인박스    │  사이드바에서 알람 선택
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  core/pipeline.get_tier_data(alarm_id)                      │
│  ┌─ A1 (Photo)  ─┐  ┌─ A2 (Etch)  ─┐  ┌─ A3 (CMP)  ─┐      │
│  │ SECOM         │  │ SECOM        │  │ PHM 2016 CMP │      │
│  └──────┬────────┘  └──────┬───────┘  └──────┬───────┘      │
│         └──────────────────┼──────────────────┘              │
│                            ▼                                 │
│             agents/orchestrator (결정론적 시퀀서)            │
│  ┌──────┬─────────────┬──────────────┬──────────────┐       │
│  │Tier 1│   Tier 2    │    Tier 3    │    Tier 4    │       │
│  │이상  │  원인 분석  │ 영향 평가    │ 대응 권고    │       │
│  │탐지  │  LLM+RAG    │ LLM+RAG+WIP  │ LLM+RAG      │       │
│  │IsoF  │             │ 결정론 lots  │ 결정론 refs  │       │
│  └──┬───┴──────┬──────┴──────┬───────┴──────┬───────┘       │
│     └──────────┴─────────────┴──────────────┘                │
│                            ▼                                 │
│              core/schema.TierData (단일 계약)                │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │ Streamlit UI (cascade 등장)  │
              │ Tier 4 승인 → 작업지시서     │
              │           + 자가 학습 루프   │
              │           (knowledge .md 추가)│
              └──────────────────────────────┘
```

## 데이터 & 모델

| 알람 | 공정 step | 데이터 | 모델 / 기술 |
|---|---|---|---|
| A1 | Photo (노광) | UCI SECOM (590 익명 센서) | IsolationForest + GPT-5 mini + RAG |
| A2 | Etch (식각) | UCI SECOM (다른 fail row) | IsolationForest + GPT-5 mini + RAG |
| A3 | CMP (연마) | **PHM 2016 CMP (25개 명명 센서, SLURRY_FLOW 등)** | IsolationForest + GPT-5 mini + RAG |

SECOM은 익명 처리된 표준 벤치마크라 공정 step 라벨이 narrative입니다 (한계 명시). PHM 2016 CMP는 실제 CMP 공정 센서 데이터로 step-specific 추론이 가능합니다.

## 정량 평가 결과 요약

| 실험 | 결정 | 핵심 결과 |
|---|---|---|
| **D1**: Tier 1 모델 비교 | IsolationForest 채택 | PR-AUC 0.129 (LOF 0.089, OC-SVM 0.098, baseline 0.119 대비 우위) |
| **D2**: RAG 검색 방식 | 키워드 매칭 기본, FAISS 옵션 | 10문서 코퍼스에서 키워드 0.5ms vs FAISS ~100ms, 의미 우회 쿼리에서 FAISS 우위 |
| **D5**: Multi-Agent vs Single LLM | Multi-Agent 채택 | Single이 빠르고($0.008 vs $0.018) 저렴하나 Multi는 모듈화·확장성·detailed 권고(1.6~1.9배)에서 우위 |

상세 표·그래프·시행착오는 [experiments/README.md](experiments/README.md) 참고.

## 실행

### 로컬

```bash
pip install -r requirements.txt
cp .env.example .env           # OPENAI_API_KEY 입력
streamlit run app.py --server.port 8501
```

PHM 2016 CMP 캐시(`data/phm2016/phm_cmp_features.csv`)는 저장소에 포함되어 별도 다운로드가 필요 없습니다. raw trajectory 데이터를 직접 다루려면 `data/phm2016/README.md` 참고.

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
│   └── pipeline.py              # 알람 → Tier 데이터 라우터, REAL_AGENT_ALARMS
├── agents/
│   ├── orchestrator.py          # 4-Tier 결정론적 시퀀서 + lru_cache
│   ├── detection.py             # Tier 1 (IsoForest, SECOM/PHM 디스패치)
│   ├── cause.py impact.py response.py  # Tier 2/3/4 LLM + RAG
│   ├── llm.py                   # OpenAI 클라이언트 + 모델 설정
│   └── rag/
│       ├── store.py             # 키워드 매칭 + 백엔드 디스패치
│       ├── faiss_store.py       # FAISS 벡터 검색
│       ├── learn.py             # 자가 학습 루프 (INC-AUTO-*.md 자동 기록)
│       └── knowledge/           # 도메인 문서 (INC/FMEA/SOP/FLOW)
├── data/
│   ├── demo.py                  # 알람 정의 + A2/A3 fallback 하드코딩
│   ├── wip.py                   # 영향 WIP 결정론 데이터
│   ├── secom/                   # SECOM 로더 + 전처리 + raw .data
│   └── phm2016/                 # PHM 2016 CMP 로더 + 사전 집계 CSV
├── experiments/                 # 정량 비교 실험 결과
│   ├── tier1_detection/         # D1
│   ├── retrieval_compare/       # D2
│   └── multi_vs_single/         # D5
├── styles/main.css              # 디자인 시스템
└── tests/
```

## 기술 스택

- **프론트**: Streamlit 1.36+
- **백엔드**: OpenAI SDK (`gpt-5-mini`)
- **ML**: scikit-learn (IsolationForest, LOF, OC-SVM)
- **RAG**: 키워드 매칭 (기본) / sentence-transformers + FAISS (옵션)
- **데이터**: pandas, UCI SECOM, PHM 2016 CMP Data Challenge
- **Python**: 3.11+

## 한계와 향후 확장

- **SECOM의 익명성**: 590개 센서가 어느 공정·물리량인지 비공개라 A1/A2의 step 라벨은 시연용 narrative
- **knowledge 문서**: 시연용 합성 도메인 문서 (실 fab의 사내 SOP·인시던트 DB로 교체 가능)
- **고도화 방향**: LangGraph 기반 동적 분기, Autoencoder 앙상블, NetworkX 공정 의존성 그래프 시각화, 실 MES/SPC 어댑터 연동
