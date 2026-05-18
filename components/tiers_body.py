"""Tier 1~4 본문 HTML 빌더 (개발 가이드 9·10장)

각 함수는 본문 HTML 문자열을 반환, tiers.py가 tier-card 안에 합성
Tier 4 액션 바(거절/보류/승인 버튼)는 Streamlit 위젯이라 tiers.py에서 별도 렌더
"""
import base64
import io
from functools import lru_cache
from pathlib import Path

from core.schema import Tier1, Tier2, Tier3, Tier4

A3_TARGET_WAFER = (2058207580, "A")  # detection.ALARM_WAFER A3 매핑과 동일


@lru_cache(maxsize=1)
def _phm_spc_chart_b64() -> str:
    """PHM CMP 전체 wafer의 MRR SPC trend chart, A3 outlier 강조. 1회 생성 캐시"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from data.phm2016.loader import load_phm_cmp

    _, labels = load_phm_cmp()
    mrr = labels.values
    xs = np.arange(len(mrr))

    # outlier 제거 후 정상 분포 통계 (반복 정제)
    mask = np.ones(len(mrr), dtype=bool)
    for _ in range(3):
        m, s = mrr[mask].mean(), mrr[mask].std()
        mask = np.abs((mrr - m) / s) < 3
    nmean = mrr[mask].mean()
    nstd = mrr[mask].std()
    ucl = nmean + 3 * nstd
    lcl = max(0.1, nmean - 3 * nstd)

    # A3 wafer 위치/값
    try:
        a3_idx = labels.index.get_loc(A3_TARGET_WAFER)
        a3_val = labels.loc[A3_TARGET_WAFER]
    except KeyError:
        a3_idx, a3_val = None, None

    # outlier 마스킹 (전체 분포 대비)
    outlier_mask = ~mask

    fig, ax = plt.subplots(figsize=(9, 3.4), dpi=110)
    ax.scatter(xs[~outlier_mask], mrr[~outlier_mask], s=6, color="#6B7788", alpha=0.55, label=f"Normal (n={(~outlier_mask).sum()})")
    ax.scatter(xs[outlier_mask], mrr[outlier_mask], s=10, color="#C04A6E", alpha=0.7, label=f"Outlier |z|>3 (n={outlier_mask.sum()})")
    if a3_idx is not None:
        ax.scatter([a3_idx], [a3_val], s=180, facecolor="#C04A6E", edgecolor="white", linewidth=2.5, zorder=5, label=f"A3 wafer (MRR={a3_val:.0f})")
        ax.annotate(
            "A3 alarm wafer",
            xy=(a3_idx, a3_val),
            xytext=(a3_idx - 400, a3_val * 0.45),
            fontsize=10, color="#C04A6E", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#C04A6E", lw=1.2),
        )

    ax.axhline(nmean, color="#2C5AB8", linewidth=1.2, label=f"mean μ={nmean:.1f}")
    ax.axhline(ucl, color="#C04A6E", linestyle="--", linewidth=1, label=f"UCL μ+3σ={ucl:.1f}")
    ax.axhline(lcl, color="#C04A6E", linestyle="--", linewidth=1)
    ax.fill_between([0, len(mrr)], lcl, ucl, color="#E8F1FD", alpha=0.35, zorder=0)

    ax.set_yscale("log")
    ax.set_ylim(max(0.05, lcl * 0.3), max(mrr) * 1.6)  # A3 outlier가 잘리지 않도록
    ax.set_xlabel("Wafer index (n=1981)", fontsize=9)
    ax.set_ylabel("AVG_REMOVAL_RATE (log scale)", fontsize=9)
    ax.set_title("CMP MRR Control Chart - PHM 2016 (A3 position vs population)", fontsize=10, loc="left")
    ax.legend(loc="lower right", fontsize=8, framealpha=0.92, ncol=3)
    ax.grid(True, alpha=0.2, which="both")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _phm_chart_html() -> str:
    try:
        b64 = _phm_spc_chart_b64()
    except Exception:
        return ""
    return (
        '<div class="phm-chart">'
        '<div class="phm-chart-label">SPC Control Chart · PHM 2016 CMP 실측 MRR</div>'
        f'<img src="data:image/png;base64,{b64}" alt="MRR SPC chart" />'
        '</div>'
    )


def tier_1_body_html(data: Tier1) -> str:
    features = data["features"]
    max_val = features[0]["value"] if features else 1.0
    score = data["score"]

    feature_rows = "".join(
        f"""
        <div class="feat-row">
          <span class="name">{f['name']}</span>
          <div class="bar-track">
            <div class="bar-fill" style="width: {(f['value']/max_val)*100:.0f}%; opacity: {1 - i*0.15:.2f};"></div>
          </div>
          <span class="val">{f['value']:.2f}</span>
        </div>
        """
        for i, f in enumerate(features)
    )

    # PHM CMP 케이스(SLURRY_FLOW 센서 기여)일 때만 실측 trajectory 차트 추가
    chart_html = (
        _phm_chart_html()
        if any("SLURRY_FLOW" in f["name"] for f in features)
        else ""
    )

    return f"""
        <div class="t1-grid">
          <div class="score-tile">
            <div class="score-tile-label">이상 점수</div>
            <div class="score-tile-value">{score:.2f}</div>
            <div class="score-tile-meta">임계 0.50 · 모델 IsolationForest</div>
            <div class="score-tile-bar"><span style="width: {score*100:.0f}%;"></span></div>
          </div>
          <div class="feat-block">
            <div class="feat-block-title">기여 피처 (Top {len(features)}) <span class="hint">|z-score| 기준</span></div>
            {feature_rows}
          </div>
        </div>
        <div class="lot-strip">
          <div>
            <span class="lab">영향 lot · </span>
            <span class="lot">{data['lot']['id']}</span>
          </div>
          <span class="count">{data['lot']['wafers']}장</span>
        </div>
        {chart_html}
    """


def tier_2_body_html(data: Tier2) -> str:
    causes = data["causes"]

    def row(i, c):
        primary = " primary" if i == 0 else ""
        citations_html = "".join(
            f'<span class="cite-tag">📄 {cid}</span>' for cid in c["citations"]
        )
        return f"""
        <div class="cause-row{primary}">
          <div class="cause-rank">{i+1}</div>
          <div class="cause-body">
            <div class="cause-top">
              <span class="cause-name">{c['name']}</span>
              <span class="cause-pct">{c['pct']}%</span>
            </div>
            <div class="cause-bar"><span style="width: {c['pct']}%;"></span></div>
            <div class="cause-evidence">{c['evidence']}</div>
            <div class="cause-cite">{citations_html}</div>
          </div>
          <div></div>
        </div>
        """

    rows = "".join(row(i, c) for i, c in enumerate(causes))
    return f'<div class="cause-list">{rows}</div>'


def tier_3_body_html(data: Tier3) -> str:
    yield_loss = data["yield_loss"]
    # dep-graph CSS는 3노드(1fr 24px 1fr 24px 1fr) 기준이라 처음 3개만 렌더
    deps = data["dependencies"][:3]
    impact_lots = data["impact_lots"]

    dep_nodes = []
    for i, d in enumerate(deps):
        dep_nodes.append(
            f"""
            <div class="dep-node {d['kind']}">
              <div class="dep-stage-name">{d['stage']}</div>
              <div class="dep-delta">{d['delta']}</div>
              <div class="dep-tag">{d['tag']}</div>
            </div>
            """
        )
        if i < len(deps) - 1:
            dep_nodes.append('<div class="dep-arrow">→</div>')

    impact_lots_html = "".join(
        f"""
        <div class="impact-lot">
          <span class="impact-lot-label">{l['label']}</span>
          <span class="impact-lot-value">
            <span class="lots-num">{l['lots']} lot</span>
            <span class="wafer">/ {l['wafers']}장</span>
          </span>
        </div>
        """
        for l in impact_lots
    )

    return f"""
        <div class="t3-grid">
          <div class="loss-tile">
            <div class="loss-tile-label">예상 수율 손실</div>
            <div class="loss-tile-value">{yield_loss}<span class="unit">%p</span></div>
            <div class="loss-tile-meta">동일 스캐너 처리 lot 전체 기준</div>
          </div>
          <div class="dep-block">
            <div class="feat-block-title">공정 의존성 그래프</div>
            <div class="dep-graph">{"".join(dep_nodes)}</div>
          </div>
        </div>
        <div class="impact-lots">{impact_lots_html}</div>
    """


def tier_4_body_html(data: Tier4) -> str:
    def item(i, a):
        meta_html = (
            f'<span class="action-meta">{a["meta"]}</span>'
            if a.get("meta") else "<span></span>"
        )
        return f"""
        <div class="action-item">
          <span class="action-num">{i+1}</span>
          <span class="action-text">{a['text']}</span>
          {meta_html}
        </div>
        """

    imm_items = "".join(item(i, a) for i, a in enumerate(data["immediate"]))
    lng_items = "".join(item(i, a) for i, a in enumerate(data["longterm"]))
    refs_html = "".join(
        f'<li><code>{r["id"]}</code> - {r["desc"]}</li>' for r in data["refs"]
    )

    return f"""
        <div class="action-section">
          <div class="action-section-head">
            <span class="badge imm">즉시 조치</span>
            <span>응급 대응</span>
          </div>
          <div class="action-box urgent">{imm_items}</div>
        </div>
        <div class="action-section">
          <div class="action-section-head">
            <span class="badge lng">중장기</span>
            <span>재발 방지</span>
          </div>
          <div class="action-box">{lng_items}</div>
        </div>
        <div class="refs">
          <div class="refs-title">📚 근거 자료</div>
          <ul>{refs_html}</ul>
        </div>
    """
