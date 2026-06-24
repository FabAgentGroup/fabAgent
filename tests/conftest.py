"""결정론 파이프라인 회귀 테스트 공유 픽스처

트리아지·커몬낼리티는 LLM 없이 100% 재현되므로(seed 42 고정), 합성 ground-truth
(data/synth_scenario.PLANTED_INCIDENTS)를 정답으로 두고 회귀를 잠근다
"""
import pytest

from agents.triage import triage
from data.fdc.stream import load_alarm_stream


@pytest.fixture(scope="session")
def alarms():
    return load_alarm_stream()


@pytest.fixture(scope="session")
def triage_result(alarms):
    return triage(alarms)


@pytest.fixture(scope="session")
def incidents(triage_result):
    return triage_result["incidents"]
