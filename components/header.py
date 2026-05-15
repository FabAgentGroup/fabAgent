"""상단 헤더 (개발 가이드 부록 A)

로고 + 공정/라인 컨텍스트 + LIVE 시계 + 시스템 상태 + 사용자 영역
"""
from datetime import datetime

import streamlit as st


def render_header():
    now = datetime.now().strftime("%H:%M:%S")
    st.markdown(
        f"""
        <header class="fab-header">
          <div class="fab-logo">
            <div class="fab-logo-mark">
              <svg width="16" height="16" viewBox="0 0 160 160" fill="none">
                <circle cx="80" cy="80" r="60" stroke="#fff" stroke-width="10"/>
                <path d="M70 22 L90 22 L86 32 L74 32 Z" fill="#fff"/>
                <rect x="46" y="58" width="68" height="8" rx="4" fill="#fff"/>
                <rect x="46" y="76" width="52" height="8" rx="4" fill="#fff" opacity="0.7"/>
                <rect x="46" y="94" width="36" height="8" rx="4" fill="#fff" opacity="0.4"/>
              </svg>
            </div>
            FabAgent
          </div>
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
