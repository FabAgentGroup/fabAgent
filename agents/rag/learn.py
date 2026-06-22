"""자가 학습 루프 - 운영자 승인 시 분석 결과를 인시던트 DB에 자동 기록

승인된 분석을 INC-AUTO-{date}-{alarm_id}.md로 저장하면 RAG 검색 대상에 포함되어
향후 유사 알람의 원인 분석/대응 권고 정확도가 점진적으로 향상됨

PDF 기획서 "자가 학습 루프 - 운영자 승인 결과가 인시던트 DB에 즉시 반영" 대응 항목
"""
from datetime import datetime
from pathlib import Path

from agents.rag.store import KNOWLEDGE_DIR
from core.schema import TierData


def record_incident(alarm: dict, tier_data: TierData, work_order_id: str) -> Path:
    """승인된 분석을 인시던트 .md로 저장, 저장된 경로 반환"""
    date = datetime.now().strftime("%Y-%m-%d")
    doc_id = f"INC-AUTO-{date}-{alarm['id']}"
    path = KNOWLEDGE_DIR / f"{doc_id}.md"
    path.write_text(_render_doc(doc_id, alarm, tier_data, work_order_id), encoding="utf-8")
    return path


_DECISION_LABEL = {"approved": "승인", "held": "보류", "rejected": "거절"}


def record_incident_brief(
    incident: dict, commonality: dict, disposition: dict, decision: str, work_order_id: str
) -> Path:
    """트리아지 incident 결정(LLM 4-Tier 없이)을 인시던트 .md로 저장

    커몬낼리티 정량 용의자 + 디스포지션 결정을 결정론으로 기록해 RAG 학습 대상에 포함
    """
    date = datetime.now().strftime("%Y-%m-%d")
    doc_id = f"INC-AUTO-{date}-{incident['incident_id']}"
    path = KNOWLEDGE_DIR / f"{doc_id}.md"
    path.write_text(
        _render_brief(doc_id, incident, commonality, disposition, decision, work_order_id),
        encoding="utf-8",
    )
    return path


def _render_brief(
    doc_id: str, inc: dict, comm: dict, disp: dict, decision: str, work_order: str
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    suspects_md = "\n".join(
        f"{i+1}. {s['dim_label']} {s['value']} - 불량률 {s['entity_fail_rate']:.0%} "
        f"vs 전체 {s['baseline_fail_rate']:.0%} (lift {s['lift']}x, p={s['p_value']:.1e})"
        for i, s in enumerate(comm.get("suspects", []))
    ) or "(정량 용의자 없음)"
    opts_md = "\n".join(
        f"- {o['label']}: 기대비용 ${o['expected_cost_usd']:,}"
        for o in disp.get("options", [])
    )
    return f"""# {doc_id} - {inc['title']} 트리아지 결정 기록

## 분류
- 유형: 트리아지 incident 결정 (운영자 {_DECISION_LABEL.get(decision, decision)})
- 공정: {inc['process']}
- 장비: {inc['dominant_tool']}
- recipe: {inc['dominant_recipe']}
- 기록 시각: {now}
- 작업지시서: {work_order}

## 증상
{inc['process']} {inc['param']} 이상 - 알람 {inc['n_alarms']}건, max σ {inc['max_sigma']}

## 정량 용의자 (커몬낼리티)
{suspects_md}

## 디스포지션
- 추천: {disp.get('recommended_label', '-')} (신뢰도 {disp.get('confidence', 0):.0%})
{opts_md}

## 운영자 결정
- 결정: {_DECISION_LABEL.get(decision, decision)}
"""


def _render_doc(doc_id: str, alarm: dict, td: TierData, work_order: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    t1, t2, t3, t4 = td["tier1"], td["tier2"], td["tier3"], td["tier4"]

    causes_md = "\n".join(
        f"{i+1}. {c['name']} ({c['pct']}%) - {c['evidence']}"
        for i, c in enumerate(t2["causes"])
    )
    deps_md = ", ".join(
        f"{d['stage']}({d['delta']}, {d['tag']})" for d in t3["dependencies"]
    )
    impact_md = ", ".join(
        f"{l['label']} {l['lots']} lot/{l['wafers']}장" for l in t3["impact_lots"]
    )

    def actions(items):
        return "\n".join(
            f"- {a['text']}" + (f" ({a['meta']})" if a.get("meta") else "")
            for a in items
        )

    return f"""# {doc_id} - {alarm['title']} 자동 기록

## 분류
- 유형: 자동 학습 인시던트 (운영자 승인 기반)
- 공정: {alarm['title']}
- lot: {alarm['lot_id']}
- 발생 알림: {alarm['time']}
- 기록 시각: {now}
- 작업지시서: {work_order}

## Tier 1 이상 탐지
- 이상 점수: {t1['score']}
- 기여 센서 Top: {', '.join(f['name'] for f in t1['features'])}
- 영향 lot: {t1['lot']['id']} ({t1['lot']['wafers']}장)

## Tier 2 추정 원인
{causes_md}

## Tier 3 영향 평가
- 예상 수율 손실: {t3['yield_loss']} %p
- 공정 의존성: {deps_md}
- 영향 WIP: {impact_md}

## Tier 4 채택 권고

### 즉시 조치
{actions(t4['immediate'])}

### 중장기 조치
{actions(t4['longterm'])}

## 운영자 결정
- 권고 채택: 전체 승인
- 작업지시서 발행: {work_order}
"""
