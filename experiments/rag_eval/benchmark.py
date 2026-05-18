"""RAGAS Eval - RAG 백엔드별 답 품질 정량 평가

production 표준 평가 프레임워크. faithfulness/answer_relevancy/context_precision으로
검색 + 생성 품질을 LLM 기반으로 점수화한다.

같은 알람·Tier 2(원인 분석)에 대해 backend별로 실행 후 평가:
- hybrid: BM25 + FAISS + RRF
- hybrid_rerank: hybrid + cross-encoder 재정렬

실행: python -m experiments.rag_eval.benchmark
결과: results.md
"""
import os
from pathlib import Path

from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithoutReference,
    ResponseRelevancy,
)

from agents.cause import _build_query, run_cause
from agents.detection import run_detection
from agents.rag.store import load_document, search
from data.demo import DEFAULT_ALARMS

OUT_DIR = Path(__file__).parent
BACKENDS = ["hybrid", "hybrid_rerank"]
TARGET_ALARM = "A3"


def collect_samples():
    """각 backend별로 Tier 2 실행 후 (question, contexts, answer) 수집"""
    alarm = next(a for a in DEFAULT_ALARMS if a["id"] == TARGET_ALARM)
    tier1 = run_detection(alarm)
    query = _build_query(alarm, tier1)

    rows = {"question": [], "answer": [], "contexts": [], "backend": []}
    for backend in BACKENDS:
        os.environ["RAG_BACKEND"] = backend
        # cause.py가 search()를 호출하므로 backend 따라 다른 결과
        doc_ids = search(query, top_k=3)
        contexts = [load_document(d) for d in doc_ids]

        tier2 = run_cause(alarm, tier1)
        answer = "\n".join(
            f"- {c['name']} ({c['pct']}%): {c['evidence']}" for c in tier2["causes"]
        )

        rows["question"].append(query)
        rows["answer"].append(answer)
        rows["contexts"].append(contexts)
        rows["backend"].append(backend)
        print(f"  {backend}: {len(doc_ids)} docs, {len(tier2['causes'])} causes")
    return rows


def main():
    print(f"=== Tier 2 결과 수집 (알람 {TARGET_ALARM}) ===")
    rows = collect_samples()

    print("\n=== RAGAS 평가 ===")
    # 평가용은 gpt-4o-mini (gpt-5-mini는 temperature 0.01을 지원 안 해 ragas 평가 시 BadRequest 발생)
    eval_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", temperature=0))
    eval_emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

    dataset = Dataset.from_dict(
        {"question": rows["question"], "answer": rows["answer"], "contexts": rows["contexts"]}
    )
    metrics = [
        Faithfulness(llm=eval_llm),
        ResponseRelevancy(llm=eval_llm, embeddings=eval_emb),
        LLMContextPrecisionWithoutReference(llm=eval_llm),
    ]
    result = evaluate(dataset=dataset, metrics=metrics)

    print("\n--- 결과 ---")
    print(result)

    df = result.to_pandas()
    df["backend"] = rows["backend"]
    write_results(df)


def write_results(df):
    metric_cols = [c for c in df.columns if c not in ("question", "answer", "contexts", "backend")]

    lines = [
        "# RAG Eval (RAGAS) - 백엔드별 답 품질 정량 비교",
        "",
        f"같은 알람({TARGET_ALARM}, CMP)에 대해 두 retrieval 백엔드의 Tier 2(원인 분석) 결과를 RAGAS로 평가합니다.",
        "",
        "## 설정",
        "",
        "- 평가 LLM: gpt-5-mini",
        "- 평가 임베딩: text-embedding-3-small",
        "- Metric:",
        "  - **Faithfulness**: 답이 검색된 context에 충실한가 (환각 측정)",
        "  - **Response Relevancy**: 답이 질문에 관련 있는가",
        "  - **LLM Context Precision (no ref)**: 검색된 context 중 관련된 것의 비율",
        "",
        "## 결과",
        "",
        "| Backend | " + " | ".join(metric_cols) + " |",
        "|---|" + "|".join(["---"] * len(metric_cols)) + "|",
    ]
    for _, row in df.iterrows():
        cells = [f"{row[c]:.3f}" if isinstance(row[c], float) else str(row[c]) for c in metric_cols]
        lines.append(f"| {row['backend']} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## 해석",
        "",
        "- **Faithfulness 높음** = LLM이 검색된 문서에 충실히 근거 (환각 적음)",
        "- **Response Relevancy 높음** = 답이 질문에 정확히 답함",
        "- **Context Precision 높음** = 검색된 문서가 답 생성에 실제로 기여",
        "",
        "## 채택",
        "",
        "정량 차이를 보고 적합한 backend 채택. 일반적으로 Hybrid+Rerank가 정밀도에서 우위.",
        "",
    ]
    (OUT_DIR / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"--- 저장: {OUT_DIR / 'results.md'} ---")


if __name__ == "__main__":
    main()
