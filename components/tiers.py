"""Tier 1~4 순차 등장 렌더러 (개발 가이드 8·9·10장)

st.empty() placeholder 4개 + time.sleep으로 스켈레톤 → 콘텐츠 순차 교체
이미 완료된 상태(stage>=5)거나 animation_pending이 아닐 때는 즉시 정적 렌더

★ Tier 데이터는 반드시 core.pipeline.get_tier_data() 한 함수로만 받음
data.demo.TIER_DATA를 직접 import 하지 말 것 (실제 에이전트 교체가 막힘)
"""
import time
from datetime import datetime

import streamlit as st

from components.skeleton import skeleton_html
from components.tiers_body import (
    tier_1_body_html,
    tier_2_body_html,
    tier_3_body_html,
    tier_4_body_html,
)
from core.pipeline import get_tier_data

SPEED_PRESETS = {
    "fast":   {"skel": 0.6, "hold": 0.4},
    "normal": {"skel": 1.4, "hold": 0.7},
    "real":   {"skel": 3.0, "hold": 1.5},
}

TIER_NAMES = {1: "이상 탐지", 2: "원인 분석", 3: "공정 간 영향 평가", 4: "대응 권고"}

# 각 Tier의 에이전트 페르소나 + 활동 요약 (loading=False일 때만 활성)
AGENT_PERSONA = {
    1: {"name": "Detection Agent", "tool": "IsolationForest · SECOM/PHM"},
    2: {"name": "Cause Agent", "tool": "GPT-5-mini · RAG 검색"},
    3: {"name": "Impact Agent", "tool": "GPT-5-mini · RAG + WIP 결합"},
    4: {"name": "Response Agent", "tool": "GPT-5-mini · RAG + 근거 추출"},
}


def _agent_summary(tier_num: int, data) -> str:
    """Tier별 에이전트 활동 1줄 요약, data가 None이면 분석 중 메시지"""
    if data is None:
        return "분석 중..."
    if tier_num == 1:
        return f"{len(data['features'])}개 기여 센서 검출 (이상 점수 {data['score']})"
    if tier_num == 2:
        cites = sum(len(c["citations"]) for c in data["causes"])
        return f"사내 문서 {cites}건 인용해 원인 {len(data['causes'])}개 추정"
    if tier_num == 3:
        return f"의존성 + WIP 결합해 예상 수율 손실 {data['yield_loss']} %p 추정"
    if tier_num == 4:
        return f"근거 {len(data['refs'])}건 인용해 즉시 {len(data['immediate'])}건 · 중장기 {len(data['longterm'])}건 권고"
    return ""


BODY_BUILDERS = {
    1: tier_1_body_html,
    2: tier_2_body_html,
    3: tier_3_body_html,
    4: tier_4_body_html,
}


LOADING_HTML = """
<div class="fab-loading">
  <div class="fab-loading-spinner"></div>
  <h3 class="fab-loading-title">4-Tier 멀티 에이전트 분석 진행 중</h3>
  <div class="fab-loading-subtitle">알람을 분석하기 위해 4단계 에이전트가 순차 실행됩니다</div>
  <div class="fab-loading-pipeline">
    <span class="step t1">Tier 1 이상 탐지</span>
    <span class="arrow">→</span>
    <span class="step t2">Tier 2 원인 분석</span>
    <span class="arrow">→</span>
    <span class="step t3">Tier 3 영향 평가</span>
    <span class="arrow">→</span>
    <span class="step t4">Tier 4 대응 권고</span>
  </div>
  <div class="fab-loading-hint">첫 호출은 LLM 3회 직렬로 약 60초 소요됩니다 · 이후 동일 알람은 캐시로 즉시 응답</div>
</div>
"""


