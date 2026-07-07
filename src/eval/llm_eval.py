"""LLM-as-judge evaluation suite with a faithfulness quality gate.

Runs the RAG subgraph over a labelled dataset and scores each answer on three
metrics, using the project's own Gemini model as the judge:

* faithfulness        - is every claim in the answer supported by the retrieved
                        context? (the core anti-hallucination metric)
* answer_relevancy    - does the answer directly address the question?
* context_precision   - how much of the retrieved context is actually relevant?

The process exits non-zero if mean faithfulness falls below the gate, so this
module can be wired into CI to block hallucination regressions before deploy.

Why LLM-as-judge instead of RAGAS: RAGAS does not yet support langchain 1.x
(its import chain references modules removed in newer langchain), and forcing a
compatible RAGAS would downgrade the app's core stack. This harness reuses the
same conceptual metrics with zero extra dependencies and full control.

Dataset format (eval_dataset.json) - a list of objects::

    {"question": str, "ground_truth": str, "persist_key": str}

Usage::

    uv run python -m src.eval.llm_eval
    uv run python -m src.eval.llm_eval --gate 0.9 --dataset src/eval/eval_dataset.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.core.llm import get_llm
from src.core.vector_store import (
    load_vector_store,
    similarity_search_with_sources,
)
from src.graph.rag_graph import build_rag_subgraph

logger = logging.getLogger(__name__)

DEFAULT_DATASET = Path(__file__).parent / "eval_dataset.json"
DEFAULT_GATE = 0.9
DEFAULT_REPORT = Path(__file__).parent / "eval_report.md"
TOP_K = 5


class JudgeScore(BaseModel):
    """Structured judgement returned by the evaluator LLM."""

    score: float = Field(..., ge=0.0, le=1.0, description="Score between 0.0 and 1.0")
    reason: str = Field(..., description="One-sentence justification for the score")


_FAITHFULNESS_SYS = (
    "You are a strict RAG evaluator. Given CONTEXT and an ANSWER, rate from 0.0 "
    "to 1.0 how well every factual claim in the ANSWER is supported by the "
    "CONTEXT. 1.0 = every claim is grounded in the context; 0.0 = the answer is "
    "unsupported or hallucinated. Judge grounding only, not writing quality."
)
_RELEVANCY_SYS = (
    "You are a strict evaluator. Given a QUESTION and an ANSWER, rate from 0.0 to "
    "1.0 how directly and completely the ANSWER addresses the QUESTION. 1.0 = "
    "fully on-point; 0.0 = off-topic or evasive."
)
_PRECISION_SYS = (
    "You are a strict retrieval evaluator. Given a QUESTION and the retrieved "
    "CONTEXT, rate from 0.0 to 1.0 the fraction of the CONTEXT that is relevant "
    "to answering the QUESTION. 1.0 = all of it is relevant; 0.0 = none is."
)


def _structured_judge():
    """Structured-output judge that tolerates a provider-fallback wrapper."""
    base = get_llm()
    if hasattr(base, "with_structured_output"):
        return base.with_structured_output(JudgeScore)
    primary = base.runnable.with_structured_output(JudgeScore)
    fallbacks = [r.with_structured_output(JudgeScore) for r in base.fallbacks]
    return primary.with_fallbacks(fallbacks)


def _judge(judge, system_prompt: str, payload: str) -> float:
    """Run a single judgement and return its numeric score (0.0 on failure)."""
    try:
        result = judge.invoke([("system", system_prompt), ("human", payload)])
        return max(0.0, min(1.0, float(result.score)))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Judge call failed (%s); scoring 0.0", exc)
        return 0.0


def _load_dataset(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or not data:
        raise ValueError(f"Eval dataset {path} must be a non-empty JSON list")
    return data


def _retrieve_contexts(persist_key: str, question: str) -> list[str]:
    """Fetch the same chunks the RAG graph would retrieve, as plain text."""
    db = load_vector_store(persist_key)
    if db is None:
        return []
    result = similarity_search_with_sources(db, question, k=TOP_K, label="eval")
    return [chunk["excerpt"] for chunk in result.get("chunks", [])]


def _generate_answer(rag_graph, persist_key: str, question: str) -> str:
    out = rag_graph.invoke({"question": question, "persist_key": persist_key})
    return out.get("answer") or ""


def summarize_scores(
    faith_scores: list[float],
    rel_scores: list[float],
    prec_scores: list[float],
    gate: float,
    unsupported_claim_counts: list[int] | None = None,
) -> dict:
    """Aggregate raw judge scores into means + gate decision (pure, testable)."""

    def _mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 3) if values else 0.0

    unsupported_claim_counts = unsupported_claim_counts or []
    total_cases = len(faith_scores)
    cases_with_unsupported = sum(1 for count in unsupported_claim_counts if count > 0)
    unsupported_rate = round(cases_with_unsupported / total_cases, 3) if total_cases else 0.0

    faith_mean = _mean(faith_scores)
    return {
        "faithfulness": faith_mean,
        "answer_relevancy": _mean(rel_scores),
        "context_precision": _mean(prec_scores),
        "unsupported_claim_rate": unsupported_rate,
        "total_cases": total_cases,
        "gate": gate,
        "passed": faith_mean >= gate,
    }


def write_markdown_report(summary: dict[str, Any], rows: list[dict[str, Any]], path: Path) -> None:
    """Write a concise eval report for README/interview evidence."""
    status = "PASS" if summary.get("passed") else "FAIL"
    lines = [
        "# UPSC AI RAG Evaluation Report",
        "",
        f"Status: **{status}**",
        "",
        "## Summary",
        "",
        f"- Total cases: {summary.get('total_cases', 0)}",
        f"- Faithfulness: {summary.get('faithfulness', 0.0)}",
        f"- Answer relevancy: {summary.get('answer_relevancy', 0.0)}",
        f"- Context precision: {summary.get('context_precision', 0.0)}",
        f"- Unsupported claim rate: {summary.get('unsupported_claim_rate', 0.0)}",
        f"- Faithfulness gate: {summary.get('gate')}",
        "",
        "## Case results",
        "",
        "| # | Faithfulness | Relevancy | Context precision | Unsupported claims | Question |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for i, row in enumerate(rows, start=1):
        q = str(row.get("question", "")).replace("|", "\\|")[:90]
        lines.append(
            f"| {i} | {row.get('faithfulness', 0.0)} | {row.get('answer_relevancy', 0.0)} | "
            f"{row.get('context_precision', 0.0)} | {row.get('unsupported_claims', 0)} | {q} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- This report is generated by `src.eval.llm_eval`.",
        "- Metrics are intended as a regression signal, not a claim of perfect factual correctness.",
        "- Keep expanding the dataset before using these numbers as production guarantees.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_eval(
    dataset_path: Path = DEFAULT_DATASET,
    gate: float = DEFAULT_GATE,
    report_path: Path | None = None,
) -> bool:
    """Evaluate the dataset and return True if the faithfulness gate passes."""
    dataset = _load_dataset(dataset_path)
    rag_graph = build_rag_subgraph(label="rag")
    judge = _structured_judge()

    faith_scores, rel_scores, prec_scores = [], [], []
    unsupported_claim_counts, rows = [], []

    for row in dataset:
        question = row["question"]
        persist_key = row["persist_key"]
        contexts = _retrieve_contexts(persist_key, question)
        out = rag_graph.invoke({"question": question, "persist_key": persist_key})
        answer = out.get("answer") or ""
        unsupported_claims = out.get("unsupported_claims") or []
        context_blob = "\n\n".join(contexts) if contexts else "(no context retrieved)"

        faith = _judge(
            judge,
            _FAITHFULNESS_SYS,
            f"CONTEXT:\n{context_blob}\n\nANSWER:\n{answer}",
        )
        rel = _judge(
            judge,
            _RELEVANCY_SYS,
            f"QUESTION:\n{question}\n\nANSWER:\n{answer}",
        )
        prec = _judge(
            judge,
            _PRECISION_SYS,
            f"QUESTION:\n{question}\n\nCONTEXT:\n{context_blob}",
        )

        faith_scores.append(faith)
        rel_scores.append(rel)
        prec_scores.append(prec)
        unsupported_claim_counts.append(len(unsupported_claims))
        rows.append({
            "question": question,
            "faithfulness": faith,
            "answer_relevancy": rel,
            "context_precision": prec,
            "unsupported_claims": len(unsupported_claims),
        })
        logger.info(
            "Scored | faith=%.2f rel=%.2f prec=%.2f | %s",
            faith, rel, prec, question[:55],
        )

    summary = summarize_scores(faith_scores, rel_scores, prec_scores, gate, unsupported_claim_counts)

    print("\n" + "=" * 60)
    print(f"LLM-AS-JUDGE RESULTS (mean over {len(dataset)} samples)")
    print(f"  faithfulness             {summary['faithfulness']}")
    print(f"  answer_relevancy         {summary['answer_relevancy']}")
    print(f"  context_precision        {summary['context_precision']}")
    print(f"  unsupported_claim_rate   {summary['unsupported_claim_rate']}")
    print("=" * 60)

    if report_path is not None:
        write_markdown_report(summary, rows, report_path)
        print(f"Report written: {report_path}")

    passed = summary["passed"]
    print(f"Faithfulness gate >= {gate}: {'PASS' if passed else 'FAIL'} (got {summary['faithfulness']})")
    return passed


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="LLM-as-judge eval with a faithfulness gate")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--gate", type=float, default=DEFAULT_GATE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Markdown report path")
    parser.add_argument("--no-report", action="store_true", help="Do not write a markdown report")
    args = parser.parse_args()

    try:
        passed = run_eval(args.dataset, args.gate, None if args.no_report else args.report)
    finally:
        # Release DB pools opened by the RAG graph's memory wiring.
        from src.graph.memory import close_memory

        close_memory()
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
