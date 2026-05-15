"""4단계 진행 스트립 (개발 가이드 부록 C)

st.session_state.stage 기준으로 각 단계를 idle / active / done으로 렌더
- stage > num: done (✓)
- stage == num: active (현재 분석 중)
- stage < num: idle
"""
import streamlit as st


STEPS = [(1, "이상 탐지"), (2, "원인 분석"), (3, "영향 평가"), (4, "권고서")]


def render_progress_strip():
    stage = st.session_state.stage

    pieces = []
    for i, (num, label) in enumerate(STEPS):
        if stage > num:
            state, mark = "done", "✓"
        elif stage == num:
            state, mark = "active", str(num)
        else:
            state, mark = "idle", str(num)
        pieces.append(
            f'<div class="fab-progress-step {state}"><span class="num">{mark}</span>{label}</div>'
        )
        if i < len(STEPS) - 1:
            pieces.append('<span class="conn"></span>')

    st.markdown(
        f'<div class="fab-progress">{"".join(pieces)}</div>',
        unsafe_allow_html=True,
    )
