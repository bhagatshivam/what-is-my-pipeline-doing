"""
Smoke tests for evaluation/readability.py: deterministic-only (Layer 3a)
readability scoring across the 10 real tests/fixtures/, plus
score_workflow_readability_llm()'s error-surfacing against a fake/
monkeypatched provider only -- never the real Gemini provider, so no test
here ever makes a live LLM call.
"""

import os

import pytest

from evaluation._path_guard import HELD_OUT_ROOT
from evaluation.readability import (
    ReadabilityResult,
    score_workflow_readability,
    score_workflow_readability_llm,
)
from llm.base import LLMProvider

REAL_FIXTURE_FILES = [
    "checkout_check_dist.yml",
    "eslint_ci.yml",
    "fastapi_test.yml",
    "flask_tests.yml",
    "node_test_linux.yml",
    "pandas_unit_tests.yml",
    "pytorch_lint.yml",
    "rust_ci.yml",
    "setup_python_test.yml",
    "upload_artifact_test.yml",
]

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.mark.parametrize("filename", REAL_FIXTURE_FILES)
def test_score_workflow_readability_is_plausible(filename):
    result = score_workflow_readability(os.path.join(_FIXTURES_DIR, filename))
    assert isinstance(result, ReadabilityResult)
    assert result.fixture == filename
    assert result.source == "deterministic"
    # Sanity bounds, not exact values: these formulas can go negative or
    # very high on short/fragmentary text, so the check is "a real number
    # came back, nothing crashed" rather than a tight range.
    assert isinstance(result.flesch_kincaid_grade, float)
    assert isinstance(result.flesch_reading_ease, float)
    assert isinstance(result.gunning_fog, float)
    assert -50.0 < result.flesch_kincaid_grade < 50.0
    assert -50.0 < result.flesch_reading_ease < 150.0
    assert -50.0 < result.gunning_fog < 50.0


def test_score_workflow_readability_refuses_held_out_path():
    held_out_file = os.path.join(str(HELD_OUT_ROOT), "requests_lint.yml")
    with pytest.raises(ValueError):
        score_workflow_readability(held_out_file)


def test_score_workflow_readability_llm_refuses_held_out_path():
    # assert_not_held_out() is the first line of score_workflow_readability_llm(),
    # before get_default_provider() or any parse -- this must raise without
    # ever touching a provider, live or fake.
    held_out_file = os.path.join(str(HELD_OUT_ROOT), "requests_lint.yml")
    with pytest.raises(ValueError):
        score_workflow_readability_llm(held_out_file)


class _FakeFailingProvider(LLMProvider):
    """Every _call_once attempt raises -- verifies
    score_workflow_readability_llm() surfaces the real failure reason
    rather than only a bare "llm_fallback" label. No live call, no SDK,
    no key: this subclasses LLMProvider directly and is monkeypatched in
    as get_default_provider()'s return value below."""

    @property
    def provider_name(self):
        return "fake"

    @property
    def model_name(self):
        return "fake-model"

    @property
    def temperature(self):
        return 0.0

    def _call_once(self, structured_text, pipeline):
        raise ValueError("simulated API failure")


def test_score_workflow_readability_llm_surfaces_real_error(monkeypatch):
    monkeypatch.setattr(
        "evaluation.readability.get_default_provider",
        lambda: _FakeFailingProvider(),
    )
    fixture_path = os.path.join(_FIXTURES_DIR, "checkout_check_dist.yml")
    result = score_workflow_readability_llm(fixture_path)

    assert result.source == "llm_fallback"
    assert result.error is not None
    assert "ValueError: simulated API failure" in result.error


def test_score_workflow_readability_llm_no_provider_labels_missing_key(monkeypatch):
    monkeypatch.setattr("evaluation.readability.get_default_provider", lambda: None)
    fixture_path = os.path.join(_FIXTURES_DIR, "checkout_check_dist.yml")
    result = score_workflow_readability_llm(fixture_path)

    assert result.source == "llm_fallback"
    assert result.error == "GEMINI_API_KEY not set"
