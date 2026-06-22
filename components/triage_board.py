"""Tier 0 트리아지 보드 (운영자 진입 화면)

FDC 알람 폭주를 랭킹된 incident로 압축해 보여주는 새 진입 surface
운영자는 수백 알람 대신 상위 incident만 보고, 카드를 클릭하면 그 incident의
정량 용의자(MES genealogy 커몬낼리티)를 확인

데이터는 결정론 파이프라인(triage + commonality)이라 LLM 호출 없이 즉시 렌더
"""
import streamlit as st

from agents.commonality import commonality_for_incident
from agents.disposition import disposition_for_incident
from agents.triage import triage
from data.fdc.stream import load_alarm_stream

_STYLE = """
<style>
.t0-wrap { margin-top: 4px; }
.t0-headline {
  display: flex; gap: 18px; align-items: stretch; margin-bottom: 18px; flex-wrap: wrap;
}
.t0-stat {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
  padding: 14px 18px; min-width: 150px;
}
.t0-stat-val { font-size: 26px; font-weight: 800; color: var(--text-primary); font-family: var(--mono); }
.t0-stat-val.accent { color: var(--t1-text); }
.t0-stat-label { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.t0-arrow { display: flex; align-items: center; font-size: 22px; color: var(--text-tertiary); }

.t0-card-link { text-decoration: none; display: block; margin-bottom: 10px; }
.t0-card {
  background: var(--bg-card); border: 1px solid var(--border); border-left-width: 4px;
  border-radius: 10px; padding: 12px 16px; transition: box-shadow .15s, transform .15s;
}
.t0-card:hover { box-shadow: 0 3px 12px rgba(31,42,58,.10); transform: translateY(-1px); }
.t0-card.sel { border-color: var(--t1-border); box-shadow: 0 0 0 2px var(--t1-bg); }
.t0-card.risk-crit { border-left-color: var(--crit-text); }
.t0-card.risk-warn { border-left-color: var(--warn); }
.t0-card.risk-low  { border-left-color: var(--t1-text); }
.t0-card-top { display: flex; align-items: center; gap: 10px; }
.t0-rank {
  font-family: var(--mono); font-weight: 800; font-size: 13px; color: var(--text-tertiary);
  min-width: 26px;
}
.t0-title { font-weight: 700; color: var(--text-primary); font-size: 15px; flex: 1; }
.t0-risk-chip {
  font-family: var(--mono); font-weight: 800; font-size: 13px; padding: 2px 9px;
  border-radius: 7px;
}
.t0-risk-chip.risk-crit { background: var(--crit-bg); color: var(--crit-text); }
.t0-risk-chip.risk-warn { background: var(--t4-bg); color: var(--t4-text); }
.t0-risk-chip.risk-low  { background: var(--t1-bg); color: var(--t1-text); }
.t0-meta { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 7px; font-size: 12px; color: var(--text-secondary); }
.t0-meta .mono { font-family: var(--mono); }
.t0-kind {
  font-size: 11px; padding: 1px 7px; border-radius: 6px; background: var(--bg-subtle);
  color: var(--text-secondary); border: 1px solid var(--border);
}

.t0-suspects {
  background: var(--t2-bg-soft); border: 1px solid var(--t2-border); border-radius: 12px;
  padding: 16px 20px; margin-top: 14px;
}
.t0-suspects-head { font-weight: 800; color: var(--t2-text); font-size: 15px; margin-bottom: 4px; }
.t0-suspects-sub { font-size: 12px; color: var(--text-secondary); margin-bottom: 14px; }
.t0-suspect { margin-bottom: 13px; }
.t0-suspect-top { display: flex; align-items: baseline; gap: 8px; }
.t0-suspect-dim {
  font-size: 11px; padding: 1px 7px; border-radius: 6px; background: var(--t2-bg);
  color: var(--t2-text); font-weight: 700;
}
.t0-suspect-val { font-family: var(--mono); font-weight: 700; color: var(--text-primary); font-size: 14px; }
.t0-suspect-lift { margin-left: auto; font-family: var(--mono); font-weight: 800; color: var(--t2-text); }
.t0-bar-track { height: 7px; background: var(--bg-subtle); border-radius: 4px; margin-top: 6px; overflow: hidden; }
.t0-bar-fill { height: 100%; background: var(--t2-text); border-radius: 4px; }
.t0-suspect-meta { font-size: 11px; color: var(--text-secondary); margin-top: 4px; font-family: var(--mono); }
.t0-top-flag { color: var(--crit-text); font-weight: 800; }

.t0-disp {
  background: var(--t4-bg-soft); border: 1px solid var(--t4-border); border-radius: 12px;
  padding: 16px 20px; margin-top: 14px;
}
.t0-disp-head { font-weight: 800; color: var(--t4-text); font-size: 15px; margin-bottom: 4px; }
.t0-disp-rec {
  display: flex; align-items: baseline; gap: 10px; margin: 10px 0 4px;
}
.t0-disp-rec-label { font-size: 18px; font-weight: 800; color: var(--text-primary); }
.t0-disp-rec-tag { font-size: 11px; padding: 2px 8px; border-radius: 6px; background: var(--t4-bg); color: var(--t4-text); font-weight: 700; }
.t0-disp-rationale { font-size: 12px; color: var(--text-secondary); margin-bottom: 12px; }
.t0-disp-opt { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-top: 1px dashed var(--border); }
.t0-disp-opt.rec .t0-disp-opt-name { color: var(--t4-text); font-weight: 800; }
.t0-disp-opt-name { min-width: 150px; font-size: 13px; color: var(--text-primary); }
.t0-disp-opt-cost { font-family: var(--mono); font-weight: 800; font-size: 14px; min-width: 110px; text-align: right; }
.t0-disp-opt-range { font-family: var(--mono); font-size: 11px; color: var(--text-tertiary); }
.t0-disp-foot { font-size: 11px; color: var(--text-secondary); margin-top: 10px; font-family: var(--mono); }
</style>
"""


