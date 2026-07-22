"""
Tests for evaluation/fact_scoring.py (E1): scores the self-test manifests
in evaluation/scorer_self_test_manifests/ against the real parser output,
plus synthetic per-category tests for categories the self-test manifests
don't naturally exercise (linked_workflow -- no self-test fixture has one)
and for the MISSING/INCORRECT outcome paths (the self-test manifests are
all-correct by construction, so a deliberately wrong expectation is needed
to prove the checkers don't just always report CORRECT).
"""

import os

import pytest

from evaluation.fact_scoring import (
    FactOutcome,
    aggregate_by_category,
    load_manifest,
    score_manifest_against_ir,
    score_workflow,
)
from ir.schema import Job, LinkedWorkflow, Pipeline, SourcePlatform

_EVAL_DIR = os.path.join(os.path.dirname(__file__), "..", "evaluation")
_SELF_TEST_MANIFESTS_DIR = os.path.join(_EVAL_DIR, "scorer_self_test_manifests")

_ALL_12_CATEGORIES = {
    "trigger", "job", "dependency", "step", "condition", "matrix", "secret",
    "environment_variable", "linked_workflow", "permissions", "concurrency",
    "deployment_environment",
}


@pytest.mark.parametrize("manifest_filename", ["rust_ci.manifest.yml", "pandas_unit_tests.manifest.yml"])
def test_self_test_manifest_scores_all_correct(manifest_filename):
    manifest_path = os.path.join(_SELF_TEST_MANIFESTS_DIR, manifest_filename)
    results = score_workflow(manifest_path)
    incorrect = [r for r in results if r.outcome != FactOutcome.CORRECT]
    assert incorrect == [], f"unexpected non-correct results: {incorrect}"
    assert len(results) > 0


def test_rust_ci_manifest_covers_expected_categories():
    manifest_path = os.path.join(_SELF_TEST_MANIFESTS_DIR, "rust_ci.manifest.yml")
    results = score_workflow(manifest_path)
    covered = {r.category for r in results}
    # linked_workflow is the only category with no coverage in rust_ci.yml --
    # covered by a synthetic test below instead.
    assert covered == _ALL_12_CATEGORIES - {"linked_workflow"}


def test_pandas_manifest_covers_expected_categories():
    manifest_path = os.path.join(_SELF_TEST_MANIFESTS_DIR, "pandas_unit_tests.manifest.yml")
    results = score_workflow(manifest_path)
    covered = {r.category for r in results}
    # pandas_unit_tests.yml has no `needs:` (dependency), no deployment
    # environment, and no linked workflow.
    assert covered == _ALL_12_CATEGORIES - {"dependency", "deployment_environment", "linked_workflow"}


def test_all_12_categories_covered_across_both_self_test_manifests_plus_synthetic():
    rust_ci = score_workflow(os.path.join(_SELF_TEST_MANIFESTS_DIR, "rust_ci.manifest.yml"))
    pandas = score_workflow(os.path.join(_SELF_TEST_MANIFESTS_DIR, "pandas_unit_tests.manifest.yml"))
    covered = {r.category for r in rust_ci} | {r.category for r in pandas}
    assert covered | {"linked_workflow"} == _ALL_12_CATEGORIES


# ---------------------------------------------------------------------------
# Synthetic tests: linked_workflow (no self-test fixture has one) and the
# MISSING/INCORRECT outcome paths for a representative set of categories.
# ---------------------------------------------------------------------------

def _pipeline_with_linked_workflow():
    return Pipeline(
        name="synthetic",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file="synthetic.yml",
        linked_workflows=[LinkedWorkflow(target="./.github/workflows/build.yml", relationship="calls")],
    )


def test_linked_workflow_fact_correct():
    fact = {
        "fact_id": "synthetic.linked_workflow.1",
        "category": "linked_workflow",
        "expected": {"target": "./.github/workflows/build.yml", "relationship": "calls"},
    }
    results = score_manifest_against_ir({"facts": [fact]}, _pipeline_with_linked_workflow())
    assert results[0].outcome == FactOutcome.CORRECT