def render_tier_cascade():
    ss = st.session_state
    # 첫 호출 시 LLM 3회 직렬로 약 60초, 사용자 안내를 위해 로딩 카드 먼저 렌더
    loading_slot = st.empty()
    loading_slot.html(LOADING_HTML)
    try:
        data = get_tier_data(ss.selected_alarm_id)
    finally:
        loading_slot.empty()

    if data is None:
        st.markdown(
            """
            <div class="fab-empty">
              <div class="fab-empty-inner">
                <div class="fab-empty-icon" style="font-size: 24px;">∅</div>
                <h3>분석 데이터가 없습니다</h3>
                <p>선택한 알람에 매핑된 분석 결과가 없습니다</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if ss.animation_pending:
        ss.animation_pending = False
        _run_sequence(data)
        return

    # 정적 렌더 (재실행/새로고침 대응)
    for t in range(1, 5):
        render_tier(t, data[f"tier{t}"], loading=False, with_actions=(t == 4))


def _run_sequence(data):
    ss = st.session_state
    timing = SPEED_PRESETS[ss.speed]
    slots = [st.empty() for _ in range(4)]

    for tier_idx in range(1, 5):
        ss.stage = tier_idx
        with slots[tier_idx - 1].container():
            render_tier(tier_idx, None, loading=True)
        time.sleep(timing["skel"])
        with slots[tier_idx - 1].container():
            render_tier(
                tier_idx,
                data[f"tier{tier_idx}"],
                loading=False,
                with_actions=(tier_idx == 4),
            )
        ss.completed_tiers.add(tier_idx)
        if tier_idx < 4:
            time.sleep(timing["hold"])

    ss.stage = 5


def render_tier(tier_num: int, data, loading: bool, with_actions: bool = False):
    """Tier 카드 한 덩어리를 단일 markdown으로 렌더, Tier 4 액션 바만 별도 위젯"""
    status_html = (
        '<div class="tier-status"><span class="spinner"></span>실행 중...</div>'
        if loading
        else '<div class="tier-status"><span class="check">✓</span>완료</div>'
    )
    body_html = skeleton_html(tier_num) if loading else BODY_BUILDERS[tier_num](data)
    p = AGENT_PERSONA[tier_num]
    summary = _agent_summary(tier_num, None if loading else data)

    st.html(
        f'<section class="tier-card tier-{tier_num}">'
        f'<div class="tier-head">'
        f'<div class="tier-head-left">'
        f'<div class="agent-id">'
        f'<div class="agent-name-row">'
        f'<span class="agent-name">{p["name"]}</span>'
        f'<span class="chip chip-t{tier_num}">Tier {tier_num} · {TIER_NAMES[tier_num]}</span>'
        f'</div>'
        f'<div class="agent-summary">{summary} · <span class="agent-tool">{p["tool"]}</span></div>'
        f'</div>'
        f'</div>'
        f'{status_html}'
        f'</div>'
        f'<div class="tier-body">{body_html}</div>'
        f'</section>'
    )

    if tier_num == 4 and with_actions and not loading:
        _render_action_bar()


def _render_action_bar():
    ss = st.session_state

    st.markdown(
        '<div class="action-bar-head">'
        '<span class="label">운영자 결정</span>'
        '<span>권고서를 검토하고 액션을 선택하세요</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # 결정 사유 (보류·거절 시 감사 로그에 기록)
    ss.setdefault("decision_reason", "")
    ss.decision_reason = st.text_input(
        "결정 사유 (선택, 감사 로그 기록)",
        value=ss.decision_reason,
        key="decision-reason-input",
        disabled=ss.approved,
        placeholder="보류·거절 사유나 승인 코멘트를 남기면 감사 추적에 기록됩니다",
    )

    # 양쪽 spacer로 가운데 정렬
    _, c1, c2, c3, _ = st.columns([2.5, 1, 1, 2.2, 2.5])
    with c1:
        if st.button("거절", key="btn-reject", disabled=ss.approved, use_container_width=True):
            _on_reject()
    with c2:
        if st.button("보류", key="btn-hold", disabled=ss.approved, use_container_width=True):
            _on_hold()
    with c3:
        label = "작업지시서 생성됨" if ss.approved else "승인 및 작업지시서 생성"
        if st.button(label, key="btn-approve", disabled=ss.approved, type="primary", use_container_width=True):
            _on_approve()

    _render_action_result()


def _render_action_result():
    ss = st.session_state
    act = ss.get("last_action")
    if not act:
        return
    kind = act["type"]
    icon = {"approved": "✓", "held": "⏸", "rejected": "✗"}[kind]
    title = act["title"]
    meta = act["meta"]
    st.html(
        f'<div class="action-result {kind}">'
        f'<div class="action-result-icon">{icon}</div>'
        f'<div class="action-result-body">'
        f'<div class="action-result-title">{title}</div>'
        f'<div class="action-result-meta">{meta}</div>'
        f'</div>'
        f'</div>'
    )


OPERATOR = "박○○"


def _decision_confidence(tier_data: dict | None) -> float | None:
    """기록용 신뢰도 - Tier4 디스포지션 신뢰도 우선, 없으면 Tier2 최상위 원인 기여도"""
    if not tier_data:
        return None
    disp = tier_data.get("tier4", {}).get("disposition")
    if disp and disp.get("confidence") is not None:
        return float(disp["confidence"])
    causes = tier_data.get("tier2", {}).get("causes", [])
    return max((c.get("pct", 0) for c in causes), default=0) / 100.0


def _audit_decision(decision: str):
    """운영자 결정을 감사 로그에 영속 기록 (알람·incident 공통)"""
    from core.audit import record_decision, surface_for

    ss = st.session_state
    alarm = next((a for a in ss.alarms if a["id"] == ss.selected_alarm_id), None)
    tier_data = get_tier_data(ss.selected_alarm_id)
    record_decision(
        decision=decision,
        target_id=ss.selected_alarm_id,
        target_title=alarm["title"] if alarm else "",
        surface=surface_for(ss.selected_alarm_id),
        operator=OPERATOR,
        confidence=_decision_confidence(tier_data),
        reason=ss.get("decision_reason", ""),
    )


def _on_reject():
    _audit_decision("rejected")
    st.session_state.last_action = {
        "type": "rejected",
        "title": "권고 거절",
        "meta": "거절 사유가 감사 로그에 기록되었습니다, 후속 분석·자가학습에 반영됩니다",
    }
    st.toast("권고 거절됨", icon="❌")
    st.rerun()


def _on_hold():
    _audit_decision("held")
    st.session_state.last_action = {
        "type": "held",
        "title": "권고 보류",
        "meta": "보류 사유가 감사 로그에 기록되었습니다, 추가 데이터 확보 후 재검토 권장",
    }
    st.toast("권고 보류됨", icon="⏸️")
    st.rerun()


def _on_approve():
    ss = st.session_state
    ss.approved = True

    # 자가 학습 - 현재 알람의 분석 결과를 knowledge로 자동 기록
    from core.audit import make_work_order

    alarm = next((a for a in ss.alarms if a["id"] == ss.selected_alarm_id), None)
    work_order = make_work_order(ss.selected_alarm_id)
    incident_doc = ""
    if alarm:
        from agents.rag.learn import record_incident
        tier_data = get_tier_data(ss.selected_alarm_id)
        if tier_data:
            path = record_incident(alarm, tier_data, work_order)
            incident_doc = path.name

    # 감사 로그 영속 기록 (승인)
    _audit_decision("approved")

    # 알람 상태 업데이트
    for a in ss.alarms:
        if a["id"] == ss.selected_alarm_id:
            a["status"] = "done"
            a["time"] = "방금 전"
            break

    ss.last_action = {
        "type": "approved",
        "title": "승인 완료, 작업지시서 발행",
        "meta": (
            f"작업지시서 <code>{work_order}</code> 생성 · "
            f"인시던트 DB <code>{incident_doc}</code> 자동 기록 · "
            "사이드바 알람 상태가 [완료]로 전환되었습니다"
        ),
    }
    st.toast(
        f"✓ 작업 지시서 {work_order} 생성 · 인시던트 DB 자동 기록",
        icon="✅",
    )
    st.rerun()
