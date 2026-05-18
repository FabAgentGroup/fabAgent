"""공정 관련 tools - downstream 의존성 + WIP + yield baseline

실 fab에선 MES + Yield Management System에서 조회되는 값
"""
from data.wip import get_affected_wip

# 공정 흐름 (대표 라인: Photo -> Etch -> CMP -> Diffusion -> Implant -> Metal -> Test)
# 각 entry는 (downstream_stage, typical_delta_pct, severity)
_DOWNSTREAM = {
    "Photo": [
        ("Etch", 18, "impacted"),
        ("CMP", 5, "minor"),
    ],
    "Etch": [
        ("CMP", 15, "impacted"),
        ("Diffusion", 3, "minor"),
    ],
    "CMP": [
        ("Diffusion", 8, "impacted"),
        ("Implant", 12, "impacted"),
        ("Test", 6, "minor"),
    ],
    "Diffusion": [
        ("Implant", 10, "impacted"),
        ("Metal", 4, "minor"),
    ],
    "Implant": [
        ("Metal", 7, "impacted"),
        ("Test", 5, "minor"),
    ],
}

# 공정별 yield 기준선 (최근 30일 평균, %)
_YIELD_BASELINE = {
    "Photo": 96.4,
    "Etch": 95.8,
    "CMP": 96.1,
    "Diffusion": 97.2,
    "Implant": 96.7,
}


def get_downstream_steps(current_stage: str) -> dict:
    """현재 공정 이후로 영향 받는 후공정 목록 반환

    각 후공정에 대해 typical delta(%, 영향 강도)와 severity(impacted/minor) 제공
    """
    deps = _DOWNSTREAM.get(current_stage, [])
    return {
        "current_stage": current_stage,
        "downstream": [
            {"stage": s, "typical_delta_pct": d, "severity": sev}
            for s, d, sev in deps
        ],
    }


def query_wip_status(alarm_id: str) -> dict:
    """알람으로 영향 받는 WIP(가공중·대기중) lot 수 + wafer 수 조회"""
    lots = get_affected_wip(alarm_id)
    return {"alarm_id": alarm_id, "wip": lots}


def get_yield_baseline(process: str) -> dict:
    """공정의 최근 30일 yield 기준선(%) 반환

    이상 발생 시 baseline 대비 yield_loss 계산에 사용
    """
    baseline = _YIELD_BASELINE.get(process)
    if baseline is None:
        return {"error": f"등록되지 않은 공정: {process}"}
    return {"process": process, "baseline_yield_pct": baseline, "window": "최근 30일"}


SCHEMA_DOWNSTREAM = {
    "type": "function",
    "function": {
        "name": "get_downstream_steps",
        "description": (
            "현재 공정 이후 영향 받는 후공정 목록을 반환합니다. "
            "각 후공정의 일반적 영향 강도(typical_delta_pct)와 severity(impacted/minor)를 포함. "
            "Tier 3 영향 평가에서 downstream_dependencies 산출에 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "current_stage": {
                    "type": "string",
                    "description": "현재 공정 (Photo, Etch, CMP, Diffusion, Implant 중)",
                },
            },
            "required": ["current_stage"],
        },
    },
}

SCHEMA_WIP = {
    "type": "function",
    "function": {
        "name": "query_wip_status",
        "description": (
            "알람으로 영향 받는 WIP(가공중·대기중) lot/wafer 수를 MES에서 조회합니다. "
            "Tier 3 impact_lots 필드를 채울 때 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "alarm_id": {
                    "type": "string",
                    "description": "알람 ID (A1, A2, A3)",
                },
            },
            "required": ["alarm_id"],
        },
    },
}

SCHEMA_YIELD = {
    "type": "function",
    "function": {
        "name": "get_yield_baseline",
        "description": (
            "공정의 최근 30일 yield 기준선(%)을 조회합니다. "
            "yield_loss를 baseline 대비로 정량화할 때 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "process": {
                    "type": "string",
                    "description": "공정 이름 (Photo, Etch, CMP, Diffusion, Implant)",
                },
            },
            "required": ["process"],
        },
    },
}
