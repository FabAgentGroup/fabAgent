"""D13: 리스크 정량 디스포지션 vs naive 정책 비용 비교

영향 WIP 처리 결정(진행/보류/재작업/폐기)을 비용엔진이 얼마나 잘 내리는지,
현장에서 흔한 naive 정책 대비 얼마를 아끼는지 정량 평가한다

설정:
- 시나리오: 공정 5종 × true p_defect 그리드 × 영향수 3종 (seed 고정)
- oracle: 진짜 p로 기대비용 최소 결정 (이론 상한)
- engine: 추정 p(true + 노이즈)로 결정 (실제 분석 추정오차 모사)
- naive: 항상 보류 / 항상 진행 / 항상 폐기
- 실현비용: 어떤 결정이든 '진짜 p'에서의 기대비용으로 평가

측정:
- 정책별 총 실현비용 (oracle 대비)
- engine 결정 정확도 (oracle 일치율)
- engine의 naive 대비 절감액
- regret (engine - oracle)

실행: python -m experiments.disposition_eval.benchmark
결과: results.md + charts/*.png
"""
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = ["Apple SD Gothic Neo", "AppleGothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from agents.disposition import compute_disposition, expected_costs

HERE = Path(__file__).parent
CHARTS = HERE / "charts"
CHARTS.mkdir(exist_ok=True)

SEED = 42
PROCESSES = ["Photo", "Etch", "CMP", "Diffusion", "Implant"]
P_GRID = [0.03, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 0.92]
N_GRID = [50, 150, 300]
P_EST_NOISE = 0.10  # 분석 파이프라인의 p_defect 추정 표준편차


def _scenarios():
    for proc in PROCESSES:
        for p in P_GRID:
            for n in N_GRID:
                yield proc, p, n


def _realized(process: str, n: int, true_p: float, action: str) -> float:
    return expected_costs(process, n, true_p)[action]


def _oracle(process: str, n: int, true_p: float) -> tuple[str, float]:
    costs = expected_costs(process, n, true_p)
    action = min(costs, key=costs.get)
    return action, costs[action]


def evaluate():
    rng = random.Random(SEED)
    policies = ["oracle", "engine", "always_hold", "always_continue", "always_scrap"]
    totals = {p: 0.0 for p in policies}
    engine_correct = 0
    n_scen = 0
    regrets = []
    by_p = {p: {"oracle": 0.0, "engine": 0.0, "always_hold": 0.0,
                "always_continue": 0.0, "always_scrap": 0.0} for p in P_GRID}

    for process, true_p, n in _scenarios():
        n_scen += 1
        oracle_act, oracle_cost = _oracle(process, n, true_p)

        # engine: 추정 p로 결정
        p_est = max(0.0, min(1.0, true_p + rng.gauss(0, P_EST_NOISE)))
        engine_act = compute_disposition(process, n, p_est)["recommended"]
        engine_cost = _realized(process, n, true_p, engine_act)
        if engine_act == oracle_act:
            engine_correct += 1
        regrets.append(engine_cost - oracle_cost)

        realized = {
            "oracle": oracle_cost,
            "engine": engine_cost,
            "always_hold": _realized(process, n, true_p, "hold"),
            "always_continue": _realized(process, n, true_p, "continue"),
            "always_scrap": _realized(process, n, true_p, "scrap"),
        }
        for pol, c in realized.items():
            totals[pol] += c
            by_p[true_p][pol] += c

    return {
        "n_scenarios": n_scen,
        "totals": totals,
        "accuracy": engine_correct / n_scen,
        "avg_regret": sum(regrets) / len(regrets),
        "max_regret": max(regrets),
        "by_p": by_p,
        "savings": {
            "vs_hold": totals["always_hold"] - totals["engine"],
            "vs_continue": totals["always_continue"] - totals["engine"],
            "vs_scrap": totals["always_scrap"] - totals["engine"],
        },
    }


# ==================== 차트 ====================

def chart_total_cost(m, path):
    fig, ax = plt.subplots(figsize=(7.5, 4))
    labels = ["oracle\n(이론상한)", "engine\n(채택)", "항상 보류", "항상 진행", "항상 폐기"]
    keys = ["oracle", "engine", "always_hold", "always_continue", "always_scrap"]
    vals = [m["totals"][k] / 1e6 for k in keys]
    colors = ["#64748b", "#10b981", "#3b82f6", "#ef4444", "#f59e0b"]
    bars = ax.bar(labels, vals, color=colors)
    ax.set_ylabel("총 실현비용 (백만 $)")
    ax.set_title(f"디스포지션 정책별 총 비용 ({m['n_scenarios']} 시나리오)", fontweight="bold")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + max(vals) * 0.01, f"${v:.1f}M",
                ha="center", fontweight="bold", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def chart_cost_vs_p(m, path):
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ps = P_GRID
    series = {
        "oracle": ("#64748b", "--"), "engine": ("#10b981", "-"),
        "항상 보류": ("#3b82f6", "-"), "항상 진행": ("#ef4444", "-"), "항상 폐기": ("#f59e0b", "-"),
    }
    key_map = {"oracle": "oracle", "engine": "engine", "항상 보류": "always_hold",
               "항상 진행": "always_continue", "항상 폐기": "always_scrap"}
    for label, (color, ls) in series.items():
        ys = [m["by_p"][p][key_map[label]] / 1e3 for p in ps]
        ax.plot(ps, ys, color=color, ls=ls, marker="o", ms=4, label=label, lw=2)
    ax.set_xlabel("실제 불량확률 p_defect")
    ax.set_ylabel("실현비용 (천 $)")
    ax.set_title("불량확률별 정책 비용 (engine은 oracle에 밀착)", fontweight="bold")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ==================== results.md ====================

def write_results(m):
    t = m["totals"]
    s = m["savings"]
    lines = []
    lines.append("# D13: 리스크 정량 디스포지션 vs naive 정책")
    lines.append("")
    lines.append("영향 WIP 처리 결정(진행/보류/재작업/폐기)을 기대비용 엔진으로 내릴 때,")
    lines.append("현장에서 흔한 naive 정책 대비 비용을 얼마나 아끼는지 정량 평가합니다.")
    lines.append("비용 계산은 전적으로 결정론이라 100% 재현됩니다(seed 고정).")
    lines.append("")
    lines.append("## 실험 설정")
    lines.append("")
    lines.append(f"- 시나리오 {m['n_scenarios']}건: 공정 5종 × p_defect {len(P_GRID)}수준 × 영향수 3종")
    lines.append(f"- oracle: 실제 p로 기대비용 최소 결정 (이론 상한)")
    lines.append(f"- engine: 추정 p(실제 + 노이즈 σ={P_EST_NOISE})로 결정 (분석 추정오차 모사)")
    lines.append(f"- naive: 항상 보류 / 항상 진행 / 항상 폐기")
    lines.append(f"- 실현비용: 어떤 결정이든 '실제 p'에서의 기대비용으로 평가")
    lines.append("")
    lines.append("## 결과: 총 실현비용")
    lines.append("")
    lines.append("| 정책 | 총 비용 | oracle 대비 |")
    lines.append("|---|---|---|")
    base = t["oracle"]
    for key, label in [("oracle", "oracle (이론상한)"), ("engine", "engine (채택)"),
                       ("always_hold", "항상 보류"), ("always_continue", "항상 진행"),
                       ("always_scrap", "항상 폐기")]:
        over = (t[key] - base) / base * 100
        lines.append(f"| {label} | ${t[key]/1e6:.2f}M | +{over:.1f}% |")
    lines.append("")
    lines.append("![total](charts/total_cost.png)")
    lines.append("")
    lines.append("## engine 품질")
    lines.append("")
    lines.append("| 지표 | 값 |")
    lines.append("|---|---|")
    lines.append(f"| oracle 결정 일치율 | **{m['accuracy']:.0%}** |")
    lines.append(f"| 평균 regret (engine - oracle) | ${m['avg_regret']/1e3:.1f}K / 시나리오 |")
    lines.append(f"| engine 총비용 oracle 초과 | **+{(t['engine']-base)/base*100:.1f}%** |")
    lines.append("")
    lines.append("## naive 정책 대비 절감액")
    lines.append("")
    lines.append("| 비교 | 절감액 | 절감률 |")
    lines.append("|---|---|---|")
    lines.append(f"| vs 항상 보류 | ${s['vs_hold']/1e6:.2f}M | {s['vs_hold']/t['always_hold']*100:.1f}% |")
    lines.append(f"| vs 항상 진행 | ${s['vs_continue']/1e6:.2f}M | {s['vs_continue']/t['always_continue']*100:.1f}% |")
    lines.append(f"| vs 항상 폐기 | ${s['vs_scrap']/1e6:.2f}M | {s['vs_scrap']/t['always_scrap']*100:.1f}% |")
    lines.append("")
    lines.append("![cost_vs_p](charts/cost_vs_p.png)")
    lines.append("")
    lines.append("## 결론")
    lines.append("")
    lines.append(f"- 비용엔진은 oracle 결정을 **{m['accuracy']:.0%}** 재현, 총비용은 이론상한 대비 "
                 f"**+{(t['engine']-base)/base*100:.1f}%**에 불과")
    lines.append(f"- 항상 진행(출하)은 고위험 구간에서 폭증, 항상 폐기는 저위험 구간에서 낭비 "
                 f"→ engine은 p에 따라 적응")
    lines.append(f"- 모든 결정에 기대비용·신뢰구간·입력을 노출 → 관리자가 $ 근거로 결재 가능 (감사성)")
    (HERE / "results.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    m = evaluate()
    chart_total_cost(m, CHARTS / "total_cost.png")
    chart_cost_vs_p(m, CHARTS / "cost_vs_p.png")
    write_results(m)
    t = m["totals"]
    base = t["oracle"]
    print(f"시나리오 {m['n_scenarios']}건")
    print(f"oracle 일치율 {m['accuracy']:.0%}, engine 총비용 oracle +{(t['engine']-base)/base*100:.1f}%")
    print(f"절감 vs 항상진행 ${m['savings']['vs_continue']/1e6:.2f}M, "
          f"vs 항상폐기 ${m['savings']['vs_scrap']/1e6:.2f}M, "
          f"vs 항상보류 ${m['savings']['vs_hold']/1e6:.2f}M")
    print("-> results.md + charts 작성 완료")


if __name__ == "__main__":
    main()
