"""
Tests for the fourth slice of parsers/github_actions.py: `needs:` parsing
into Job.dependencies (env/secrets, if-conditions, matrix, and reusable
workflows are still out of scope, see module docstring in
parsers/github_actions.py).

Covers all 10 real-world fixtures (every job's Job.dependencies checked
against manual inspection of each file's `needs:` blocks) plus the shapes
no fixture happens to exercise (a `needs:` list with a non-string item, and
a `needs:` value that's neither a string nor a list).
"""

import os

import pytest

from ir.validate import is_valid, validate_pipeline
from parsers.github_actions import GitHubActionsParser, _parse_dependencies

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Exact (job key -> dependencies) map per fixture, taken directly from each
# file's `needs:` blocks. Across all 10 fixtures (58 jobs total): 42 jobs
# have no `needs:`, 6 have single-string `needs:`, and 10 have list-form
# `needs:` (23 dependency edges total). Every referenced key resolves to an
# actual sibling job key in the same file — no dangling references found.
EXPECTED_DEPENDENCIES = {
    "checkout_check_dist.yml": {
        "check-dist": [],
    },
    "eslint_ci.yml": {
        "verify_files": [],
        "test_on_node": [],
        "test_on_browser": [],
        "test_types": [],
        "test_package_manager": [],
        "pnpm_test": [],
    },
    "fastapi_test.yml": {
        "changes": [],
        "test": ["changes"],
        "benchmark": ["changes"],
        "coverage-combine": ["test"],
        "test-alls-green": ["test", "coverage-combine", "benchmark"],
    },
    "flask_tests.yml": {
        "tests": [],
        "typing": [],
    },
    "node_test_linux.yml": {
        "test-linux": [],
    },
    "pandas_unit_tests.yml": {
        "ubuntu": [],
        "macos-windows": [],
        "Linux-32-bit": [],
        "Linux-Musl": [],
        "Windows-MinGW": [],
        "Linux-Sanitizers": [],
        "python-dev": [],
        "emscripten": [],
    },
    "pytorch_lint.yml": {
        "get-label-type": [],
        "get-changed-files": [],
        "lintrunner-clang": ["get-label-type", "get-changed-files"],
        "lintrunner-pyrefly": ["get-label-type", "get-changed-files"],
        "lintrunner-noclang": ["get-label-type", "get-changed-files"],
        "quick-checks": ["get-label-type"],
        "pr-sanity-checks": [],
        "workflow-checks": ["get-label-type"],
        "toc": ["get-label-type"],
        "test-tools": ["get-label-type"],
        "test_run_test": [],
        "test_collect_env": [],
        "link-check": ["get-label-type"],
        "doc-redirects-check": [],
    },
    "rust_ci.yml": {
        "calculate_matrix": [],
        "job": ["calculate_matrix"],
        "outcome": ["calculate_matrix", "job"],
    },
    "setup_python_test.yml": {
        "setup-versions-from-manifest": [],
        "setup-versions-from-file": [],
        "setup-versions-from-file-without-parameter": [],
        "setup-versions-from-standard-pyproject-file": [],
        "setup-versions-from-poetry-pyproject-file": [],
        "setup-versions-from-tool-versions-file": [],
        "setup-versions-from-pipfile-with-python_version": [],
        "setup-versions-from-pipfile-with-python_full_version": [],
        "setup-pre-release-version-from-manifest": [],
        "setup-dev-version": [],
        "setup-prerelease-version": [],
        "setup-versions-noenv": [],
        "check-latest": [],
        "setup-python-multiple-python-versions": [],
    },
    "upload_artifact_test.yml": {
        "build": [],
        "upload-html-report": [],
        "merge": ["build"],
        "cleanup": ["build", "merge"],
    },
}


@pytest.mark.parametrize("filename,expected_deps", EXPECTED_DEPENDENCIES.items())
def test_fixture_job_dependencies(filename, expected_deps):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    actual_deps = {job.name: job.dependencies for job in pipeline.jobs}
    assert actual_deps == expected_deps


@pytest.mark.parametrize("filename", EXPECTED_DEPENDENCIES.keys())
def test_fixture_pipeline_is_valid(filename):
    # First pass where validate.py's dependency checks (dangling deps,
    # circular deps) are exercised against real multi-job graphs.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    issues = validate_pipeline(pipeline)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []
    assert is_valid(pipeline) is True


# ---------------------------------------------------------------------------
# `needs:` shapes, tested directly against _parse_dependencies.
# ---------------------------------------------------------------------------

def test_dependencies_none_when_missing():
    assert _parse_dependencies(None) == []


def test_dependencies_single_string():
    assert _parse_dependencies("build") == ["build"]


def test_dependencies_list_form():
    assert _parse_dependencies(["build", "test"]) == ["build", "test"]


def test_dependencies_list_with_non_string_item_coerced():
    assert _parse_dependencies(["build", 1]) == ["build", "1"]


def test_dependencies_unexpected_shape_returns_empty():
    assert _parse_dependencies({"weird": True}) == []
