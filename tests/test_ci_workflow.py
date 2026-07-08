"""Static checks for the GitHub Actions quality gate."""
from pathlib import Path


def test_ci_workflow_uses_uv_and_pytest():
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'uv sync --frozen' in text
    assert 'uv run pytest -q' in text
    assert 'uv run python -m py_compile' in text


def test_live_eval_is_gated_and_uploads_report():
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'run_llm_eval' in text
    assert "github.event_name == 'schedule'" in text
    assert 'src.eval.llm_eval --gate 0.9 --report src/eval/eval_report.md' in text
    assert 'actions/upload-artifact@v4' in text


def test_ci_uses_named_secrets_not_placeholder_values():
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'secrets.GOOGLE_API_KEY' in text
    assert 'secrets.QDRANT_URL' in text
    assert '$ secrets.GOOGLE_API_KEY ' not in text


def test_live_smoke_job_present():
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'smoke-live:' in text
    assert 'tests/test_smoke_live.py' in text
    assert 'LIVE_BASE_URL' in text
