"""Tier 1~4 본문 HTML 빌더 (개발 가이드 9·10장)

각 함수는 본문 HTML 문자열을 반환, tiers.py가 tier-card 안에 합성
Tier 4 액션 바(거절/보류/승인 버튼)는 Streamlit 위젯이라 tiers.py에서 별도 렌더
"""
from core.schema import Tier1, Tier2, Tier3, Tier4


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
        f'<li><code>{r["id"]}</code> — {r["desc"]}</li>' for r in data["refs"]
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
