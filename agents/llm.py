"""OpenAI 클라이언트와 모델 설정

서브에이전트(cause/impact/response) = SUBAGENT_MODEL
오케스트레이터는 현재 결정론적 시퀀서라 LLM 호출 없음
모델명을 여기 한 곳에서 관리해 교체를 쉽게 함

LangSmith 트레이싱: 환경변수 LANGSMITH_TRACING=true 면 wrap_openai 로 모든 LLM 호출 자동 캡처
"""
import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

SUBAGENT_MODEL = "gpt-5-mini"


def _langsmith_enabled() -> bool:
    return os.getenv("LANGSMITH_TRACING", "").lower() in ("true", "1", "yes")


@lru_cache(maxsize=1)
def client() -> OpenAI:
    """OpenAI 클라이언트, 첫 호출 시 1회만 생성

    LANGSMITH_TRACING=true 면 langsmith.wrappers.wrap_openai 로 감싸
    모든 chat.completions.create 호출이 자동으로 LangSmith 대시보드에 트레이스로 기록됨
    """
    base = OpenAI()
    if _langsmith_enabled():
        try:
            from langsmith.wrappers import wrap_openai

            return wrap_openai(base)
        except ImportError:
            pass
    return base
