"""Workflow vs Agentic 비교 실험

같은 알람(A1·A2·A3)에 대해 두 패턴을 실행하고 정량 비교:
- **Workflow**: Tier 2/3/4 각 1회 LLM 호출, 사전 RAG 1회 (이전 코드 그대로 인라인 재현)
- **Agentic**: tool-using agent (현재 main 코드, agents/*.py)

측정:
- 호출 횟수: LLM calls, tool calls (per tier, per alarm)
- 다양성: 사용한 도구 유니크 수, 인용 문서 유니크 수
- 시간: per-tier latency, total
- 비용: 추정 토큰·USD (gpt-5-mini 단가 기준)
- 품질: 인용된 citation 수 (얕은 grounding vs 깊은 grounding)

차트 3종: 호출 횟수 / latency / 인용 깊이 (matplotlib)

실행: python -m experiments.agentic_vs_workflow.benchmark
결과: results.md + charts/*.png
"""
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from agents.cause import run_cause as agentic_cause
from agents.detection import run_detection
from agents.impact import run_impact as agentic_impact
from agents.llm import SUBAGENT_MODEL, client
from agents.rag.store import load_document, search
from agents.response import run_response as agentic_response
from core.schema import Tier1, Tier2, Tier3, Tier4
from data.demo import DEFAULT_ALARMS
from data.wip import get_affected_wip

plt.rcParams["font.family"] = ["Apple SD Gothic Neo", "AppleGothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = Path(__file__).parent
CHART_DIR = OUT_DIR / "charts"
ALARMS = ["A1", "A2", "A3"]
TOP_K = 3

# gpt-5-mini 추정 단가 (USD per 1M token, 2026 기준 가정)
PRICE_INPUT = 0.25
PRICE_OUTPUT = 2.0


# ==================== Workflow 버전 (이전 단일 호출 방식 재현) ====================

_T2_SCHEMA = {
    "type": "object",
    "properties": {
        "causes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "pct": {"type": "integer"},
                    "evidence": {"type": "string"},
                    "citations": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "pct", "evidence", "citations"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["causes"],
    "additionalProperties": False,
}

_T3_SCHEMA = {
    "type": "object",
    "properties": {
        "yield_loss": {"type": "number"},
        "downstream_dependencies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string"},
                    "delta": {"type": "string"},
                    "tag": {"type": "string"},
                    "kind": {"type": "string", "enum": ["impacted", "minor"]},
                },
                "required": ["stage", "delta", "tag", "kind"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["yield_loss", "downstream_dependencies"],
    "additionalProperties": False,
}

_T4_SCHEMA = {
    "type": "object",
    "properties": {
        "immediate": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "meta": {"type": ["string", "null"]},
                },
                "required": ["text", "meta"],
                "additionalProperties": False,
            },
        },
        "longterm": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "meta": {"type": ["string", "null"]},
                },
                "required": ["text", "meta"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["immediate", "longterm"],
    "additionalProperties": False,
}


def _llm_call(messages, schema, name):
    return client().chat.completions.create(
        model=SUBAGENT_MODEL,
        messages=messages,
        response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
    )


def workflow_run_cause(alarm: dict, tier1: Tier1, trace: dict) -> Tier2:
    sensors = ", ".join(f["name"] for f in tier1["features"])
    query = f"{alarm['title']} {alarm.get('feature') or ''} {sensors} 원인 분석"
    doc_ids = search(query, top_k=TOP_K)
    knowledge = "\n\n".join(f"[{d}]\n{load_document(d)}" for d in doc_ids)
    user = f"""## 이상 알람
- 공정: {alarm['title']}, lot: {alarm['lot_id']}
## Tier 1
- 점수: {tier1['score']}, 센서: {sensors}
## 사내 지식 문서
{knowledge}
위 정보로 원인 2~3개를 산출."""
    resp = _llm_call(
        [
            {"role": "system", "content": "반도체 공정 원인 분석 전문가. JSON 스키마에 맞춰 응답."},
            {"role": "user", "content": user},
        ],
        _T2_SCHEMA,
        "tier2",
    )
    trace["llm_calls"] = 1
    trace["tool_calls"] = 0
    trace["unique_tools"] = 0
    trace["input_tokens"] = resp.usage.prompt_tokens
    trace["output_tokens"] = resp.usage.completion_tokens
    return json.loads(resp.choices[0].message.content)


