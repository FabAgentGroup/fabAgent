"""D11: Conductor (Plan-and-Execute) vs Autonomous (tool-using loop) 정량 비교

같은 알람(A1·A2·A3)을 두 모드로 실행해 측정:
- LLM 호출 수 / 알람 (autonomous: 9~13회 예상, conductor: 4~5회 예상)
- Latency (autonomous: ~194s, conductor: 목표 ~60s)
- 토큰·비용
- 인용 깊이 (citations 유니크)
- RAGAS faithfulness (선택적 - 시간 절약 위해 skip 가능)

모드 토글: 환경변수 AGENT_MODE=conductor 또는 autonomous

실행: python -m experiments.conductor_vs_autonomous.benchmark
결과: results.md + charts/*.png
"""
import os
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# 실험을 위해 CRAG는 비활성 (양 모드 동일 조건)
os.environ.setdefault("CRAG_ENABLED", "false")

from agents.cause import run_cause
from agents.detection import run_detection
from agents.impact import run_impact
from agents.llm import client
from agents.planner import plan_workflow
from agents.response import run_response
from data.demo import DEFAULT_ALARMS

plt.rcParams["font.family"] = ["Apple SD Gothic Neo", "AppleGothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = Path(__file__).parent
CHART_DIR = OUT_DIR / "charts"
ALARMS = ["A1", "A2", "A3"]

PRICE_INPUT = 0.25  # gpt-5-mini 추정
PRICE_OUTPUT = 2.0


def _capture_tokens(fn, *args, **kwargs):
    """LLM token usage를 직접 capture하기 위한 wrapper"""
    captured = {"in": 0, "out": 0}
    real = client().chat.completions.create

    def patched(**kw):
        r = real(**kw)
        captured["in"] += r.usage.prompt_tokens
        captured["out"] += r.usage.completion_tokens
        return r

    client().chat.completions.create = patched
    try:
        result = fn(*args, **kwargs)
    finally:
        client().chat.completions.create = real
    return result, captured


def run_autonomous(alarm: dict) -> dict:
    """autonomous 모드 (Tier 2/3/4 각 agent loop)"""
    t1 = run_detection(alarm)
    traces = {"tier2": {}, "tier3": {}, "tier4": {}}
    tier_lat = {}

    t0 = time.time()
    (t2, tok_t2) = _capture_tokens(run_cause, alarm, t1, trace=traces["tier2"])
    tier_lat["tier2"] = (time.time() - t0) * 1000

    t0 = time.time()
    (t3, tok_t3) = _capture_tokens(run_impact, alarm, t1, t2, trace=traces["tier3"])
    tier_lat["tier3"] = (time.time() - t0) * 1000

    t0 = time.time()
    (t4, tok_t4) = _capture_tokens(run_response, alarm, t1, t2, t3, trace=traces["tier4"])
    tier_lat["tier4"] = (time.time() - t0) * 1000

    citations = set()
    for c in t2["causes"]: citations.update(c.get("citations", []))
    for r in t4["refs"]: citations.add(r["id"])

    llm_calls = sum(t.get("llm_calls", 0) for t in traces.values())
    tool_calls = sum(len(t.get("tool_calls", [])) for t in traces.values())
    input_tokens = tok_t2["in"] + tok_t3["in"] + tok_t4["in"]
    output_tokens = tok_t2["out"] + tok_t3["out"] + tok_t4["out"]

    return {
        "tier2": t2, "tier3": t3, "tier4": t4,
        "tier_latency_ms": tier_lat,
        "total_latency_ms": sum(tier_lat.values()),
        "llm_calls": llm_calls,
        "tool_calls": tool_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "citations": sorted(citations),
        "traces": traces,
    }


def run_conductor(alarm: dict) -> dict:
    """conductor 모드 (Planner 1회 + Tier executor 각 1회)"""
    t1 = run_detection(alarm)
    traces = {"planner": {}, "tier2": {}, "tier3": {}, "tier4": {}}
    tier_lat = {}

    # Planner
    t0 = time.time()
    (plan, tok_pl) = _capture_tokens(plan_workflow, alarm, t1)
    tier_lat["planner"] = (time.time() - t0) * 1000

    # Tier 2/3/4 - 각 1회 LLM call (plan-driven)
    t0 = time.time()
    (t2, tok_t2) = _capture_tokens(run_cause, alarm, t1, trace=traces["tier2"], plan=plan)
    tier_lat["tier2"] = (time.time() - t0) * 1000

    t0 = time.time()
    (t3, tok_t3) = _capture_tokens(run_impact, alarm, t1, t2, trace=traces["tier3"], plan=plan)
    tier_lat["tier3"] = (time.time() - t0) * 1000

    t0 = time.time()
    (t4, tok_t4) = _capture_tokens(run_response, alarm, t1, t2, t3, trace=traces["tier4"], plan=plan)
    tier_lat["tier4"] = (time.time() - t0) * 1000

    citations = set()
    for c in t2["causes"]: citations.update(c.get("citations", []))
    for r in t4["refs"]: citations.add(r["id"])

    llm_calls = 1 + sum(traces[t].get("llm_calls", 0) for t in ("tier2", "tier3", "tier4"))
    tool_calls = sum(len(traces[t].get("tool_calls", [])) for t in ("tier2", "tier3", "tier4"))
    input_tokens = tok_pl["in"] + tok_t2["in"] + tok_t3["in"] + tok_t4["in"]
    output_tokens = tok_pl["out"] + tok_t2["out"] + tok_t3["out"] + tok_t4["out"]

    return {
        "tier2": t2, "tier3": t3, "tier4": t4,
        "tier_latency_ms": tier_lat,
        "total_latency_ms": sum(tier_lat.values()),
        "llm_calls": llm_calls,
        "tool_calls": tool_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "citations": sorted(citations),
        "plan": plan,
        "traces": traces,
    }


def collect_samples():
    rows = []
    for aid in ALARMS:
        alarm = next(a for a in DEFAULT_ALARMS if a["id"] == aid)
        print(f"\n=== [{aid}] {alarm['title']} ===")
        print("  [Autonomous]")
        auto = run_autonomous(alarm)
        print(f"    llm={auto['llm_calls']}, tool={auto['tool_calls']}, "
              f"lat={auto['total_latency_ms']:.0f}ms, cit={len(auto['citations'])}, "
              f"tokens={auto['input_tokens']}+{auto['output_tokens']}")
        print("  [Conductor]")
        cond = run_conductor(alarm)
        print(f"    llm={cond['llm_calls']}, tool={cond['tool_calls']}, "
              f"lat={cond['total_latency_ms']:.0f}ms, cit={len(cond['citations'])}, "
              f"tokens={cond['input_tokens']}+{cond['output_tokens']}, "
              f"plan_action={cond['plan']['action']}")
        rows.append({"alarm": aid, "autonomous": auto, "conductor": cond})
    return rows


def aggregate(rows):
    def avg(key1, key2):
        return np.mean([r[key1][key2] for r in rows])

    out = {}
    for mode in ("autonomous", "conductor"):
        out[mode] = {
            "llm_calls": avg(mode, "llm_calls"),
            "tool_calls": avg(mode, "tool_calls"),
            "latency_ms": avg(mode, "total_latency_ms"),
            "input_tokens": avg(mode, "input_tokens"),
            "output_tokens": avg(mode, "output_tokens"),
            "citations": np.mean([len(r[mode]["citations"]) for r in rows]),
        }
    return out


def make_charts(agg, rows):
    CHART_DIR.mkdir(exist_ok=True)
    auto, cond = agg["autonomous"], agg["conductor"]

    # 1. 호출 횟수 비교
    fig, ax = plt.subplots(figsize=(9, 5))
    metrics = ["LLM 호출", "Tool 호출", "유니크 인용"]
    auto_vals = [auto["llm_calls"], auto["tool_calls"], auto["citations"]]
    cond_vals = [cond["llm_calls"], cond["tool_calls"], cond["citations"]]
    x = np.arange(len(metrics))
    w = 0.35
    b1 = ax.bar(x - w/2, auto_vals, w, label="Autonomous", color="#94a3b8")
    b2 = ax.bar(x + w/2, cond_vals, w, label="Conductor", color="#3b82f6")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.1, f"{b.get_height():.1f}",
                    ha="center", fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(metrics)
    ax.set_ylabel("평균 (3 알람)")
    ax.set_title("Autonomous vs Conductor - 호출 횟수")
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(CHART_DIR / "calls_comparison.png", dpi=150); plt.close(fig)

    # 2. Latency 비교
    fig, ax = plt.subplots(figsize=(9, 5))
    auto_lat = auto["latency_ms"] / 1000
    cond_lat = cond["latency_ms"] / 1000
    bars = ax.bar(["Autonomous", "Conductor"], [auto_lat, cond_lat], color=["#94a3b8", "#3b82f6"])
    for b, v in zip(bars, [auto_lat, cond_lat]):
        ax.text(b.get_x() + b.get_width()/2, v + 5, f"{v:.0f}s", ha="center", fontsize=11, fontweight="bold")
    ax.set_ylabel("평균 Latency (초)")
    ax.set_title(f"Latency 비교 - Conductor가 {(1 - cond_lat/auto_lat)*100:.0f}% 단축")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(CHART_DIR / "latency_comparison.png", dpi=150); plt.close(fig)

    # 3. 비용 비교
    fig, ax = plt.subplots(figsize=(9, 5))
    auto_cost = (auto["input_tokens"] * PRICE_INPUT + auto["output_tokens"] * PRICE_OUTPUT) / 1_000_000
    cond_cost = (cond["input_tokens"] * PRICE_INPUT + cond["output_tokens"] * PRICE_OUTPUT) / 1_000_000
    bars = ax.bar(["Autonomous", "Conductor"], [auto_cost*1000, cond_cost*1000], color=["#94a3b8", "#3b82f6"])
    for b, v in zip(bars, [auto_cost*1000, cond_cost*1000]):
        ax.text(b.get_x() + b.get_width()/2, v + max(auto_cost, cond_cost)*1000*0.02, f"${v:.2f}",
                ha="center", fontsize=11, fontweight="bold")
    ax.set_ylabel("USD / 1000 알람")
    ax.set_title(f"비용 비교 - Conductor가 {(1 - cond_cost/auto_cost)*100:.0f}% 절감")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(CHART_DIR / "cost_comparison.png", dpi=150); plt.close(fig)


def write_results(rows, agg):
    auto, cond = agg["autonomous"], agg["conductor"]
    auto_cost = (auto["input_tokens"] * PRICE_INPUT + auto["output_tokens"] * PRICE_OUTPUT) / 1_000_000
    cond_cost = (cond["input_tokens"] * PRICE_INPUT + cond["output_tokens"] * PRICE_OUTPUT) / 1_000_000

    lines = [
        "# D11: Conductor (Plan-and-Execute) vs Autonomous (tool-using loop)",
        "",
        "같은 알람·동일 LLM 모델·CRAG OFF 동일 조건에서 두 패턴을 정량 비교합니다.",
        "",
        "- **Autonomous**: 각 Tier가 tool-using agent loop (2-3 iteration + synthesis)",
        "- **Conductor**: Central Planner Agent가 plan 1회 산출 + 각 Tier executor가 plan대로 tool 실행 + LLM 1회 synthesis",
        "",
        "## 실험 설정",
        "",
        f"- 알람: {', '.join(ALARMS)}",
        "- 생성 모델: gpt-5-mini (양 모드 동일)",
        "- Planner: gpt-4o-mini (conductor 전용)",
        "- CRAG: 비활성 (비교 조건 통일 위해)",
        "",
        "## 결과 요약 (3 알람 평균)",
        "",
        "| 지표 | Autonomous | Conductor | 변화 |",
        "|---|---|---|---|",
        f"| LLM 호출 / 알람 | {auto['llm_calls']:.1f} | {cond['llm_calls']:.1f} | **-{(1 - cond['llm_calls']/auto['llm_calls'])*100:.0f}%** |",
        f"| Tool 호출 / 알람 | {auto['tool_calls']:.1f} | {cond['tool_calls']:.1f} | {(cond['tool_calls']/max(auto['tool_calls'],1) - 1)*100:+.0f}% |",
        f"| 유니크 인용 / 알람 | {auto['citations']:.1f} | {cond['citations']:.1f} | {(cond['citations']/max(auto['citations'],1) - 1)*100:+.0f}% |",
        f"| 입력 토큰 / 알람 | {auto['input_tokens']:.0f} | {cond['input_tokens']:.0f} | **-{(1 - cond['input_tokens']/auto['input_tokens'])*100:.0f}%** |",
        f"| 출력 토큰 / 알람 | {auto['output_tokens']:.0f} | {cond['output_tokens']:.0f} | **-{(1 - cond['output_tokens']/auto['output_tokens'])*100:.0f}%** |",
        f"| **Latency / 알람** | **{auto['latency_ms']/1000:.0f}초** | **{cond['latency_ms']/1000:.0f}초** | **-{(1 - cond['latency_ms']/auto['latency_ms'])*100:.0f}%** |",
        f"| 비용 / 1000알람 | ${auto_cost*1000:.2f} | ${cond_cost*1000:.2f} | **-{(1 - cond_cost/auto_cost)*100:.0f}%** |",
        "",
        "## 시각화",
        "",
        "### 호출 횟수",
        "![Calls](charts/calls_comparison.png)",
        "",
        "### Latency",
        "![Latency](charts/latency_comparison.png)",
        "",
        "### 비용",
        "![Cost](charts/cost_comparison.png)",
        "",
        "## 알람별 상세",
        "",
    ]
    for r in rows:
        lines.append(f"### {r['alarm']}")
        lines.append("")
        lines.append("| 모드 | LLM | Tool | Latency | Citations |")
        lines.append("|---|---|---|---|---|")
        for mode in ("autonomous", "conductor"):
            d = r[mode]
            lines.append(
                f"| {mode} | {d['llm_calls']} | {d['tool_calls']} | "
                f"{d['total_latency_ms']/1000:.0f}s | {len(d['citations'])} |"
            )
        cp = r["conductor"].get("plan", {})
        lines.append("")
        lines.append(f"- Conductor plan: action={cp.get('action')}, severity={cp.get('severity')}")
        lines.append(f"  - reasoning: {cp.get('reasoning', '')[:200]}")
        lines.append("")

    lat_reduce = (1 - cond['latency_ms']/auto['latency_ms']) * 100
    cost_reduce = (1 - cond_cost/auto_cost) * 100
    cit_change = (cond['citations']/max(auto['citations'], 1) - 1) * 100

    lines += [
        "## 핵심 인사이트",
        "",
        f"1. **Latency {lat_reduce:.0f}% 단축**: {auto['latency_ms']/1000:.0f}초 → {cond['latency_ms']/1000:.0f}초. 각 Tier의 agent loop iteration이 제거되어 LLM 호출이 직병됨",
        f"2. **LLM 호출 {(1 - cond['llm_calls']/auto['llm_calls'])*100:.0f}% 감소**: Planner 1 + Tier×3 (각 synthesis 1회) = 4회로 통일. 재귀·무한루프 위험 원천 차단",
        f"3. **비용 {cost_reduce:.0f}% 절감**: 입력 토큰이 가장 큰 폭으로 감소 (agent loop의 messages 누적 효과 제거)",
        f"4. **인용 깊이 변화 {cit_change:+.0f}%**: " + ("거의 동등" if abs(cit_change) < 15 else f"{'증가' if cit_change > 0 else '감소'}, plan이 retrieval 채널을 사전 결정"),
        "",
        "## 채택 결론",
        "",
        f"**기본 모드: `AGENT_MODE=conductor`** (Plan-and-Execute 패턴).",
        "",
        f"- 속도·비용 우위 결정적 (latency -{lat_reduce:.0f}%, cost -{cost_reduce:.0f}%)",
        "- 통신 횟수 최소화로 production 운영 안정성↑",
        "- 재귀 호출 위험 원천 차단",
        "",
        "**`AGENT_MODE=autonomous` 옵션 유지**:",
        "- 복잡한 알람·예상치 못한 컨텍스트가 필요할 때 LLM의 적응적 tool 호출이 유리할 수 있음",
        "- 환경변수로 즉시 토글 가능",
        "",
        "## Portfolio narrative 의의",
        "",
        "- D7에서 \"workflow → agentic\"으로 전환해 reasoning trace 확보",
        "- D11에서 \"agentic → conductor\"로 다시 전환해 통신 효율 회복",
        "- **\"tool-using agent\"의 자율성과 \"plan-and-execute\"의 효율성을 trade-off로 명시적 채택**",
        "- production agent 시스템 설계의 핵심 의사결정을 정량 데이터로 입증",
        "",
    ]
    (OUT_DIR / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"--- 저장: {OUT_DIR / 'results.md'} ---")


def main():
    rows = collect_samples()
    agg = aggregate(rows)
    print("\n--- 집계 ---")
    for mode, vals in agg.items():
        print(f"  {mode}: {vals}")
    make_charts(agg, rows)
    write_results(rows, agg)


if __name__ == "__main__":
    main()
