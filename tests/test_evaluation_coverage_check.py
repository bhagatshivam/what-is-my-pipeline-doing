"""
Tests for evaluation/coverage_check.py (E2, deterministic half): checks
self-test manifest facts against Tool 1's actual generated text output.
"""

import os

import pytest

from evaluation.coverage_check import (
    CoverageOutcome,
    aggregate_by_category,
    score_coverage,
    score_llm_conditions,
    score_workflow_coverage,
)

_SELF_TEST_MANIFESTS_DIR = os.path.join(os.path.dirname(__file__), "..", "evaluation", "scorer_self_test_manifests")


def test_rust_ci_coverage_all_correct_except_env_vars():
    manifest_path = os.path.join(_SELF_TEST_MANIFESTS_DIR, "rust_ci.manifest.yml")
    results = score_workflow_coverage(manifest_path)
    non_correct = [r for r in results if r.outcome != CoverageOutcome.CORRECT]
    # environment_variable facts are expected MISSING -- text_generator.py
    # has no env-var section at all today, a real finding, not a scorer bug.
    assert {r.category for r in non_correct} == {"environment_variable"}
    assert all(r.outcome == CoverageOutcome.MISSING for r in non_correct)


def test_pandas_coverage_all_correct_except_env_vars():
    manifest_path = os.path.join(_SELF_TEST_MANIFESTS_DIR, "pandas_unit_tests.manifest.yml")
    results = score_workflow_coverage(manifest_path)
    non_correct = [r for r in results if r.outcome != CoverageOutcome.CORRECT]
    assert {r.category for r in non_correct} == {"environment_variable"}


def test_job_coverage_missing_when_job_line_absent():
    fact = {"fact_id": "p.job.1", "category": "job", "expected": {"name": "nonexistent"}}
    results = score_coverage({"facts": [fact]}, "Pipeline: p\nSource: p.yml (GitHub Actions)\n")
    assert results[0].outcome == CoverageOutcome.MISSING


def test_secret_coverage_correct_when_present():
    fact = {"fact_id": "p.secret.1", "category": "secret", "expected": {"name": "MY_TOKEN"}}
    text = "SECRETS REQUIRED\n- MY_TOKEN\n"
    results = score_coverage({"facts": [fact]}, text)
    assert results[0].outcome == CoverageOutcome.CORRECT


def test_permissions_coverage_workflow_scope():
    fact = {"fact_id": "p.permissions.1", "category": "permissions", "expected": {"scope": "workflow"}}
    text = "Pipeline: p\nSource: p.yml (GitHub Actions)\nPermissions: contents: read\n"
    results = score_coverage({"facts": [fact]}, text)
    assert results[0].outcome == CoverageOutcome.CORRECT


def test_aggregate_by_category():
    fact_present = {"fact_id": "p.job.1", "category": "job", "expected": {"name": "build"}}
    fact_absent = {"fact_id": "p.job.2", "category": "job", "expected": {"name": "missing"}}
    text = "1. build — 2 steps\n"
    results = score_coverage({"facts": [fact_present, fact_absent]}, text)
    aggregate = aggregate_by_category(results)
    assert aggregate["job"] == {"correct": 1, "missing": 1, "unsupported_claim": 0}


def test_llm_conditions_not_yet_available():
    with pytest.raises(NotImplementedError):
        score_llm_conditions()