def workflow_run_impact(alarm: dict, tier1: Tier1, tier2: Tier2, trace: dict) -> Tier3:
    cause_names = " ".join(c["name"] for c in tier2["causes"])
    query = f"{alarm['title']} 하류 후공정 영향 수율 {cause_names}"
    doc_ids = search(query, top_k=TOP_K)
    knowledge = "\n\n".join(f"[{d}]\n{load_document(d)}" for d in doc_ids)
    cause_lines = "\n".join(f"- {c['name']} ({c['pct']}%)" for c in tier2["causes"])
    user = f"""## 알람: {alarm['title']}
## 원인
{cause_lines}
## 사내 지식
{knowledge}
yield_loss와 downstream_dependencies 산출."""
    resp = _llm_call(
        [
            {"role": "system", "content": "반도체 영향 평가 전문가. JSON 스키마에 맞춰 응답."},
            {"role": "user", "content": user},
        ],
        _T3_SCHEMA,
        "tier3_part",
    )
    trace["llm_calls"] = 1
    trace["tool_calls"] = 0
    trace["unique_tools"] = 0
    trace["input_tokens"] = resp.usage.prompt_tokens
    trace["output_tokens"] = resp.usage.completion_tokens
    llm_out = json.loads(resp.choices[0].message.content)
    current = {"stage": alarm["title"].split()[0], "delta": f"+{tier1['score']}", "tag": "현재", "kind": "current"}
    return {
        "yield_loss": round(float(llm_out["yield_loss"]), 1),
        "dependencies": [current] + llm_out["downstream_dependencies"],
        "impact_lots": get_affected_wip(alarm["id"]),
    }


def workflow_run_response(alarm: dict, tier1: Tier1, tier2: Tier2, tier3: Tier3, trace: dict) -> Tier4:
    causes = " ".join(c["name"] for c in tier2["causes"])
    query = f"{alarm['title']} 대응 PM 조치 보류 모니터링 {causes}"
    doc_ids = search(query, top_k=4)
    knowledge = "\n\n".join(f"[{d}]\n{load_document(d)}" for d in doc_ids)
    cause_lines = "\n".join(f"- {c['name']} ({c['pct']}%)" for c in tier2["causes"])
    user = f"""## 알람: {alarm['title']}
## 원인
{cause_lines}
## 영향
- yield_loss: {tier3['yield_loss']}%p
## 사내 지식
{knowledge}
immediate와 longterm 조치 권고."""
    resp = _llm_call(
        [
            {"role": "system", "content": "반도체 대응 권고 전문가. JSON 스키마에 맞춰 응답."},
            {"role": "user", "content": user},
        ],
        _T4_SCHEMA,
        "tier4_part",
    )
    trace["llm_calls"] = 1
    trace["tool_calls"] = 0
    trace["unique_tools"] = 0
    trace["input_tokens"] = resp.usage.prompt_tokens
    trace["output_tokens"] = resp.usage.completion_tokens
    llm_out = json.loads(resp.choices[0].message.content)
    refs = [{"id": d, "desc": d} for d in doc_ids]
    return {"immediate": llm_out["immediate"], "longterm": llm_out["longterm"], "refs": refs}


# ==================== Agentic 버전 wrapper (trace에 token 합계 추가) ====================

def _run_agentic_with_token_capture(fn, *args, trace: dict):
    """현재 agentic 함수는 LLM resp.usage를 직접 노출 안 함 - monkey patch로 capture"""
    captured = {"input": 0, "output": 0}
    real_create = client().chat.completions.create

    def patched(**kwargs):
        r = real_create(**kwargs)
        captured["input"] += r.usage.prompt_tokens
        captured["output"] += r.usage.completion_tokens
        return r

    client().chat.completions.create = patched
    try:
        result = fn(*args, trace=trace)
    finally:
        client().chat.completions.create = real_create
    trace["input_tokens"] = captured["input"]
    trace["output_tokens"] = captured["output"]
    trace["unique_tools"] = len({tc["name"] for tc in trace.get("tool_calls", [])})
    trace["tool_calls_count"] = len(trace.get("tool_calls", []))
    return result


# ==================== Sample 수집 ====================

def _alarm_by_id(aid: str) -> dict:
    return next(a for a in DEFAULT_ALARMS if a["id"] == aid)


