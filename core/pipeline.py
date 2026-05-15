"""알람 -> Tier 데이터 라우터

components/는 이 함수 하나만 호출함
데이터가 하드코딩(demo.py)에서 오는지 실제 멀티에이전트(agents/)에서
오는지 프론트는 알 필요가 없음

실제 LLM 에이전트로 돌릴 알람을 늘리려면 REAL_AGENT_ALARMS에 ID만 추가하면 됨
"""
from core.schema import TierData
from data import demo

# LLM 멀티에이전트로 처리할 알람
REAL_AGENT_ALARMS = {"A1"}


def get_tier_data(alarm_id: str) -> TierData | None:
    """알람 ID로 4-Tier 분석 결과를 반환, 데이터가 없으면 None"""
    if alarm_id in REAL_AGENT_ALARMS:
        from agents.orchestrator import run_orchestrator

        return run_orchestrator(alarm_id)
    return demo.TIER_DATA.get(alarm_id)