def test_linked_workflow_fact_missing():
    fact = {
        "fact_id": "synthetic.linked_workflow.2",
        "category": "linked_workflow",
        "expected": {"target": "./.github/workflows/nonexistent.yml", "relationship": "calls"},
    }
    results = score_manifest_against_ir({"facts": [fact]}, _pipeline_with_linked_workflow())
    assert results[0].outcome == FactOutcome.MISSING


def test_job_fact_missing_when_job_absent():
    pipeline = Pipeline(name="p", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="p.yml")
    fact = {"fact_id": "p.job.1", "category": "job", "expected": {"name": "nonexistent", "runner": "ubuntu-latest"}}
    results = score_manifest_against_ir({"facts": [fact]}, pipeline)
    assert results[0].outcome == FactOutcome.MISSING


def test_job_fact_incorrect_when_runner_wrong():
    pipeline = Pipeline(
        name="p", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="p.yml",
        jobs=[Job(name="build", runner="ubuntu-latest")],
    )
    fact = {"fact_id": "p.job.1", "category": "job", "expected": {"name": "build", "runner": "windows-latest"}}
    results = score_manifest_against_ir({"facts": [fact]}, pipeline)
    assert results[0].outcome == FactOutcome.INCORRECT


def test_dependency_fact_missing_when_no_such_dependency():
    pipeline = Pipeline(
        name="p", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="p.yml",
        jobs=[Job(name="test", dependencies=[])],
    )
    fact = {"fact_id": "p.dependency.1", "category": "dependency", "expected": {"job": "test", "depends_on": "build"}}
    results = score_manifest_against_ir({"facts": [fact]}, pipeline)
    assert results[0].outcome == FactOutcome.MISSING


def test_permissions_fact_missing_when_unset():
    pipeline = Pipeline(name="p", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="p.yml")
    fact = {"fact_id": "p.permissions.1", "category": "permissions",
             "expected": {"scope": "workflow", "value": {"contents": "read"}}}
    results = score_manifest_against_ir({"facts": [fact]}, pipeline)
    assert results[0].outcome == FactOutcome.MISSING


def test_permissions_fact_incorrect_when_value_differs():
    pipeline = Pipeline(name="p", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="p.yml",
                         permissions={"contents": "write"})
    fact = {"fact_id": "p.permissions.1", "category": "permissions",
             "expected": {"scope": "workflow", "value": {"contents": "read"}}}
    results = score_manifest_against_ir({"facts": [fact]}, pipeline)
    assert results[0].outcome == FactOutcome.INCORRECT


def test_unknown_category_raises():
    pipeline = Pipeline(name="p", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="p.yml")
    fact = {"fact_id": "p.bogus.1", "category": "bogus_category", "expected": {}}
    with pytest.raises(ValueError, match="Unknown fact category"):
        score_manifest_against_ir({"facts": [fact]}, pipeline)


def test_aggregate_by_category():
    pipeline = Pipeline(
        name="p", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="p.yml",
        jobs=[Job(name="build", runner="ubuntu-latest")],
    )
    facts = [
        {"fact_id": "p.job.1", "category": "job", "expected": {"name": "build", "runner": "ubuntu-latest"}},
        {"fact_id": "p.job.2", "category": "job", "expected": {"name": "missing", "runner": "x"}},
    ]
    results = score_manifest_against_ir({"facts": facts}, pipeline)
    aggregate = aggregate_by_category(results)
    assert aggregate["job"] == {"correct": 1, "missing": 1, "incorrect": 0}


def test_load_manifest_reads_yaml():
    manifest = load_manifest(os.path.join(_SELF_TEST_MANIFESTS_DIR, "rust_ci.manifest.yml"))
    assert manifest["workflow_id"] == "rust_ci"
    assert manifest["purpose"] == "scorer_self_test"
