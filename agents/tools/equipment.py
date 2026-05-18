"""장비 관련 tools - PM 이력 조회 + 가용 윈도우

실 fab에선 EAP(Equipment Automation Program) / CIM 시스템에서 조회되는 값
오늘 기준일은 2026-05-18 (데모 고정)
"""
from datetime import date

TODAY = date(2026, 5, 18)

# 알람 ID -> 대표 장비 매핑
ALARM_EQUIPMENT = {
    "A1": "ASML-PH-01",
    "A2": "TEL-ET-03",
    "A3": "AMAT-CMP-02",
}

_EQUIPMENT = {
    "ASML-PH-01": {
        "kind": "Photo Scanner (lens, stage)",
        "process": "Photo",
        "last_pm": date(2026, 5, 4),
        "pm_cycle_days": 21,
        "next_pm_windows": ["2026-05-19 02:00~06:00", "2026-05-21 22:00~02:00"],
    },
    "TEL-ET-03": {
        "kind": "Etch Chamber",
        "process": "Etch",
        "last_pm": date(2026, 5, 11),
        "pm_cycle_days": 30,
        "next_pm_windows": ["2026-05-24 03:00~07:00"],
    },
    "AMAT-CMP-02": {
        "kind": "CMP Polisher (slurry, pad)",
        "process": "CMP",
        "last_pm": date(2026, 4, 27),
        "pm_cycle_days": 21,
        "next_pm_windows": ["2026-05-19 04:00~07:00", "2026-05-20 23:00~03:00"],
    },
    "ASM-DIF-04": {
        "kind": "Diffusion Furnace",
        "process": "Diffusion",
        "last_pm": date(2026, 4, 30),
        "pm_cycle_days": 60,
        "next_pm_windows": ["2026-05-25 06:00~10:00"],
    },
}


def get_pm_history(equipment_id: str) -> dict:
    """장비 마지막 PM 이력 + 경과일 + 다음 PM 예정일 반환

    overdue: 다음 PM 예정일을 지났는가
    """
    eq = _EQUIPMENT.get(equipment_id)
    if not eq:
        return {"error": f"등록되지 않은 장비: {equipment_id}"}
    days_since = (TODAY - eq["last_pm"]).days
    overdue = days_since > eq["pm_cycle_days"]
    return {
        "equipment_id": equipment_id,
        "kind": eq["kind"],
        "process": eq["process"],
        "last_pm_date": eq["last_pm"].isoformat(),
        "days_since_pm": days_since,
        "pm_cycle_days": eq["pm_cycle_days"],
        "overdue": overdue,
        "overdue_days": max(0, days_since - eq["pm_cycle_days"]),
    }


def check_pm_schedule(equipment_id: str) -> dict:
    """다음 7일 내 사용 가능한 PM 정비 윈도우 목록 반환"""
    eq = _EQUIPMENT.get(equipment_id)
    if not eq:
        return {"error": f"등록되지 않은 장비: {equipment_id}"}
    return {
        "equipment_id": equipment_id,
        "available_windows": eq["next_pm_windows"],
    }


SCHEMA_GET_PM = {
    "type": "function",
    "function": {
        "name": "get_pm_history",
        "description": (
            "장비의 마지막 PM(예방정비) 이력과 경과일, overdue 여부를 조회합니다. "
            "원인 분석에서 'PM 누락이 원인인가' 판단할 때 활용하세요. "
            "장비 ID는 알람별로 ASML-PH-01(A1), TEL-ET-03(A2), AMAT-CMP-02(A3) 가 매핑됩니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "equipment_id": {
                    "type": "string",
                    "description": "장비 ID (예: 'ASML-PH-01')",
                },
            },
            "required": ["equipment_id"],
        },
    },
}

SCHEMA_CHECK_PM = {
    "type": "function",
    "function": {
        "name": "check_pm_schedule",
        "description": (
            "다음 7일 내 PM 정비 가능 윈도우를 조회합니다. "
            "대응 권고에서 '언제 PM을 투입할 수 있는가'를 답할 때 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "equipment_id": {
                    "type": "string",
                    "description": "장비 ID",
                },
            },
            "required": ["equipment_id"],
        },
    },
}
