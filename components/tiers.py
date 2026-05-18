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
        '<div class="tier-status"><span class="spinner"></span>분석 중…</div>'
        if loading
        else '<div class="tier-status"><span class="check">✓</span>방금</div>'
    )
    body_html = skeleton_html(tier_num) if loading else BODY_BUILDERS[tier_num](data)

    # st.html을 쓰면 markdown 파서를 거치지 않아 들여쓰기 4칸 짜리 라인이 코드블록으로 변하지 않음
    st.html(
        f'<section class="tier-card tier-{tier_num}">'
        f'<div class="tier-head">'
        f'<div class="tier-head-left">'
        f'<span class="chip chip-t{tier_num}">Tier {tier_num}</span>'
        f'<span class="tier-name">{TIER_NAMES[tier_num]}</span>'
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
    c1, c2, c3, _ = st.columns([1, 1, 2.2, 4])
    with c1:
        if st.button("✗ 거절", key="btn-reject", disabled=ss.approved):
            st.toast("권고 거절됨, 사유 수집 모달(MVP 범위 외)", icon="✗")
    with c2:
        if st.button("⏸ 보류", key="btn-hold", disabled=ss.approved):
            st.toast("권고 보류됨, 5분 후 재발생 예정", icon="⏸")
    with c3:
        label = "✓ 작업지시서 생성됨" if ss.approved else "✓ 승인 및 작업지시서 생성"
        if st.button(label, key="btn-approve", disabled=ss.approved, type="primary"):
            _on_approve()


def _on_approve():
    ss = st.session_state
    ss.approved = True

    # 자가 학습 - 현재 알람의 분석 결과를 knowledge로 자동 기록
    alarm = next((a for a in ss.alarms if a["id"] == ss.selected_alarm_id), None)
    work_order = f"W-{datetime.now():%Y%m%d}-{ss.selected_alarm_id[1:].zfill(3)}"
    if alarm:
        from agents.rag.learn import record_incident
        tier_data = get_tier_data(ss.selected_alarm_id)
        if tier_data:
            record_incident(alarm, tier_data, work_order)

    # 알람 상태 업데이트
    for a in ss.alarms:
        if a["id"] == ss.selected_alarm_id:
            a["status"] = "done"
            a["time"] = "방금 전"
            break

    st.toast(
        f"✓ 작업 지시서 {work_order} 생성 완료 · 인시던트 DB 자동 기록",
        icon="✅",
    )
    st.rerun()
