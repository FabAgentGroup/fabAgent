"""lookup_incident_history tool - 과거 incident 구조화 조회

knowledge/INC-*.md 의 RAG 검색과 별도로, 증상 키워드로 구조화 incident 레코드를 반환
(MES/incident DB 모방, 실 fab에선 Maximo/Splunk 등에서 조회)
"""

_INCIDENTS = [
    {
        "id": "INC-2024-0312",
        "date": "2024-03-12",
        "process": "Photo",
        "symptom": "CD-X 산포 증가",
        "root_cause": "렌즈 오염",
        "resolution": "긴급 PM 후 정상화 (2h 소요)",
        "yield_recovery": "3.1% → 0.4%",
        "keywords": ["cd", "산포", "렌즈", "오염", "photo", "노광"],
    },
    {
        "id": "INC-2024-0289",
        "date": "2024-02-28",
        "process": "Photo",
        "symptom": "스테이지 진동 이상치",
        "root_cause": "스테이지 베어링 마모",
        "resolution": "베어링 교체 후 alignment 재수행 (6h)",
        "yield_recovery": "1.8% → 0.2%",
        "keywords": ["스테이지", "진동", "베어링", "alignment", "photo"],
    },
    {
        "id": "INC-CMP-2025-0142",
        "date": "2025-08-14",
        "process": "CMP",
        "symptom": "MRR(재료 제거율) 산포 증가",
        "root_cause": "슬러리 유량 변동",
        "resolution": "슬러리 펌프 교체 + 유량 센서 재교정 (4h)",
        "yield_recovery": "2.4% → 0.3%",
        "keywords": ["mrr", "슬러리", "유량", "cmp", "재료", "제거율"],
    },
    {
        "id": "INC-ET-2024-0301",
        "date": "2024-03-01",
        "process": "Etch",
        "symptom": "트렌치 깊이 부족",
        "root_cause": "식각 가스 유량 저하",
        "resolution": "가스 라인 청소 + MFC 교정 (3h)",
        "yield_recovery": "2.0% → 0.5%",
        "keywords": ["트렌치", "깊이", "식각", "가스", "mfc", "etch"],
    },
    {
        "id": "INC-2023-0892",
        "date": "2023-11-22",
        "process": "Photo",
        "symptom": "Focus 편차 증가",
        "root_cause": "스테이지 평탄도 이상",
        "resolution": "스테이지 leveling 재수행 (2h)",
        "yield_recovery": "1.5% → 0.3%",
        "keywords": ["focus", "편차", "평탄도", "leveling", "photo"],
    },
]


def lookup_incident_history(symptom: str, max_results: int = 3) -> dict:
    """증상 키워드로 과거 incident DB 조회, 일치 키워드 수로 랭킹

    반환: {"incidents": [{"id", "date", "process", "symptom", "root_cause",
                          "resolution", "yield_recovery"}, ...]}
    """
    q = symptom.lower()
    q_tokens = [t for t in q.replace(",", " ").split() if len(t) >= 2]
    scored = []
    for inc in _INCIDENTS:
        score = sum(1 for kw in inc["keywords"] if any(kw in t or t in kw for t in q_tokens))
        if score > 0:
            scored.append((score, inc))
    scored.sort(key=lambda x: -x[0])
    matched = [
        {k: v for k, v in inc.items() if k != "keywords"}
        for _, inc in scored[:max_results]
    ]
    return {"incidents": matched}


SCHEMA = {
    "type": "function",
    "function": {
        "name": "lookup_incident_history",
        "description": (
            "과거 incident DB에서 증상 키워드와 일치하는 사례를 조회합니다. "
            "구조화된 레코드(원인, 해결책, 소요시간, yield 회복률)를 반환하므로 "
            "유사 사례 기반 의사결정에 활용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symptom": {
                    "type": "string",
                    "description": "증상 키워드 (예: 'CD 산포 증가', '슬러리 유량 이상')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "최대 반환 건수 (기본 3)",
                    "default": 3,
                },
            },
            "required": ["symptom"],
        },
    },
}
