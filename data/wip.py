"""WIP(Work-In-Progress) 모의 데이터

실 fab에선 MES/WIP 시스템에서 조회되는 값
MVP에서는 알람별로 영향 받는 lot 수를 결정론적으로 반환해 LLM 환각을 피함
Tier 3 영향 평가에서 impact_lots 필드 채울 때 사용
"""
from core.schema import ImpactLot

WIP_BY_ALARM: dict[str, list[ImpactLot]] = {
    "A1": [
        {"label": "가공 중", "lots": 3, "wafers": 75},
        {"label": "대기 중", "lots": 5, "wafers": 125},
    ],
}


def get_affected_wip(alarm_id: str) -> list[ImpactLot]:
    """알람 ID로 영향 WIP 정보를 반환, 매핑이 없으면 빈 리스트"""
    return WIP_BY_ALARM.get(alarm_id, [])
