"""Offline tests for the eval quality-gate logic and dataset integrity.

These run in CI without any API keys or a live vector store: `summarize_scores`
is pure, and the dataset check only reads JSON. The full LLM-as-judge run
(`python -m src.eval.llm_eval`) is a separate, secret-gated CI job.
"""
import json
from pathlib import Path

from src.eval.llm_eval import summarize_scores, write_markdown_report, DEFAULT_DATASET

REQUIRED_KEYS = {"question", "ground_truth", "persist_key"}


def test_gate_passes_when_faithfulness_at_or_above_threshold():
    s = summarize_scores([0.9, 1.0], [0.5], [0.5], gate=0.9)
    assert s["passed"] is True
    assert s["faithfulness"] == 0.95


def test_gate_fails_below_threshold():
    s = summarize_scores([0.8, 0.7], [1.0], [1.0], gate=0.9)
    assert s["passed"] is False


def test_gate_uses_faithfulness_only_not_other_metrics():
    # High relevancy/precision must NOT rescue low faithfulness.
    s = summarize_scores([0.0], [1.0], [1.0], gate=0.9)
    assert s["passed"] is False


def test_empty_scores_are_zero_not_crash():
    s = summarize_scores([], [], [], gate=0.9)
    assert s == {
        "faithfulness": 0.0,
        "answer_relevancy": 0.0,
        "context_precision": 0.0,
        "unsupported_claim_rate": 0.0,
        "total_cases": 0,
        "gate": 0.9,
        "passed": False,
    }


def test_eval_dataset_schema_is_valid():
    data = json.loads(Path(DEFAULT_DATASET).read_text(encoding="utf-8"))
    assert isinstance(data, list) and data, "dataset must be a non-empty list"
    for row in data:
        assert REQUIRED_KEYS <= set(row), f"row missing keys: {row}"
        assert all(isinstance(row[k], str) and row[k] for k in REQUIRED_KEYS)


def test_unsupported_claim_rate_counts_cases_not_claims():
    s = summarize_scores([1.0, 1.0, 1.0], [1.0], [1.0], gate=0.9, unsupported_claim_counts=[0, 2, 1])
    assert s["unsupported_claim_rate"] == 0.667
    assert s["total_cases"] == 3


def test_markdown_report_writer(tmp_path):
    path = tmp_path / "eval_report.md"
    summary = summarize_scores([0.9], [0.8], [0.7], gate=0.9, unsupported_claim_counts=[0])
    write_markdown_report(
        summary,
        [{
            "question": "What is science?",
            "faithfulness": 0.9,
            "answer_relevancy": 0.8,
            "context_precision": 0.7,
            "unsupported_claims": 0,
        }],
        path,
    )
    text = path.read_text(encoding="utf-8")
    assert "UPSC AI RAG Evaluation Report" in text
    assert "Unsupported claim rate" in text
    assert "What is science?" in text
