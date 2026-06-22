"""Central Planner Agent (Plan-and-Execute pattern)

알람과 Tier 1 결과를 보고 전체 워크플로우 plan을 1회 LLM 호출로 산출합니다.
각 Tier executor는 plan대로 도구를 직접 호출하고 LLM 1회로 결과를 합성합니다.

기존 autonomous tool-using loop 대비:
- LLM 호출 ~70% 감소 (각 tier loop 제거)
- 재귀/무한루프 위험 원천 차단 (LLM이 tool을 자율 선택하지 않음)
- 통신 오버헤드 최소화 (synthesis context를 한 번에 구성)
- 비용·latency 큰 폭 절감 (gpt-4o-mini로 planning + gpt-5-mini로 synthesis)

설계:
- Planner가 구체적 함수 호출이 아닌 "필요한 정보 채널" (query/symptom/equipment_id 리스트)을 지정
- 각 Tier executor가 그 채널을 받아 결정론적으로 tool 호출 (병렬 가능)
- Tier executor는 단 1회 LLM 호출로 synthesis (tools 인자 없이)
"""
import json

from langsmith import traceable

from agents.llm import client
from agents.tools.equipment import ALARM_EQUIPMENT
from core.schema import Tier1

PLANNER_MODEL = "gpt-4o-mini"

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "tier2": {
            "type": "object",
            "properties": {
                "search_queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "사내 지식 검색 쿼리 (1~3개)",
                },
                "incident_symptoms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "과거 incident DB 조회용 증상 (0~2개)",
                },
                "equipment_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "PM 이력 조회 장비 ID (0~1개)",
                },
                "commonality": {
                    "type": "object",
                    "description": "MES genealogy 커몬낼리티 분석 (불량 웨이퍼 공통 엔티티 통계 추출)",
                    "properties": {
                        "process": {
                            "type": "string",
                            "description": "분석 공정 (Photo/Etch/CMP/Diffusion/Implant). 불필요하면 빈 문자열",
                        },
                        "scope_tool": {"type": "string", "description": "용의 장비로 한정 (없으면 빈 문자열)"},
                        "scope_recipe": {"type": "string", "description": "용의 recipe로 한정 (없으면 빈 문자열)"},
                    },
                    "required": ["process", "scope_tool", "scope_recipe"],
                    "additionalProperties": False,
                },
            },
            "required": ["search_queries", "incident_symptoms", "equipment_ids", "commonality"],
            "additionalProperties": False,
        },
        "tier3": {
            "type": "object",
            "properties": {
                "alarm_id": {"type": "string", "description": "WIP 조회용 알람 ID"},
                "downstream_stages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "후공정 의존성 조회 (1개)",
                },
                "yield_processes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "yield baseline 조회 (1~2개)",
                },
                "equipment_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "PM 이력 조회 장비 ID (0~1개)",
                },
            },
            "required": ["alarm_id", "downstream_stages", "yield_processes", "equipment_ids"],
            "additionalProperties": False,
        },
        "tier4": {
            "type": "object",
            "properties": {
                "search_queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "SOP 검색 쿼리 (1~3개)",
                },
                "incident_symptoms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "과거 해결책 조회 (0~2개)",
                },
                "equipment_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "PM 윈도우 조회 장비 ID (1개)",
                },
            },
            "required": ["search_queries", "incident_symptoms", "equipment_ids"],
            "additionalProperties": False,
        },
        "action": {
            "type": "string",
            "enum": ["proceed_full", "fast_track", "escalate"],
            "description": "워크플로우 분기 (Tier 3 skip 여부, escalation 플래그)",
        },
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
        "reasoning": {"type": "string"},
    },
    "required": ["tier2", "tier3", "tier4", "action", "severity", "reasoning"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 반도체 fab 인시던트 대응 시스템의 Central Planner Agent입니다.
이상 알람과 Tier 1 탐지 결과를 받아 전체 워크플로우(Tier 2 원인분석 → Tier 3 영향평가 → Tier 4 대응권고)에 필요한 정보 수집 plan을 한 번에 산출합니다.

[가용 정보 채널 - tier별]

Tier 2 (원인 분석):
- search_queries: 사내 지식(INC/FMEA/SOP/FLOW) hybrid 검색 (1~3개)
- incident_symptoms: 과거 incident DB 구조화 조회 (0~2개)
- equipment_ids: 장비 PM 이력 조회 (0~1개)
- commonality: MES genealogy로 불량 웨이퍼의 공통 엔티티(장비·챔버·슬러리·작업자)를 통계 추출
  - process: 알람 공정명을 넣으면 분석 수행. 단발성 이상이라 불필요하면 빈 문자열
  - scope_tool/scope_recipe: 용의 범위를 좁힐 장비/recipe (모르면 빈 문자열)

Tier 3 (영향 평가):
- alarm_id: WIP 조회 (반드시 1개, 알람 ID 그대로)
- downstream_stages: 후공정 의존성 (1개, 현재 공정명 - 예: "Photo", "Etch", "CMP")
- yield_processes: yield baseline 조회 (1~2개)
- equipment_ids: PM 이력 조회 (0~1개)

Tier 4 (대응 권고):
- search_queries: SOP·표준 절차 검색 (1~3개)
- incident_symptoms: 과거 해결책 조회 (0~2개)
- equipment_ids: PM 윈도우 조회 (1개, immediate 조치의 실행 가능 시점)

[routing 결정]
- action:
  - proceed_full (대부분, 표준 Tier 2 → 3 → 4)
  - fast_track (단일 원인 80%+ 우세 시 - Tier 3 LLM skip)
  - escalate (고위험·다대수 영향 - 정상 진행 + human review 플래그)
- severity: low / medium / high / critical

[중요 원칙]
- 알람과 Tier 1을 보고 가장 정보가치 큰 쿼리/조회만 선별 (불필요한 호출 제거)
- search_queries는 도메인 용어를 풍부하게 (예: "Photo CD 산포 렌즈 오염 헤이즈")
- Tier 2와 Tier 4의 search_queries는 목적이 다름:
  - Tier 2: 원인 후보 탐색용
  - Tier 4: SOP·조치 절차 탐색용
- reasoning은 한 문장으로 plan의 핵심 의도 명시"""


def _build_user_prompt(alarm: dict, tier1: Tier1) -> str:
    sensors = ", ".join(f["name"] for f in tier1["features"])
    equipment_id = alarm.get("equipment_id") or ALARM_EQUIPMENT.get(alarm["id"], "(미매핑)")
    process = alarm["title"].split()[0]
    return f"""## 이상 알람
- 공정: {alarm['title']} (current_stage: {process})
- lot: {alarm['lot_id']}
- 이상 피처: {alarm.get('feature')} {alarm.get('feature_arrow') or ''}
- 알람 ID: {alarm['id']}
- 추정 장비 ID: {equipment_id}

## Tier 1 이상 탐지 결과
- 이상 점수: {tier1['score']}
- 기여 센서(Top): {sensors}

위 알람의 전체 워크플로우(Tier 2→3→4) plan을 산출하세요."""


@traceable(name="Planner_Agent", run_type="chain")
def plan_workflow(alarm: dict, tier1: Tier1) -> dict:
    """알람 + Tier 1을 보고 전체 워크플로우 plan을 한 번에 산출

    반환: PLAN_SCHEMA 형식 dict (tier2/tier3/tier4 + action/severity/reasoning)
    """
    resp = client().chat.completions.create(
        model=PLANNER_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(alarm, tier1)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "plan", "schema": PLAN_SCHEMA, "strict": True},
        },
    )
    return json.loads(resp.choices[0].message.content)
