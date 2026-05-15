"""4-Tier 멀티에이전트 오케스트레이터 (M2에서 구현)

run_orchestrator()가 detection -> cause -> impact -> response 순으로
서브에이전트를 호출하고 각 결과를 core.schema.TierData로 합쳐 반환

설계 원칙: 특정 알람(A1)에 하드코딩하지 말 것
알람의 공정 타입(Photo/Etch/CMP)을 받아 처리하는 일반 함수로 만들면
core.pipeline.REAL_AGENT_ALARMS에 ID만 추가해 다른 알람도 확장 가능

모델: 서브에이전트 = GPT-5 mini, 오케스트레이터 = GPT-5 (OpenAI SDK)

현재는 스텁, demo.py 데이터를 그대로 반환해 프론트가 M1부터 동작하게 함
"""
from core.schema import TierData
from data import demo


def run_orchestrator(alarm_id: str) -> TierData:
    # TODO(M2/M3) detection->cause->impact->response 서브에이전트 호출로 교체
    return demo.TIER_DATA[alarm_id]
