"""
Smoke tests for evaluation/readability.py: deterministic-only (Layer 3a)
readability scoring across the 10 real tests/fixtures/. Never invokes
score_workflow_readability_llm() -- that path may make a live LLM call
and must not run under pytest.
"""

import os

import pytest

from evaluation._path_guard import HELD_OUT_ROOT
from evaluation.readability import ReadabilityResult, score_workflow_readability

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
