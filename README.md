# FabAgent

반도체 공정 이상의 **탐지 → 원인 분석 → 영향 평가 → 대응 권고**를 하나의
멀티 에이전트 파이프라인으로 통합하는 운영 플랫폼 MVP입니다.

## 아키텍처

```
알람 클릭 → core/pipeline.get_tier_data(alarm_id)
              ├─ A1 (Photo): agents/ 실제 LLM 멀티에이전트 + RAG
              │              └ Tier 1은 SECOM 센서 데이터로 이상 탐지
              └─ A2·A3:      data/demo.py 하드코딩
           → core/schema.TierData (단일 계약면)
           → components/ 가 Streamlit으로 렌더
```

프론트엔드는 데이터가 실제 에이전트에서 오는지 하드코딩인지 알지 못합니다.
실제 에이전트로 돌릴 알람을 늘리려면 `core/pipeline.REAL_AGENT_ALARMS`에
ID만 추가하면 됩니다.

## 파일 구조

```
fabagent/
├── app.py                  # 엔트리포인트
├── components/             # Streamlit UI (프론트 담당)
├── core/
│   ├── schema.py           # Tier1~4 데이터 계약 ★ 양쪽 공유
│   └── pipeline.py         # 알람 → Tier 데이터 라우터
├── data/
│   ├── demo.py             # A2·A3 하드코딩 데이터
│   └── secom/              # UCI SECOM 데이터셋 + 로더 (Tier 1 이상 탐지용)
├── agents/                 # A1 실제 멀티에이전트 (백엔드 담당)
│   ├── orchestrator.py
│   ├── detection.py / cause.py / impact.py / response.py
│   └── rag/                # 도메인 지식 검색
├── styles/main.css         # 디자인 시안 CSS
└── assets/
```

## 기술 스택

- **프론트**: Streamlit 1.36+ (의존성 최소화 — `streamlit-extras` 등 미사용)
- **백엔드**: OpenAI SDK — 서브에이전트 `GPT-5 mini`, 오케스트레이터 `GPT-5`
- **데이터**: UCI SECOM 공개 데이터셋 (Tier 1 이상 탐지), pandas
- **Python**: 3.11+

데이터셋 준비 방법은 `data/README.md`를 참고하세요.

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env        # OPENAI_API_KEY 입력
streamlit run app.py --server.port 8501
```

## 개발 마일스톤

| 단계 | 내용 | 담당 |
|---|---|---|
| M0 | 레포 골격 · `schema.py` 합의 · 설정 파일 | 같이 |
| M1 | Streamlit UI 전체 (`demo.py` 데이터로) | 프론트 |
| M2 | `agents/` — A1 4단계 오케스트레이션 + RAG | 백엔드 |
| M3 | A1을 실제 에이전트로 스위치 · 통합 테스트 | 같이 |
| M4 | 시연 리허설 (개발 가이드 15장 체크리스트) | 같이 |

M1·M2는 `core/schema.py`만 고정되면 완전히 병렬로 작업할 수 있습니다.

## 브랜치 전략

- 기본 브랜치는 `develop`이며, 직접 푸시하지 않고 PR로만 머지합니다.
- `feat/streamlit-ui` · `feat/agents-a1` · `feat/css-port` 로 작업을 분담합니다.
- `core/schema.py`를 가장 먼저 작은 PR로 머지한 뒤 병렬 작업을 시작합니다.
