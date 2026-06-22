"""예지보전 보드 (반응형에서 예측형으로)

CMP 장비별 소모품 잔여수명(RUL)과 예지보전 권고를 보여준다. 운영자는 고장 후가
아니라 마모 추세로 'PM을 언제 넣을지' 미리 결정한다

데이터는 RUL 엔진(결정론)이라 LLM 호출 없이 즉시 렌더
"""
import streamlit as st

from agents.rul import assess_equipment
from data.phm2016.consumables import EQUIPMENT_STATE

_STYLE = """
<style>
.pm-card {
  background: var(--bg-card); border: 1px solid var(--border); border-left-width: 4px;
  border-radius: 10px; padding: 14px 18px; margin-bottom: 12px;
}
.pm-card.st-critical { border-left-color: var(--crit-text); }
.pm-card.st-watch { border-left-color: var(--warn); }
.pm-card.st-healthy { border-left-color: var(--t3-text); }
.pm-top { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.pm-eq { font-family: var(--mono); font-weight: 800; font-size: 15px; color: var(--text-primary); }
.pm-status { font-size: 11px; padding: 2px 9px; border-radius: 7px; font-weight: 800; }
.pm-status.st-critical { background: var(--crit-bg); color: var(--crit-text); }
.pm-status.st-watch { background: var(--t4-bg); color: var(--t4-text); }
.pm-status.st-healthy { background: var(--t3-bg); color: var(--t3-text); }
.pm-rul { margin-left: auto; font-family: var(--mono); font-size: 13px; color: var(--text-secondary); }
.pm-rul b { color: var(--text-primary); font-size: 16px; }
.pm-cons { margin: 10px 0 4px; }
.pm-con { margin-bottom: 9px; }
.pm-con-top { display: flex; align-items: baseline; gap: 8px; font-size: 13px; }
.pm-con-label { font-weight: 700; color: var(--text-primary); min-width: 70px; }
.pm-con-rul { font-family: var(--mono); color: var(--text-secondary); }
.pm-con-mrr { margin-left: auto; font-family: var(--mono); font-size: 11px; color: var(--text-tertiary); }
.pm-bar-track { height: 8px; background: var(--bg-subtle); border-radius: 4px; margin-top: 5px; overflow: hidden; }
.pm-bar-fill { height: 100%; border-radius: 4px; }
.pm-bar-fill.st-critical { background: var(--crit-text); }
.pm-bar-fill.st-watch { background: var(--warn); }
.pm-bar-fill.st-healthy { background: var(--t3-text); }
.pm-rec {
  margin-top: 10px; padding: 10px 14px; border-radius: 9px; background: var(--bg-subtle);
  font-size: 13px; color: var(--text-primary);
}
.pm-rec b { color: var(--t4-text); }
.pm-rec-win { font-family: var(--mono); font-size: 11px; color: var(--text-secondary); margin-top: 3px; }
</style>
"""


@st.cache_data(show_spinner=False)
def _assess(equipment_id: str) -> dict:
    return assess_equipment(equipment_id)


def _con_status(hi: float, rul: float) -> str:
    if rul <= 3 or hi >= 0.9:
        return "st-critical"
    if rul <= 7 or hi >= 0.75:
        return "st-watch"
    return "st-healthy"


def _render_equipment(equipment_id: str):
    a = _assess(equipment_id)
    status = a.get("status", "unknown")
    st_cls = f"st-{status}" if status in ("critical", "watch", "healthy") else "st-healthy"
    status_label = {"critical": "긴급 PM", "watch": "주의", "healthy": "정상"}.get(status, status)

    con_rows = []
    for c in a.get("consumables", []):
        cs = _con_status(c["health_index"], c["rul_lots"])
        width = min(100, c["health_index"] * 100)
        con_rows.append(
            f'<div class="pm-con">'
            f'<div class="pm-con-top">'
            f'<span class="pm-con-label">{c["label"]}</span>'
            f'<span class="pm-con-rul">RUL {c["rul_lots"]:.0f} lot</span>'
            f'<span class="pm-con-mrr">MRR {c["mrr_now"]} (spec≥{c["mrr_spec_low"]:.0f})</span>'
            f'</div>'
            f'<div class="pm-bar-track"><div class="pm-bar-fill {cs}" style="width:{width:.0f}%"></div></div>'
            f'</div>'
        )

    pm = a.get("pm", {})
    rec_html = ""
    if pm:
        rec_html = (
            f'<div class="pm-rec"><b>예지보전 권고</b>  {pm.get("reason", "")}'
            f'<div class="pm-rec-win">권고 PM 윈도우  {pm.get("recommended_window", "-")}</div></div>'
        )

    driver = a.get("driver") or {}
    st.html(
        f'<div class="pm-card {st_cls}">'
        f'<div class="pm-top">'
        f'<span class="pm-eq">{equipment_id}</span>'
        f'<span class="pm-status {st_cls}">{status_label}</span>'
        f'<span class="pm-rul">장비 RUL <b>{a.get("tool_rul_lots", "-")}</b> lot '
        f'(driver {driver.get("label", "-")})</span>'
        f'</div>'
        f'<div class="pm-cons">{"".join(con_rows)}</div>'
        f'{rec_html}'
        f'</div>'
    )


def render_maintenance_board():
    st.html(_STYLE)
    st.markdown(
        '<h1 class="fab-main-title">예지보전 보드</h1>'
        '<div class="fab-main-sub"><span>소모품 잔여수명(RUL) 예측</span>'
        '<span class="sep">·</span><span>반응형에서 예측형 PM으로</span></div>',
        unsafe_allow_html=True,
    )
    st.html(
        '<div style="font-size:12px;color:var(--text-secondary);margin:6px 0 14px;">'
        'PHM 2016 CMP 데이터 기반 마모 모델로 소모품(패드·드레서·멤브레인) 마모 추세를 외삽, '
        'worst 소모품이 장비 PM 시점을 결정합니다. 고장 후가 아니라 한계 도달 전에 PM을 잡습니다.'
        '</div>'
    )
    for equipment_id in EQUIPMENT_STATE:
        _render_equipment(equipment_id)