def collect_samples():
    rows = []
    for aid in ALARMS:
        alarm = _alarm_by_id(aid)
        tier1 = run_detection(alarm)
        print(f"\n=== [{aid}] {alarm['title']} (T1 score={tier1['score']}) ===")

        # --- Workflow ---
        print("  [Workflow] T2 -> T3 -> T4")
        wf_traces = {"tier2": {}, "tier3": {}, "tier4": {}}
        wf_tier_lat = {}
        t0 = time.time(); wf_t2 = workflow_run_cause(alarm, tier1, wf_traces["tier2"]); wf_tier_lat["tier2"] = (time.time() - t0) * 1000
        t0 = time.time(); wf_t3 = workflow_run_impact(alarm, tier1, wf_t2, wf_traces["tier3"]); wf_tier_lat["tier3"] = (time.time() - t0) * 1000
        t0 = time.time(); wf_t4 = workflow_run_response(alarm, tier1, wf_t2, wf_t3, wf_traces["tier4"]); wf_tier_lat["tier4"] = (time.time() - t0) * 1000
        wf_citations = set()
        for c in wf_t2["causes"]: wf_citations.update(c.get("citations", []))
        for r in wf_t4["refs"]: wf_citations.add(r["id"])

        # --- Agentic ---
        print("  [Agentic] T2 -> T3 -> T4")
        ag_traces = {"tier2": {}, "tier3": {}, "tier4": {}}
        ag_tier_lat = {}
        t0 = time.time(); ag_t2 = _run_agentic_with_token_capture(agentic_cause, alarm, tier1, trace=ag_traces["tier2"]); ag_tier_lat["tier2"] = (time.time() - t0) * 1000
        t0 = time.time(); ag_t3 = _run_agentic_with_token_capture(agentic_impact, alarm, tier1, ag_t2, trace=ag_traces["tier3"]); ag_tier_lat["tier3"] = (time.time() - t0) * 1000
        t0 = time.time(); ag_t4 = _run_agentic_with_token_capture(agentic_response, alarm, tier1, ag_t2, ag_t3, trace=ag_traces["tier4"]); ag_tier_lat["tier4"] = (time.time() - t0) * 1000
        ag_citations = set()
        for c in ag_t2["causes"]: ag_citations.update(c.get("citations", []))
        for r in ag_t4["refs"]: ag_citations.add(r["id"])

        rows.append({
            "alarm": aid,
            "workflow": {
                "traces": wf_traces, "tier_latency_ms": wf_tier_lat,
                "unique_citations": len(wf_citations), "citations": sorted(wf_citations),
            },
            "agentic": {
                "traces": ag_traces, "tier_latency_ms": ag_tier_lat,
                "unique_citations": len(ag_citations), "citations": sorted(ag_citations),
            },
        })

        # 진행 출력
        for pat, key in [("Workflow", "workflow"), ("Agentic", "agentic")]:
            tr = rows[-1][key]["traces"]
            llm = sum(t.get("llm_calls", 0) for t in tr.values())
            tool = sum(t.get("tool_calls_count", t.get("tool_calls", 0)) if isinstance(t.get("tool_calls"), list) else t.get("tool_calls", 0) for t in tr.values())
            print(f"    {pat}: LLM={llm}, tools={tool}, citations={rows[-1][key]['unique_citations']}, total_lat={sum(rows[-1][key]['tier_latency_ms'].values()):.0f}ms")
    return rows


# ==================== 집계 + 차트 + 결과 ====================

def aggregate(rows):
    def per_pat(key):
        llm = [sum(r[key]["traces"][t].get("llm_calls", 0) for t in ("tier2", "tier3", "tier4")) for r in rows]
        tools = []
        for r in rows:
            total = 0
            for t in ("tier2", "tier3", "tier4"):
                tc = r[key]["traces"][t].get("tool_calls")
                if isinstance(tc, list):
                    total += len(tc)
                else:
                    total += tc or 0
            tools.append(total)
        lat = [sum(r[key]["tier_latency_ms"].values()) for r in rows]
        cit = [r[key]["unique_citations"] for r in rows]
        inp = [sum(r[key]["traces"][t].get("input_tokens", 0) for t in ("tier2", "tier3", "tier4")) for r in rows]
        out = [sum(r[key]["traces"][t].get("output_tokens", 0) for t in ("tier2", "tier3", "tier4")) for r in rows]
        return {
            "llm_calls": np.mean(llm), "tool_calls": np.mean(tools),
            "latency_ms": np.mean(lat), "unique_citations": np.mean(cit),
            "input_tokens": np.mean(inp), "output_tokens": np.mean(out),
        }
    return {"workflow": per_pat("workflow"), "agentic": per_pat("agentic")}


def make_charts(agg, rows):
    CHART_DIR.mkdir(exist_ok=True)
    wf, ag = agg["workflow"], agg["agentic"]

    # 1. 호출·도구 비교
    fig, ax = plt.subplots(figsize=(9, 5))
    metrics = ["LLM 호출", "Tool 호출", "유니크 인용"]
    wf_vals = [wf["llm_calls"], wf["tool_calls"], wf["unique_citations"]]
    ag_vals = [ag["llm_calls"], ag["tool_calls"], ag["unique_citations"]]
    x = np.arange(len(metrics))
    w = 0.35
    bars1 = ax.bar(x - w/2, wf_vals, w, label="Workflow", color="#94a3b8")
    bars2 = ax.bar(x + w/2, ag_vals, w, label="Agentic", color="#3b82f6")
    for bars in (bars1, bars2):
        for b in bars:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.1, f"{b.get_height():.1f}", ha="center", fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(metrics)
    ax.set_ylabel("평균 (3 알람)")
    ax.set_title("Workflow vs Agentic - 호출 횟수·인용 깊이")
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(CHART_DIR / "calls_citations.png", dpi=150); plt.close(fig)

    # 2. Latency 분해 (per tier)
    fig, ax = plt.subplots(figsize=(10, 5))
    tiers = ["Tier 2 Cause", "Tier 3 Impact", "Tier 4 Response"]
    wf_lat = [np.mean([r["workflow"]["tier_latency_ms"][f"tier{i}"] for r in rows]) for i in (2, 3, 4)]
    ag_lat = [np.mean([r["agentic"]["tier_latency_ms"][f"tier{i}"] for r in rows]) for i in (2, 3, 4)]
    x = np.arange(len(tiers))
    w = 0.35
    ax.bar(x - w/2, wf_lat, w, label="Workflow", color="#94a3b8")
    ax.bar(x + w/2, ag_lat, w, label="Agentic", color="#3b82f6")
    for i, (wv, av) in enumerate(zip(wf_lat, ag_lat)):
        ax.text(i - w/2, wv + 100, f"{wv:.0f}", ha="center", fontsize=9)
        ax.text(i + w/2, av + 100, f"{av:.0f}", ha="center", fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(tiers)
    ax.set_ylabel("평균 Latency (ms)")
    ax.set_title("Tier별 Latency 비교")
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(CHART_DIR / "latency_per_tier.png", dpi=150); plt.close(fig)

    # 3. 비용 비교
    fig, ax = plt.subplots(figsize=(8.5, 5))
    wf_cost = (wf["input_tokens"] * PRICE_INPUT + wf["output_tokens"] * PRICE_OUTPUT) / 1_000_000
    ag_cost = (ag["input_tokens"] * PRICE_INPUT + ag["output_tokens"] * PRICE_OUTPUT) / 1_000_000
    labels = ["Workflow", "Agentic"]
    costs = [wf_cost, ag_cost]
    bars = ax.bar(labels, costs, color=["#94a3b8", "#3b82f6"])
    for b, v in zip(bars, costs):
        ax.text(b.get_x() + b.get_width()/2, v + max(costs) * 0.02, f"${v*1000:.2f}/1000회", ha="center", fontsize=10)
    ax.set_ylabel("알람당 평균 USD")
    ax.set_title(f"비용 비교 (gpt-5-mini 단가 기준, in=${PRICE_INPUT}/M, out=${PRICE_OUTPUT}/M)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(CHART_DIR / "cost.png", dpi=150); plt.close(fig)


def write_results(rows, agg):
    wf, ag = agg["workflow"], agg["agentic"]
    wf_cost = (wf["input_tokens"] * PRICE_INPUT + wf["output_tokens"] * PRICE_OUTPUT) / 1_000_000
    ag_cost = (ag["input_tokens"] * PRICE_INPUT + ag["output_tokens"] * PRICE_OUTPUT) / 1_000_000

    lines = [
        "# Workflow vs Agentic - 정량 비교",
        "",
        "동일한 4-Tier pipeline을 두 가지 패턴으로 실행해 정량 비교합니다.",
        "- **Workflow**: Tier 2/3/4 각 단계가 사전 RAG 1회 + LLM 1회 (구버전)",
        "- **Agentic**: Tier 2/3/4 각 단계가 LLM tool calling 루프 (현재 채택)",
        "",
        f"알람: {', '.join(ALARMS)} (총 {len(ALARMS)}건, SECOM + PHM CMP)",
        "",
        "## 결과 요약 (3 알람 평균)",
        "",
        "| 지표 | Workflow | Agentic | 배수 |",
        "|---|---|---|---|",
        f"| LLM 호출 / 알람 | {wf['llm_calls']:.1f} | {ag['llm_calls']:.1f} | x{ag['llm_calls']/wf['llm_calls']:.1f} |",
        f"| Tool 호출 / 알람 | {wf['tool_calls']:.1f} | {ag['tool_calls']:.1f} | - |",
        f"| 유니크 인용 / 알람 | {wf['unique_citations']:.1f} | {ag['unique_citations']:.1f} | x{ag['unique_citations']/max(wf['unique_citations'],1):.1f} |",
        f"| 입력 토큰 / 알람 | {wf['input_tokens']:.0f} | {ag['input_tokens']:.0f} | x{ag['input_tokens']/wf['input_tokens']:.1f} |",
        f"| 출력 토큰 / 알람 | {wf['output_tokens']:.0f} | {ag['output_tokens']:.0f} | x{ag['output_tokens']/wf['output_tokens']:.1f} |",
        f"| Latency / 알람 (Tier 2~4) | {wf['latency_ms']:.0f} ms | {ag['latency_ms']:.0f} ms | x{ag['latency_ms']/wf['latency_ms']:.1f} |",
        f"| 비용 / 알람 (USD) | ${wf_cost:.5f} | ${ag_cost:.5f} | x{ag_cost/wf_cost:.1f} |",
        "",
        "## 시각화",
        "",
        "### 호출 횟수·인용 깊이",
        "![Calls](charts/calls_citations.png)",
        "",
        "### Tier별 Latency",
        "![Latency](charts/latency_per_tier.png)",
        "",
        "### 비용",
        "![Cost](charts/cost.png)",
        "",
        "## 알람별 상세",
        "",
    ]
    for r in rows:
        lines.append(f"### {r['alarm']}")
        lines.append("")
        lines.append("| 패턴 | Tier | LLM | Tools | Latency(ms) |")
        lines.append("|---|---|---|---|---|")
        for pat in ("workflow", "agentic"):
            for tier in ("tier2", "tier3", "tier4"):
                tr = r[pat]["traces"][tier]
                tc = tr.get("tool_calls")
                tc_count = len(tc) if isinstance(tc, list) else (tc or 0)
                lines.append(
                    f"| {pat} | {tier} | {tr.get('llm_calls', 0)} | {tc_count} | "
                    f"{r[pat]['tier_latency_ms'][tier]:.0f} |"
                )
        lines.append("")
        lines.append(f"- Workflow 인용: {r['workflow']['citations']}")
        lines.append(f"- Agentic 인용: {r['agentic']['citations']}")
        lines.append("")

    lines += [
        "## 핵심 인사이트",
        "",
        f"1. **인용 깊이 {ag['unique_citations']/max(wf['unique_citations'],1):.1f}배** - agentic은 도구를 자율 호출해 다양한 소스(INC/FMEA/SOP/incident DB)를 결합",
        f"2. **호출 비용 {ag_cost/wf_cost:.1f}배** - LLM 호출이 평균 {wf['llm_calls']:.0f}회 → {ag['llm_calls']:.0f}회, 입력 토큰도 {ag['input_tokens']/wf['input_tokens']:.1f}배",
        f"3. **Latency {ag['latency_ms']/wf['latency_ms']:.1f}배** - tool calling 루프 + synthesis 추가 호출의 자연스러운 비용",
        "4. **agentic만의 정성 신호**: tool 호출 패턴 자체가 reasoning trace - 어떤 정보를 왜 찾았는지 감사·재현 가능",
        "",
        "## 채택 결론",
        "",
        "**현재 채택: Agentic**",
        "- 인용 깊이·근거 다양성이 결정적 - 반도체 fab 도메인에선 multi-source 근거가 안전성·신뢰성 결정",
        f"- 비용 {ag_cost/wf_cost:.1f}배 증가는 알람당 ${(ag_cost-wf_cost)*1000:.2f}/1000회 수준으로 사업적 영향 무시 가능",
        "- Tool 호출 로그가 자체적인 audit trail이 되어 production observability에 유리",
        "",
        "Latency가 critical한 시나리오에선 Workflow로 환경변수 토글 추가 검토 가능 (현재 미구현).",
        "",
    ]
    (OUT_DIR / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"--- 저장: {OUT_DIR / 'results.md'} ---")


def main():
    rows = collect_samples()
    print("\n=== 집계 ===")
    agg = aggregate(rows)
    for pat, vals in agg.items():
        print(f"  {pat}: {vals}")
    make_charts(agg, rows)
    write_results(rows, agg)


if __name__ == "__main__":
    main()
