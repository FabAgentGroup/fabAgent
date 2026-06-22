"""FabAgent Tier 데이터 계약

프론트엔드(components/)와 백엔드(agents/)가 공유하는 단일 계약면
이 구조를 바꾸면 양쪽 다 영향받으므로, 변경은 작은 PR로 먼저 합의 예정

모든 Tier 데이터는 plain dict로 다룸 - components/가 HTML f-string에서
dict 키로 직접 접근하기 때문, TypedDict는 타입 힌트/문서 용도
"""
from typing import Optional, TypedDict


# Tier 1 이상 탐지
class Feature(TypedDict):
    name: str
    value: float


class LotRef(TypedDict):
    id: str
    wafers: int


class Tier1(TypedDict):
    score: float             # 이상 점수 (0~1)
    features: list[Feature]  # 기여 피처 Top-N (value 내림차순)
    lot: LotRef


# Tier 2 원인 분석
class Cause(TypedDict):
    name: str
    pct: int                # 추정 기여도 (%)
    evidence: str
    citations: list[str]    # RAG 근거 문서 ID


class Tier2(TypedDict):
    causes: list[Cause]


# Tier 3 공정 간 영향 평가
class Dependency(TypedDict):
    stage: str
    delta: str
    tag: str
    kind: str               # "current" | "impacted" | "minor"


class ImpactLot(TypedDict):
    label: str
    lots: int
    wafers: int


class Tier3(TypedDict):
    yield_loss: float       # 예상 수율 손실 (%p)
    dependencies: list[Dependency]
    impact_lots: list[ImpactLot]


# Tier 4 대응 권고
class Action(TypedDict):
    text: str
    meta: Optional[str]


class Reference(TypedDict):
    id: str
    desc: str


# Tier 4 디스포지션 (영향 WIP 처리 의사결정)
class DispositionOption(TypedDict):
    action: str                 # "continue" | "hold" | "rework" | "scrap"
    label: str
    expected_cost_usd: int
    cost_range_usd: list[int]   # [lo, hi] (p_defect 신뢰구간 반영)
    rationale: str
    feasible: bool


class Disposition(TypedDict):
    recommended: str
    recommended_label: str
    options: list[DispositionOption]  # expected_cost 오름차순
    savings_vs_worst_usd: int
    confidence: float
    robust: bool                # 추천이 p_defect 불확실성 내에서 유지되는가
    inputs: dict                # 감사용 입력 (process/n_wafers/p_defect/가치 등)


class Tier4(TypedDict):
    immediate: list[Action]
    longterm: list[Action]
    refs: list[Reference]
    disposition: Disposition


# 전체
class TierData(TypedDict):
    tier1: Tier1
    tier2: Tier2
    tier3: Tier3
    tier4: Tier4