def _usd(v) -> str:
    return f"${v:,.0f}"


def incident_display_alarm(incident_id: str) -> dict | None:
    """incident ID로 심층 분석 진입용 표시 alarm dict 구성 (사이드바·헤더용)"""
    res = _run_triage()
    inc = next((i for i in res["incidents"] if i["incident_id"] == incident_id), None)
    if not inc:
        return None
    return {
        "id": inc["incident_id"],
        "status": "critical" if inc["risk_score"] >= 80 else "warn",
        "title": f"{inc['process']} {inc['param']} 이상",
        "lot_id": inc["dominant_tool"],
        "feature": inc["param"],
        "feature_arrow": "",
        "time": "방금 전",
    }


@st.cache_data(show_spinner=False)
def _run_triage() -> dict:
    return triage(load_alarm_stream())


@st.cache_data(show_spinner=False)
def _commonality(incident_id: str, incidents: tuple) -> dict:
    inc = next((i for i in incidents if i["incident_id"] == incident_id), None)
    return commonality_for_incident(dict(inc)) if inc else {"suspects": []}


@st.cache_data(show_spinner=False)
def _disposition(incident_id: str, incidents: tuple, comm: dict) -> dict:
    inc = next((i for i in incidents if i["incident_id"] == incident_id), None)
    return disposition_for_incident(dict(inc), comm) if inc else {}


def _risk_class(score: float) -> str:
    if score >= 80:
        return "risk-crit"
    if score >= 60:
        return "risk-warn"
    return "risk-low"


def _render_card(inc: dict, selected_id: str | None):
    rc = _risk_class(inc["risk_score"])
    sel = " sel" if inc["incident_id"] == selected_id else ""
    tools_str = inc["dominant_tool"] + (f" 외 {len(inc['tools'])-1}대" if len(inc["tools"]) > 1 else "")
    t_start = inc["window_start"][11:16]
    t_end = inc["window_end"][11:16]
    st.html(
        f'<a href="?view=triage&incident={inc["incident_id"]}" class="t0-card-link" target="_self">'
        f'<div class="t0-card {rc}{sel}">'
        f'<div class="t0-card-top">'
        f'<span class="t0-rank">#{inc["rank"]}</span>'
        f'<span class="t0-title">{inc["title"]}</span>'
        f'<span class="t0-kind">{inc["kind_label"]}</span>'
        f'<span class="t0-risk-chip {rc}">{inc["risk_score"]:.0f}</span>'
        f'</div>'
        f'<div class="t0-meta">'
        f'<span>장비 <span class="mono">{tools_str}</span></span>'
        f'<span>recipe <span class="mono">{inc["dominant_recipe"]}</span></span>'
        f'<span>알람 <span class="mono">{inc["n_alarms"]}</span>건</span>'
        f'<span>max σ <span class="mono">{inc["max_sigma"]}</span></span>'
        f'<span class="mono">{t_start}~{t_end}</span>'
        f'</div>'
        f'</div></a>'
    )


def _render_suspects(inc: dict, comm: dict):
    suspects = comm.get("suspects", [])
    if not suspects:
        st.html('<div class="t0-suspects"><div class="t0-suspects-head">정량 용의자 없음</div></div>')
        return
    max_lift = max(s["lift"] for s in suspects)
    rows = []
    for i, s in enumerate(suspects):
        width = min(100, s["lift"] / max_lift * 100)
        flag = '<span class="t0-top-flag">  ← 최유력</span>' if i == 0 else ""
        rows.append(
            f'<div class="t0-suspect">'
            f'<div class="t0-suspect-top">'
            f'<span class="t0-suspect-dim">{s["dim_label"]}</span>'
            f'<span class="t0-suspect-val">{s["value"]}</span>{flag}'
            f'<span class="t0-suspect-lift">lift {s["lift"]}x</span>'
            f'</div>'
            f'<div class="t0-bar-track"><div class="t0-bar-fill" style="width:{width:.0f}%"></div></div>'
            f'<div class="t0-suspect-meta">불량률 {s["entity_fail_rate"]:.0%} vs 전체 '
            f'{s["baseline_fail_rate"]:.0%}  ·  p={s["p_value"]:.1e}  ·  n={s["entity_total"]}</div>'
            f'</div>'
        )
    st.html(
        '<div class="t0-suspects">'
        '<div class="t0-suspects-head">정량 용의자 (MES genealogy 커몬낼리티)</div>'
        f'<div class="t0-suspects-sub">{inc["title"]} - 불량 웨이퍼가 통계적으로 과대표현한 공통 엔티티 '
        f'(lift = 전체 대비 불량률 배수, p = χ² 유의확률)</div>'
        + "".join(rows) +
        '</div>'
    )


