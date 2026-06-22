"""predict_tool_rul tool - 장비 소모품 잔여수명 + 예지보전 권고

반응형 PM(고장 후)이 아니라 예측형 PM을 가능케 한다. Tier 4 대응 권고에서
'언제 PM을 넣어야 하는가'를 RUL 기반으로 답할 때 사용
실 fab에선 FDC/EAP의 실시간 소모품 사용량으로 동작, 여기선 CMP 장비 데모 상태 사용
"""
from agents.rul import assess_equipment


def predict_tool_rul(equipment_id: str) -> dict:
    """장비 소모품별 RUL(lot)과 예지보전 권고 반환

    worst 소모품이 장비 PM 시점을 결정, status(healthy/watch/critical) + PM 윈도우 포함
    """
    a = assess_equipment(equipment_id)
    if a.get("status") == "unknown":
        return a
    driver = a["driver"]
    return {
        "equipment_id": equipment_id,
        "status": a["status"],
        "tool_rul_lots": a["tool_rul_lots"],
        "driver_consumable": driver["label"],
        "driver_rul_lots": driver["rul_lots"],
        "driver_health_index": driver["health_index"],
        "consumables": [
            {"label": c["label"], "rul_lots": c["rul_lots"],
             "health_index": c["health_index"], "mrr_now": c["mrr_now"]}
            for c in a["consumables"]
        ],
        "pm_recommendation": a["pm"],
    }


SCHEMA = {
    "type": "function",
    "function": {
        "name": "predict_tool_rul",
        "description": (
            "장비 소모품(패드·드레서·멤브레인)의 잔여수명(RUL, lot)과 예지보전 권고를 조회합니다. "
            "마모 추세를 외삽해 언제 한계에 도달할지 예측하므로, 반응형이 아닌 예측형 PM 시점 결정에 "
            "사용하세요. status(healthy/watch/critical)와 가장 먼저 한계 도달하는 소모품을 반환합니다. "
            "현재 CMP 장비(AMAT-CMP-02, AMAT-CMP-05)를 지원합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "equipment_id": {
                    "type": "string",
                    "description": "장비 ID (예: 'AMAT-CMP-02')",
                },
            },
            "required": ["equipment_id"],
        },
    },
}
