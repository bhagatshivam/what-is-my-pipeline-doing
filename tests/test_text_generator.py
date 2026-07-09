"""
Tests for the first slice of Phase 4: generators/text_generator.py's
generate_text(pipeline: Pipeline) -> str.

Covers all 10 real fixtures (no-raise, since none of the 3 hand-written
ground-truth pipelines exercise every real-world shape) plus the 3
hand-written Phase 2 ground-truth IR fixtures (simple/medium/complex),
where exact substring assertions are made against the known IR shapes
documented in tests/fixtures/build_ir_fixtures.py.
"""

import json
import os

import pytest

from generators.text_generator import _topological_job_order, generate_text
from ir.schema import Job, Pipeline
from parsers.github_actions import GitHubActionsParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

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

GROUND_TRUTH_FIXTURE_FILES = [
    "simple_pipeline_ir.json",
    "medium_pipeline_ir.json",
    "complex_pipeline_ir.json",
]


def _load_ground_truth(filename):
    with open(os.path.join(FIXTURES_DIR, filename)) as f:
        return Pipeline.from_dict(json.load(f))


# ---------------------------------------------------------------------------
# No-raise coverage: all 10 real fixtures + all 3 ground-truth fixtures.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", REAL_FIXTURE_FILES)
def test_generate_text_does_not_raise_on_real_fixture(filename):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    output = generate_text(pipeline)
    assert isinstance(output, str)
    assert output.startswith(f"Pipeline: {pipeline.name}")


@pytest.mark.parametrize("filename", GROUND_TRUTH_FIXTURE_FILES)
def test_generate_text_does_not_raise_on_ground_truth_fixture(filename):
    pipeline = _load_ground_truth(filename)
    output = generate_text(pipeline)
    assert isinstance(output, str)
    assert output.startswith(f"Pipeline: {pipeline.name}")


# ---------------------------------------------------------------------------
# Substring assertions against the 3 ground-truth fixtures.
# ---------------------------------------------------------------------------

def test_simple_fixture_text_shape():
    output = generate_text(_load_ground_truth("simple_pipeline_ir.json"))
    assert "Pipeline: Lint" in output
    assert "Source: .github/workflows/lint.yml (GitHub Actions)" in output
    assert "TRIGGERS" in output
    assert "- Runs on every push to main branch" in output
    assert "JOBS (in order)" in output
    assert "1. lint — runs on ubuntu-latest; 2 steps" in output
    assert "SECRETS REQUIRED" not in output
    assert "LINKED WORKFLOWS" not in output


def test_medium_fixture_text_shape():
    output = generate_text(_load_ground_truth("medium_pipeline_ir.json"))
    assert "Pipeline: CI Pipeline" in output
    assert "- Runs on every push to main branch" in output
    assert "- Runs on every pull request targeting main branch" in output
    assert "1. build — runs on ubuntu-latest; 2 steps" in output
    assert (
        "2. test — runs on ubuntu-latest; 2 steps; "
        "matrix: 3 combinations (python-version); after build"
    ) in output
    assert (
        "3. deploy — runs on ubuntu-latest; 1 step; after test; "
        "condition: branch == 'main'"
    ) in output
    assert "SECRETS REQUIRED" in output
    assert "- DEPLOY_API_KEY" in output
    assert "LINKED WORKFLOWS" not in output


def test_complex_fixture_text_shape():
    output = generate_text(_load_ground_truth("complex_pipeline_ir.json"))
    assert "Pipeline: Build, Test & Release" in output
    assert "- Runs on every push with tag matching v*" in output
    assert (
        "- Can be called by other workflows as a reusable workflow "
        "— inputs: release_tag"
    ) in output
    assert (
        "1. build — runs on ubuntu-latest; 3 steps; "
        "matrix: 3 combinations (os); produces dist/"
    ) in output
    assert (
        "2. test — runs on ubuntu-latest; 2 steps; after build; "
        "uses artifacts from build"
    ) in output
    assert (
        "3. release — runs on ubuntu-latest; 2 steps; after test; "
        "uses artifacts from build"
    ) in output
    assert "LINKED WORKFLOWS" in output
    assert "- calls ./.github/workflows/build.yml" in output
    assert "SECRETS REQUIRED" in output
    assert "- PYPI_TOKEN (used in job: release)" in output


# ---------------------------------------------------------------------------
# Topological sort: hand-written cases, proving correctness beyond
# fixture-coincidence (all 10 real fixtures already declare jobs in
# dependency order, so passing those alone wouldn't prove anything).
# ---------------------------------------------------------------------------

def _job(name, deps=()):
    return Job(name=name, dependencies=list(deps))


def test_topological_order_breaks_ties_by_declaration_order():
    # Declared C, B, A; C depends on A. Expected: B, A, C -- neither
    # declaration order (C, B, A) nor alphabetical.
    jobs = [_job("C", deps=["A"]), _job("B"), _job("A")]
    ordered = [j.name for j in _topological_job_order(jobs)]
    assert ordered == ["B", "A", "C"]


def test_topological_order_falls_back_to_declaration_order_on_cycle():
    jobs = [_job("A", deps=["B"]), _job("B", deps=["A"])]
    ordered = [j.name for j in _topological_job_order(jobs)]
    assert ordered == ["A", "B"]


def test_topological_order_ignores_dangling_dependency():
    jobs = [_job("A", deps=["does-not-exist"])]
    ordered = [j.name for j in _topological_job_order(jobs)]
    assert ordered == ["A"]
