"""상단 헤더 (개발 가이드 부록 A)

로고 + 공정/라인 컨텍스트 + LIVE 시계 + 시스템 상태 + 사용자 영역
"""
from datetime import datetime

import streamlit as st


def render_header():
    now = datetime.now().strftime("%H:%M:%S")
    # 로고는 사이드바 최상단으로 옮김 (components/alarm_inbox.py)
    st.markdown(
        f"""
        <header class="fab-header">
          <div class="fab-context">
            <span class="ctx-label">공정</span><span>Photo · Lithography</span>
            <span class="ctx-sep"></span>
            <span class="ctx-label">라인</span>
            <span style="font-family: var(--mono); font-weight: 600;">L20240511-N-03</span>
          </div>
          <span class="live-tick">
            <span class="dot"></span> LIVE · {now}
          </span>
          <div class="fab-header-spacer"></div>
          <div class="fab-status">
            <span class="fab-status-dot"></span> 시스템 정상
          </div>
          <div class="fab-user">
            <span>박○○ 운영자 · 야간 교대</span>
            <span class="avatar">박</span>
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )
