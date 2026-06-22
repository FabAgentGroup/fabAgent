"""D15: 신뢰도 캘리브레이션 (ECE)

시스템이 내는 confidence가 실제 적중률과 어긋나면(miscalibrated) 운영자가 신뢰할 수
없다. 라벨링된 FDC 알람으로 raw confidence의 ECE를 측정하고, isotonic 보정 후
ECE가 얼마나 줄어드는지 평가한다

데이터: FDC 알람 스트림(라벨 보유). raw confidence = 알람 sigma를 로지스틱으로 매핑한
naive 추정. 실제 결과 = excursion(1)/nuisance(0). train/test 분할로 보정기 학습·평가
seed 고정으로 재현

실행: python -m experiments.calibration_eval.benchmark
결과: results.md + charts/*.png
"""
import math
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = ["Apple SD Gothic Neo", "AppleGothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from agents.calibration import (
    IsotonicCalibrator,
    brier_score,
    expected_calibration_error,
    reliability_curve,
)
from data.fdc.stream import load_alarm_stream

HERE = Path(__file__).parent
CHARTS = HERE / "charts"
CHARTS.mkdir(exist_ok=True)

SEED = 42
N_BINS = 10
# naive 로지스틱 confidence 모델 (보정 전, miscalibrated)
LOGIT_K = 1.5
LOGIT_S0 = 3.5


def _raw_conf(sigma: float) -> float:
    return 1.0 / (1.0 + math.exp(-LOGIT_K * (sigma - LOGIT_S0)))


def _dataset():
    alarms = load_alarm_stream(with_truth=True)
    rows = [(_raw_conf(a["sigma"]), 1 if a["_truth"]["klass"] == "excursion" else 0)
            for a in alarms]
    rng = random.Random(SEED)
    rng.shuffle(rows)
    split = int(len(rows) * 0.5)
    return rows[:split], rows[split:]


def evaluate():
    train, test = _dataset()
    tr_conf, tr_out = [r[0] for r in train], [r[1] for r in train]
    te_conf, te_out = [r[0] for r in test], [r[1] for r in test]

    # 보정 전
    ece_raw = expected_calibration_error(te_conf, te_out, N_BINS)
    brier_raw = brier_score(te_conf, te_out)
    rel_raw = reliability_curve(te_conf, te_out, N_BINS)

    # isotonic 보정 (train으로 학습, test로 평가)
    cal = IsotonicCalibrator().fit(tr_conf, tr_out)
    te_cal = cal.transform(te_conf)
    ece_cal = expected_calibration_error(te_cal, te_out, N_BINS)
    brier_cal = brier_score(te_cal, te_out)
    rel_cal = reliability_curve(te_cal, te_out, N_BINS)

    return {
        "n_train": len(train), "n_test": len(test),
        "ece_raw": ece_raw, "ece_cal": ece_cal,
        "brier_raw": brier_raw, "brier_cal": brier_cal,
        "rel_raw": rel_raw, "rel_cal": rel_cal,
    }


def chart_reliability(m, path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for ax, rel, title, ece in [
        (axes[0], m["rel_raw"], "보정 전 (raw)", m["ece_raw"]),
        (axes[1], m["rel_cal"], "보정 후 (isotonic)", m["ece_cal"]),
    ]:
        ax.plot([0, 1], [0, 1], "--", color="#94a3b8", label="완벽 보정")
        xs = [r["avg_conf"] for r in rel]
        ys = [r["accuracy"] for r in rel]
        ax.plot(xs, ys, "o-", color="#10b981" if "후" in title else "#ef4444",
                lw=2, ms=6, label="모델")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.set_xlabel("예측 신뢰도")
        ax.set_ylabel("실제 적중률")
        ax.set_title(f"{title}  ECE={ece:.3f}", fontweight="bold")
        ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def write_results(m):
    lines = []
    lines.append("# D15: 신뢰도 캘리브레이션 (ECE)")
    lines.append("")
    lines.append("시스템 confidence가 실제 적중률과 일치하는지(calibration) 평가하고,")
    lines.append("isotonic regression 보정으로 ECE를 얼마나 줄이는지 측정합니다.")
    lines.append("운영자가 confidence를 신뢰하려면 '70% 확신'이 실제 70% 적중해야 합니다.")
    lines.append("")
    lines.append("## 실험 설정")
    lines.append("")
    lines.append(f"- 데이터: 라벨링된 FDC 알람 (train {m['n_train']} / test {m['n_test']})")
    lines.append("- raw confidence: 알람 sigma를 로지스틱으로 매핑한 naive 추정 (보정 전)")
    lines.append("- 실제 결과: excursion(1) / nuisance(0)")
    lines.append("- 보정: train으로 isotonic 학습, test로 평가 (누설 없음)")
    lines.append("")
    lines.append("## 결과")
    lines.append("")
    lines.append("| 지표 | 보정 전 | 보정 후 | 개선 |")
    lines.append("|---|---|---|---|")
    ece_drop = (m["ece_raw"] - m["ece_cal"]) / m["ece_raw"] * 100 if m["ece_raw"] else 0
    brier_drop = (m["brier_raw"] - m["brier_cal"]) / m["brier_raw"] * 100 if m["brier_raw"] else 0
    lines.append(f"| ECE | {m['ece_raw']:.3f} | **{m['ece_cal']:.3f}** | **-{ece_drop:.0f}%** |")
    lines.append(f"| Brier score | {m['brier_raw']:.3f} | **{m['brier_cal']:.3f}** | -{brier_drop:.0f}% |")
    lines.append("")
    lines.append("![reliability](charts/reliability.png)")
    lines.append("")
    lines.append("## 결론")
    lines.append("")
    lines.append(f"- raw confidence는 ECE {m['ece_raw']:.3f}로 어긋나 있었음(sigma 기반 naive 추정의 과/소확신)")
    lines.append(f"- isotonic 보정 후 ECE {m['ece_cal']:.3f}로 **{ece_drop:.0f}% 감소**, "
                 f"reliability diagram이 대각선에 밀착")
    lines.append("- 보정된 confidence는 운영자·감사에 신뢰 가능한 수치로 노출 가능")
    (HERE / "results.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    m = evaluate()
    chart_reliability(m, CHARTS / "reliability.png")
    write_results(m)
    print(f"train {m['n_train']} / test {m['n_test']}")
    print(f"ECE {m['ece_raw']:.3f} -> {m['ece_cal']:.3f}, Brier {m['brier_raw']:.3f} -> {m['brier_cal']:.3f}")
    print("-> results.md + charts 작성 완료")


if __name__ == "__main__":
    main()
