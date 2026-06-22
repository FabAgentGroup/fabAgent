"""합성 시나리오 - FDC 알람 스트림과 MES genealogy가 공유하는 단일 ground-truth

실 fab의 한 교대(shift) 동안 FDC가 쏟아내는 알람 흐름을 모사한다
핵심 의도: 수백 건의 알람 중 대부분은 nuisance(단발·경계선 이탈)이고,
소수의 진짜 excursion이 공통 원인(특정 챔버·슬러리 lot·PM 누락)으로 묶인다

이 파일은 평가용 정답을 한 곳에 모은다
- PLANTED_INCIDENTS: 진짜 excursion 3건 + 각자의 root-cause 엔티티(차원·값)
- 스트림(data/fdc)과 genealogy(data/mes)는 모두 이 시나리오를 읽어
  서로 일관된(같은 원인을 가리키는) 합성 데이터를 만든다

today = 2026-05-18 (data/tools/equipment.py TODAY와 정렬)
"""
from datetime import datetime

SEED = 42
SHIFT_START = datetime(2026, 5, 18, 0, 0, 0)  # 야간 교대 00:00 시작
SHIFT_HOURS = 8

# 라인 구성 - 동일 공정에 복수 장비/챔버 (chamber matching 대상)
TOOLS = {
    "Photo": ["ASML-PH-01", "ASML-PH-02"],
    "Etch": ["TEL-ET-03", "TEL-ET-04", "LAM-ET-07"],
    "CMP": ["AMAT-CMP-02", "AMAT-CMP-05"],
    "Diffusion": ["ASM-DIF-04"],
    "Implant": ["AMAT-IMP-06"],
}
CHAMBERS = ["A", "B", "C", "D"]
RECIPES = {
    "Photo": ["PH-LOGIC-7N", "PH-DRAM-1A"],
    "Etch": ["ET-STI-STD", "ET-GATE-HARD"],
    "CMP": ["CMP-STI-STD", "CMP-CU-LOW"],
    "Diffusion": ["DIF-WELL-STD"],
    "Implant": ["IMP-SD-STD"],
}
# 공정별 FDC 모니터링 파라미터 (센서) + 수율 가중치(0~1, 높을수록 수율 민감)
PARAMS = {
    "Photo": [("CD-X 산포", 0.9), ("Focus 편차", 0.7), ("노광 에너지", 0.5), ("Overlay", 0.6)],
    "Etch": [("Trench Depth", 0.85), ("식각 균일도", 0.7), ("가스 유량", 0.4), ("챔버 압력", 0.3)],
    "CMP": [("MRR", 0.9), ("제거 균일도", 0.75), ("슬러리 유량", 0.5), ("패드 압력", 0.4)],
    "Diffusion": [("막 두께", 0.7), ("온도 균일도", 0.5)],
    "Implant": [("도즈량", 0.8), ("빔 전류", 0.5)],
}

SLURRY_LOTS = ["SL-2261", "SL-2262", "SL-2263", "SL-BAD-2264"]
OPERATORS = ["OP-A", "OP-B", "OP-C", "OP-D"]

# ==================== 진짜 excursion (정답) ====================
# 각 incident:
#   id, process, tool, chamber, recipe, param: 알람이 집중되는 좌표
#   root_cause: 커몬낼리티 엔진이 맞춰야 할 정답 (dim, value)
#   n_alarms: 이 incident가 만드는 진짜 알람 수
#   sigma_range: 이탈 강도 (nuisance보다 큼)
#   window_min: 알람이 퍼지는 시간 폭(분) - 짧을수록 응집
#   start_min: 교대 시작 후 발생 시점(분)
PLANTED_INCIDENTS = [
    {
        "id": "INC-SYN-CMP-CHAMBER",
        "label": "CMP 챔버 드리프트",
        "process": "CMP",
        "tool": "AMAT-CMP-02",
        "chamber": "C",
        "recipe": "CMP-STI-STD",
        "param": "MRR",
        "root_cause": {"dim": "chamber", "value": "AMAT-CMP-02::C"},
        "n_alarms": 16,
        "sigma_range": (4.0, 7.5),
        "window_min": 90,
        "start_min": 70,
        "tools": ["AMAT-CMP-02"],
    },
    {
        "id": "INC-SYN-SLURRY-LOT",
        "label": "슬러리 lot 불량 (다장비 systemic)",
        "process": "CMP",
        "tool": None,  # 2개 장비에 걸침 -> tool이 아니라 slurry_lot이 공통
        "chamber": None,
        "recipe": "CMP-CU-LOW",
        "param": "제거 균일도",
        "root_cause": {"dim": "slurry_lot", "value": "SL-BAD-2264"},
        "n_alarms": 12,
        "sigma_range": (3.5, 6.0),
        "window_min": 130,
        "start_min": 150,
        "tools": ["AMAT-CMP-02", "AMAT-CMP-05"],
    },
    {
        "id": "INC-SYN-PHOTO-PM",
        "label": "Photo 스캐너 PM 누락 focus 드리프트",
        "process": "Photo",
        "tool": "ASML-PH-01",
        "chamber": "B",
        "recipe": "PH-LOGIC-7N",
        "param": "Focus 편차",
        "root_cause": {"dim": "tool", "value": "ASML-PH-01"},
        "n_alarms": 9,
        "sigma_range": (3.2, 5.5),
        "window_min": 75,
        "start_min": 240,
        "tools": ["ASML-PH-01"],
    },
]

N_NUISANCE = 360          # 단발성 노이즈 알람 수
NUISANCE_SIGMA = (3.0, 3.8)  # 경계선 이탈 (관리한계 살짝 초과)

# genealogy: 영향 웨이퍼가 root-cause 엔티티를 과대표현하는 정도
GENEALOGY_WAFERS = 600
AFFECTED_FAIL_BOOST = 0.55   # 원인 엔티티를 거친 웨이퍼의 추가 fail 확률
BASE_FAIL_RATE = 0.04        # 정상 베이스 fail 확률


def incident_by_id(incident_id: str) -> dict | None:
    for inc in PLANTED_INCIDENTS:
        if inc["id"] == incident_id:
            return inc
    return None
