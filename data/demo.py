"""데모 데이터 - 알람 인박스 + 하드코딩 Tier 데이터

A1(Photo)은 M3에서 agents/ 실제 에이전트로 교체됨, A2·A3는 시연용 하드코딩
TIER_DATA에 없는 알람을 클릭하면 pipeline이 None을 반환하고
프론트가 "데이터 없음"을 안내함
"""
from core.schema import TierData

DEFAULT_ALARMS = [
    {
        "id": "A1",
        "status": "critical",
        "title": "Photo Step 이상",
        "lot_id": "L20240511-N-03",
        "feature": "CD-X 산포",
        "feature_arrow": "↑",
        "time": "3분 전",
    },
    {
        "id": "A2",
        "status": "warn",
        "title": "Etch Step 이상",
        "lot_id": "L20240511-N-02",
        "feature": "Trench Depth",
        "feature_arrow": "↓",
        "time": "15분 전",
    },
    {
        "id": "A3",
        "status": "warn",
        "title": "CMP Step 이상",
        "lot_id": "L20240510-N-08",
        "feature": "재료 제거율(MRR)",
        "feature_arrow": "↑",
        "time": "1시간 전",
    },
]

STATUS_LABELS = {"critical": "긴급", "warn": "주의", "done": "완료"}

# alarm_id -> TierData
# A1은 개발 가이드 11장 데이터, A2·A3은 M1에서 채움
TIER_DATA: dict[str, TierData] = {
    "A1": {
        "tier1": {
            "score": 0.87,
            "features": [
                {"name": "CD-X 산포", "value": 0.42},
                {"name": "노광 에너지", "value": 0.31},
                {"name": "Focus 편차", "value": 0.14},
            ],
            "lot": {"id": "L20240511-N-03", "wafers": 25},
        },
        "tier2": {
            "causes": [
                {
                    "name": "렌즈 오염",
                    "pct": 62,
                    "evidence": "직전 PM 후 14일 경과 · 유사 사례 4건 · 헤이즈 센서 +18%",
                    "citations": ["INC-2024-0312", "FMEA-PH-007"],
                },
                {
                    "name": "스테이지 진동",
                    "pct": 23,
                    "evidence": "동일 시간대 진동 센서 이상치 검출",
                    "citations": ["INC-2024-0289"],
                },
                {
                    "name": "웨이퍼 표면 결함",
                    "pct": 15,
                    "evidence": "직전 공정 입고 검사 패스",
                    "citations": [],
                },
            ],
        },
        "tier3": {
            "yield_loss": 2.3,
            "dependencies": [
                {"stage": "Photo", "delta": "+0.87", "tag": "현재", "kind": "current"},
                {"stage": "Etch", "delta": "+18%", "tag": "영향", "kind": "impacted"},
                {"stage": "CMP", "delta": "+5%", "tag": "경미", "kind": "minor"},
            ],
            "impact_lots": [
                {"label": "가공 중", "lots": 3, "wafers": 75},
                {"label": "대기 중", "lots": 5, "wafers": 125},
            ],
        },
        "tier4": {
            "immediate": [
                {"text": "렌즈 PM 긴급 투입", "meta": "예상 2시간"},
                {"text": "후공정 진입 보류 - 영향 lot 3건 (75장)", "meta": "Etch hold"},
                {"text": "양산 일정 재조정 - 영향 범위 격리", "meta": "PPC 협조"},
            ],
            "longterm": [
                {"text": "PM 주기 단축 권고: 30일 → 21일", "meta": None},
                {"text": "동일 패턴 발생 lot 추적 모니터링 강화", "meta": None},
            ],
            "refs": [
                {"id": "SOP-PH-LENS-002", "desc": "렌즈 PM 표준 절차"},
                {"id": "INC-2024-0312", "desc": "과거 유사 사례 (메모리 1동)"},
                {"id": "FMEA-PH-007", "desc": "Photo 공정 실패 모드 분석"},
            ],
        },
    },
    # TODO(M1) A2(Etch) 시연 데이터 추가
    # TODO(M1) A3(CMP) 시연 데이터 추가, 비워두면 "데이터 없음" 경로가 시연됨
}
