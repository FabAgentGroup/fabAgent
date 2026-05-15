"""OpenAI 클라이언트와 모델 설정

서브에이전트(cause/impact/response) = SUBAGENT_MODEL
오케스트레이터는 현재 결정론적 시퀀서라 LLM 호출 없음
모델명을 여기 한 곳에서 관리해 교체를 쉽게 함
"""
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

SUBAGENT_MODEL = "gpt-5-mini"


@lru_cache(maxsize=1)
def client() -> OpenAI:
    """OpenAI 클라이언트, 첫 호출 시 1회만 생성"""
    return OpenAI()
