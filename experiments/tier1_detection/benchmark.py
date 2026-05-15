"""Tier 1 이상 탐지 모델 벤치마크

SECOM pass/fail 라벨을 정답으로 보고 비지도 이상 탐지 모델을 비교
- IsolationForest
- LocalOutlierFactor
- OneClassSVM
- baseline: 표준화 피처 절대값 평균 (단순 통계)

평가: ROC-AUC, PR-AUC (fail이 6.6%뿐인 불균형 데이터라 PR-AUC를 주지표로 봄)
train에만 fit, test에서 평가 (70/30 stratified split)

실행: python -m experiments.tier1_detection.benchmark
결과: results.md 표 + plots/ 그래프
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM

from data.secom.loader import load_secom
from data.secom.preprocess import SecomPreprocessor

RANDOM_STATE = 42
OUT_DIR = Path(__file__).parent
PLOTS_DIR = OUT_DIR / "plots"

MODELS = {
    "IsolationForest": IsolationForest(n_estimators=200, random_state=RANDOM_STATE),
    "LocalOutlierFactor": LocalOutlierFactor(n_neighbors=20, novelty=True),
    "OneClassSVM": OneClassSVM(nu=0.1, kernel="rbf", gamma="scale"),
    "baseline": None,
}


def anomaly_scores(name, model, X_train, X_test):
    """모델별 이상 점수 반환, 높을수록 이상"""
    if name == "baseline":
        # 표준화된 피처의 절대값 평균, 정상에서 멀수록 큼
        return np.abs(X_test).mean(axis=1)
    model.fit(X_train)
    # score_samples는 높을수록 정상이므로 부호 반전
    return -model.score_samples(X_test)


def main():
    X, y = load_secom()
    y_true = (y == 1).astype(int).to_numpy()  # 1 = fail(이상)

    X_train_df, X_test_df, y_train, y_test = train_test_split(
        X, y_true, test_size=0.3, stratify=y_true, random_state=RANDOM_STATE
    )

    pre = SecomPreprocessor().fit(X_train_df)
    X_train = pre.transform(X_train_df)
    X_test = pre.transform(X_test_df)

    PLOTS_DIR.mkdir(exist_ok=True)
    fig_roc, ax_roc = plt.subplots(figsize=(6, 5))
    fig_pr, ax_pr = plt.subplots(figsize=(6, 5))

    results = []
    for name, model in MODELS.items():
        scores = anomaly_scores(name, model, X_train, X_test)
        roc = roc_auc_score(y_test, scores)
        ap = average_precision_score(y_test, scores)
        results.append((name, roc, ap))

        fpr, tpr, _ = roc_curve(y_test, scores)
        ax_roc.plot(fpr, tpr, label=f"{name} (AUC={roc:.3f})")
        prec, rec, _ = precision_recall_curve(y_test, scores)
        ax_pr.plot(rec, prec, label=f"{name} (AP={ap:.3f})")

    # 참조선, plot 텍스트는 폰트 의존 피하려고 영문 사용
    ax_roc.plot([0, 1], [0, 1], "k--", alpha=0.4, label="random")
    ax_roc.set_xlabel("False Positive Rate")
    ax_roc.set_ylabel("True Positive Rate")
    ax_roc.set_title("Tier 1 Anomaly Detection - ROC")
    ax_roc.legend(loc="lower right", fontsize=8)

    ax_pr.axhline(y_test.mean(), color="k", ls="--", alpha=0.4, label="random")
    ax_pr.set_xlabel("Recall")
    ax_pr.set_ylabel("Precision")
    ax_pr.set_title("Tier 1 Anomaly Detection - Precision-Recall")
    ax_pr.legend(loc="upper right", fontsize=8)

    fig_roc.tight_layout()
    fig_roc.savefig(PLOTS_DIR / "roc.png", dpi=120)
    fig_pr.tight_layout()
    fig_pr.savefig(PLOTS_DIR / "pr.png", dpi=120)

    write_results(results, len(X_train_df), len(X_test_df), int(y_test.sum()))
    for name, roc, ap in sorted(results, key=lambda r: -r[2]):
        print(f"{name:24s}  ROC-AUC={roc:.3f}  PR-AUC={ap:.3f}")


def write_results(results, n_train, n_test, n_test_fail):
    """results.md에 평가 표 기록, PR-AUC 내림차순 정렬"""
    ranked = sorted(results, key=lambda r: -r[2])
    lines = [
        "# Tier 1 이상 탐지 - 모델 벤치마크",
        "",
        "SECOM 데이터셋(반도체 제조 공정 센서)으로 비지도 이상 탐지 모델을 비교합니다.",
        "",
        "## 설정",
        "",
        f"- train {n_train} / test {n_test} (70/30 stratified split)",
        f"- test의 fail(이상) 샘플: {n_test_fail}건",
        "- 전처리: 전결측/상수 컬럼 제거 -> 중앙값 임퓨테이션 -> 표준화",
        "- 평가 지표: ROC-AUC, PR-AUC (불균형 데이터라 PR-AUC가 주지표)",
        "",
        "## 결과 (PR-AUC 내림차순)",
        "",
        "| 모델 | ROC-AUC | PR-AUC |",
        "|---|---|---|",
    ]
    for name, roc, ap in ranked:
        lines.append(f"| {name} | {roc:.3f} | {ap:.3f} |")
    lines += [
        "",
        "![ROC](plots/roc.png)",
        "",
        "![PR](plots/pr.png)",
        "",
        f"## 채택",
        "",
        f"PR-AUC 기준 최고 모델은 **{ranked[0][0]}** "
        f"(PR-AUC {ranked[0][2]:.3f}), agents/detection.py의 baseline으로 사용합니다.",
        "",
    ]
    (OUT_DIR / "results.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
