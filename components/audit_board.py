"""감사 로그 보드 (도입 전제조건)

운영자 의사결정의 영속 추적을 보여준다. 품질시스템은 '누가 언제 무슨 근거로
결정했는가'의 추적성을 요구하며, 신뢰도는 캘리브레이션되어 표시된다

데이터는 core/audit.py의 SQLite 감사 로그에서 읽는다
"""
import streamlit as st

from core.audit import recent, record_decision, stats

_STYLE = """
<style>
.au-stats { display: flex; gap: 16px; margin: 8px 0 18px; flex-wrap: wrap; }
.au-stat { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 13px 18px; min-width: 120px; }
.au-stat-val { font-size: 24px; font-weight: 800; font-family: var(--mono); color: var(--text-primary); }
.au-stat-val.ok { color: var(--t3-text); }
.au-stat-label { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.au-row { display: flex; align-items: center; gap: 12px; padding: 11px 14px; border: 1px solid var(--border); border-left-width: 4px; border-radius: 9px; margin-bottom: 8px; background: var(--bg-card); }
.au-row.d-approved { border-left-color: var(--t3-text); }
.au-row.d-held { border-left-color: var(--warn); }
.au-row.d-rejected { border-left-color: var(--crit-text); }
.au-ts { font-family: var(--mono); font-size: 12px; color: var(--text-tertiary); min-width: 142px; }
.au-dec { font-size: 12px; font-weight: 800; padding: 2px 9px; border-radius: 7px; min-width: 52px; text-align: center; }
.au-dec.d-approved { background: var(--t3-bg); color: var(--t3-text); }
.au-dec.d-held { background: var(--t4-bg); color: var(--t4-text); }
.au-dec.d-rejected { background: var(--crit-bg); color: var(--crit-text); }
.au-target { font-weight: 700; color: var(--text-primary); min-width: 150px; }
.au-target small { font-family: var(--mono); color: var(--text-tertiary); font-weight: 400; }
.au-conf { font-family: var(--mono); font-size: 12px; color: var(--text-secondary); }
.au-reason { font-size: 12px; color: var(--text-secondary); margin-left: auto; max-width: 320px; text-align: right; }
.au-empty { color: var(--text-secondary); font-size: 13px; padding: 14px; background: var(--bg-subtle); border-radius: 10px; }
</style>
"""

_DECISION_LABEL = {"approved": "승인", "held": "보류", "rejected": "거절"}


def _seed_demo_if_empty():
    """데모 편의 - 감사 로그가 비어 있으면 직전 교대 결정 예시를 1회 기록"""
    if stats()["total"] > 0:
        return
    samples = [
        ("approved", "A3", "CMP Step 이상", 0.59, "MRR 회복 확인, 컨디셔너 교체 승인", "2026-06-22 02:14:33"),
        ("held", "A2", "Etch Step 이상", 0.41, "원인 신뢰도 낮음, 추가 SPC 데이터 대기", "2026-06-22 03:40:07"),
        ("approved", "A1", "Photo Step 이상", 0.62, "렌즈 PM 긴급 투입 승인", "2026-06-22 05:09:51"),
    ]
    for dec, tid, title, conf, reason, ts in samples:
        record_decision(dec, target_id=tid, target_title=title, surface="analysis",
                        operator="박○○", confidence=conf, reason=reason, ts=ts)


def render_audit_board():
    _seed_demo_if_empty()
    s = stats()
    rows = recent(30)

    st.html(_STYLE)
    st.markdown(
        '<h1 class="fab-main-title">감사 로그</h1>'
        '<div class="fab-main-sub"><span>운영자 의사결정 영속 추적</span>'
        '<span class="sep">·</span><span>품질시스템 추적성 · 보정된 신뢰도</span></div>',
        unsafe_allow_html=True,
    )

    st.html(
        '<div class="au-stats">'
        f'<div class="au-stat"><div class="au-stat-val">{s["total"]}</div>'
        f'<div class="au-stat-label">총 결정</div></div>'
        f'<div class="au-stat"><div class="au-stat-val ok">{s["approval_rate"]:.0%}</div>'
        f'<div class="au-stat-label">승인율</div></div>'
        f'<div class="au-stat"><div class="au-stat-val">{s["approved"]}</div>'
        f'<div class="au-stat-label">승인</div></div>'
        f'<div class="au-stat"><div class="au-stat-val">{s["held"]}</div>'
        f'<div class="au-stat-label">보류</div></div>'
        f'<div class="au-stat"><div class="au-stat-val">{s["rejected"]}</div>'
        f'<div class="au-stat-label">거절</div></div>'
        '</div>'
    )

    if not rows:
        st.html('<div class="au-empty">아직 기록된 결정이 없습니다. 심층 분석에서 운영자 결정을 내리면 여기에 추적됩니다.</div>')
        return

    for r in rows:
        d = r["decision"]
        conf = f'신뢰도 {r["confidence"]:.0%}' if r["confidence"] is not None else "신뢰도 -"
        reason = r["reason"] or ""
        st.html(
            f'<div class="au-row d-{d}">'
            f'<span class="au-ts">{r["ts"]}</span>'
            f'<span class="au-dec d-{d}">{_DECISION_LABEL.get(d, d)}</span>'
            f'<span class="au-target">{r["target_title"]} <small>{r["target_id"]}</small></span>'
            f'<span class="au-conf">{conf}</span>'
            f'<span class="au-reason">{reason}</span>'
            f'</div>'
        )
