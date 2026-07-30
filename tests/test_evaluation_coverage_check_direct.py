"""
Tests for evaluation/coverage_check_direct.py: IR-to-output coverage,
built directly from the IR (no manifest). Regression tests against all 10
real tests/fixtures/ -- since these are real, working fixtures, every job/
trigger/secret the parser extracts is expected to appear somewhere in the
generated text; a MISSING result here means Layer 3 silently dropped a
fact, a real regression this test is meant to catch.
"""

import os

import pytest

from evaluation._path_guard import HELD_OUT_ROOT
from evaluation.coverage_check_direct import (
    DirectCoverageOutcome,
    score_coverage_direct,
    score_workflow_coverage_direct,
)
from ir.schema import Job, Pipeline, Secret, SourcePlatform, Trigger, TriggerType

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
def test_score_workflow_coverage_direct_is_full_coverage(filename):
    results = score_workflow_coverage_direct(os.path.join(_FIXTURES_DIR, filename))
    missing = [r for r in results if r.outcome == DirectCoverageOutcome.MISSING]
    assert missing == [], f"{filename}: unexpected MISSING coverage results: {missing}"
    assert all(r.fixture == filename for r in results)


def test_score_workflow_coverage_direct_refuses_held_out_path():
    held_out_file = os.path.join(str(HELD_OUT_ROOT), "requests_lint.yml")
    with pytest.raises(ValueError):
        score_workflow_coverage_direct(held_out_file)


def _pipeline(**kwargs):
    defaults = dict(name="Example", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="example.yml")
    defaults.update(kwargs)
    return Pipeline(**defaults)


def test_score_coverage_direct_detects_missing_job():
    pipeline = _pipeline(jobs=[Job(name="build"), Job(name="test")])
    text = "Pipeline: Example\n\nJOBS (in order)\n1. build — 2 steps\n"
    results = score_coverage_direct("example.yml", pipeline, text)
    job_results = {r.fact_id: r.outcome for r in results if r.category == "job"}
    assert job_results == {"build": DirectCoverageOutcome.CORRECT, "test": DirectCoverageOutcome.MISSING}


def test_score_coverage_direct_detects_missing_secret():
    pipeline = _pipeline(secrets=[Secret(name="TOKEN")])
    text = "Pipeline: Example\n"
    results = score_coverage_direct("example.yml", pipeline, text)
    assert len(results) == 1
    assert results[0].category == "secret"
    assert results[0].outcome == DirectCoverageOutcome.MISSING


def test_score_coverage_direct_trigger_count_mismatch():
    pipeline = _pipeline(triggers=[Trigger(type=TriggerType.PUSH), Trigger(type=TriggerType.PULL_REQUEST)])
    # Only one trigger line present, but the IR has two.
    text = "Pipeline: Example\n\nWHEN IT RUNS\n- Runs on every push\n"
    results = score_coverage_direct("example.yml", pipeline, text)
    assert len(results) == 1
    assert results[0].category == "trigger"
    assert results[0].outcome == DirectCoverageOutcome.MISSING
    assert "expected 2" in results[0].detail and "found 1" in results[0].detail


def test_score_coverage_direct_trigger_count_match():
    pipeline = _pipeline(triggers=[Trigger(type=TriggerType.PUSH), Trigger(type=TriggerType.PULL_REQUEST)])
    text = "Pipeline: Example\n\nWHEN IT RUNS\n- Runs on every push\n- Runs on every pull request\n"
    results = score_coverage_direct("example.yml", pipeline, text)
    assert results[0].outcome == DirectCoverageOutcome.CORRECT


def test_score_coverage_direct_no_triggers_produces_no_trigger_result():
    pipeline = _pipeline()
    results = score_coverage_direct("example.yml", pipeline, "Pipeline: Example\n")
    assert [r for r in results if r.category == "trigger"] == []
