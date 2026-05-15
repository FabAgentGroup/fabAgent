"""4-Tier 멀티에이전트 오케스트레이터

run_orchestrator()가 detection -> cause -> impact -> response 순으로
서브에이전트를 호출하고 각 결과를 core.schema.TierData로 합쳐 반환

각 Tier가 이전 Tier의 출력을 입력으로 받는 고정 의존 순서이므로
별도 LLM 라우터 없이 결정론적으로 시퀀싱 (속도/비용/예측성 모두 유리)

LLM 3회 호출이 직렬로 일어나 첫 호출은 1분 안팎이 걸리므로
프로세스 내 결과 캐시로 동일 알람 재호출 시 즉시 응답하게 함
"""
from functools import lru_cache

from agents.cause import run_cause
from agents.detection import run_detection
from agents.impact import run_impact
from agents.response import run_response
from core.schema import TierData
from data.demo import DEFAULT_ALARMS


def _find_alarm(alarm_id: str) -> dict:
    for a in DEFAULT_ALARMS:
        if a["id"] == alarm_id:
            return a
    raise ValueError(f"알람 ID를 찾을 수 없음: {alarm_id}")


@lru_cache(maxsize=8)
def run_orchestrator(alarm_id: str) -> TierData:
    alarm = _find_alarm(alarm_id)
    tier1 = run_detection(alarm)
    tier2 = run_cause(alarm, tier1)
    tier3 = run_impact(alarm, tier1, tier2)
    tier4 = run_response(alarm, tier1, tier2, tier3)
    return {"tier1": tier1, "tier2": tier2, "tier3": tier3, "tier4": tier4}