def _render_disposition(inc: dict, disp: dict):
    if not disp or not disp.get("options"):
        return
    inp = disp["inputs"]
    robust = "신뢰구간 내 유지" if disp["robust"] else "불확실성 큼"
    opt_rows = []
    for o in disp["options"]:
        rec = " rec" if o["action"] == disp["recommended"] else ""
        lo, hi = o["cost_range_usd"]
        opt_rows.append(
            f'<div class="t0-disp-opt{rec}">'
            f'<span class="t0-disp-opt-name">{o["label"]}</span>'
            f'<span class="t0-disp-opt-cost">{_usd(o["expected_cost_usd"])}</span>'
            f'<span class="t0-disp-opt-range">범위 {_usd(lo)}~{_usd(hi)}</span>'
            f'</div>'
        )
    st.html(
        '<div class="t0-disp">'
        '<div class="t0-disp-head">리스크 정량 디스포지션 (영향 WIP 처리)</div>'
        f'<div class="t0-disp-rec">'
        f'<span class="t0-disp-rec-label">{disp["recommended_label"]}</span>'
        f'<span class="t0-disp-rec-tag">신뢰도 {disp["confidence"]:.0%} · {robust}</span>'
        f'</div>'
        f'<div class="t0-disp-rationale">{disp["options"][0]["rationale"]}  '
        f'(최악 대비 {_usd(disp["savings_vs_worst_usd"])} 절감)</div>'
        + "".join(opt_rows) +
        f'<div class="t0-disp-foot">입력  공정 {inp["process"]} · 영향 {inp["n_wafers"]}장 · '
        f'불량확률 {inp["p_defect"]:.0%}(±{inp["p_band"]:.0%}) · 현 가치 {_usd(inp["wafer_value_usd"])}/장 · '
        f'완성 가치 {_usd(inp["final_wafer_value_usd"])}/장</div>'
        '</div>'
    )


def render_triage_board():
    ss = st.session_state
    res = _run_triage()
    incidents = res["incidents"]

    st.html(_STYLE)
    st.markdown(
        '<h1 class="fab-main-title">Tier 0 트리아지 보드</h1>'
        '<div class="fab-main-sub"><span>FDC 알람 폭주를 incident로 압축</span>'
        '<span class="sep">·</span><span>한 교대 야간 FDC 스트림</span></div>',
        unsafe_allow_html=True,
    )

    n_clustered = res["n_total"] - res["n_suppressed"]
    st.html(
        '<div class="t0-wrap"><div class="t0-headline">'
        f'<div class="t0-stat"><div class="t0-stat-val">{res["n_total"]}</div>'
        f'<div class="t0-stat-label">원시 FDC 알람</div></div>'
        '<div class="t0-arrow">→</div>'
        f'<div class="t0-stat"><div class="t0-stat-val">{res["n_suppressed"]}</div>'
        f'<div class="t0-stat-label">산발 알람 자동 억제</div></div>'
        '<div class="t0-arrow">→</div>'
        f'<div class="t0-stat"><div class="t0-stat-val accent">{res["n_incidents"]}</div>'
        f'<div class="t0-stat-label">incident (클러스터 {n_clustered}알람)</div></div>'
        f'<div class="t0-stat"><div class="t0-stat-val accent">{res["compression_ratio"]}x</div>'
        f'<div class="t0-stat-label">압축비</div></div>'
        '</div></div>'
    )

    selected_id = ss.get("selected_incident_id")
    for inc in incidents:
        _render_card(inc, selected_id)

    if selected_id:
        sel_inc = next((i for i in incidents if i["incident_id"] == selected_id), None)
        if sel_inc:
            comm = _commonality(selected_id, tuple(incidents))
            _render_suspects(sel_inc, comm)
            _render_disposition(sel_inc, _disposition(selected_id, tuple(incidents), comm))
            st.html(
                '<style>.t0-cta{display:inline-block;margin-top:14px;padding:10px 18px;'
                'border-radius:9px;background:var(--t1-text);color:#fff;font-weight:800;'
                'font-size:14px;text-decoration:none;}</style>'
                f'<a href="?alarm={selected_id}" target="_self" class="t0-cta">'
                f'이 incident 4-Tier 심층 분석 실행 →</a>'
            )
