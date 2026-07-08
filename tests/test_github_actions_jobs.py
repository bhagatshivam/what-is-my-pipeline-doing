"""
Tests for the second slice of parsers/github_actions.py: `jobs:` parsing
(job name + runs-on only — steps/needs/env/conditions/matrix are still out
of scope, see module docstring in parsers/github_actions.py).

Covers all 10 real-world fixtures (job keys and runner values checked
against manual inspection of each file) plus the `runs-on` shapes no
fixture happens to use (list-form self-hosted labels, entirely missing).
"""

import os

import pytest
import yaml

from ir.schema import Job
from parsers.github_actions import (
    GitHubActionsParser,
    _GitHubActionsSafeLoader,
    _parse_jobs,
    _parse_runner,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Exact job-key lists per fixture, taken directly from each file's `jobs:` map.
EXPECTED_JOB_KEYS = {
    "checkout_check_dist.yml": ["check-dist"],
    "eslint_ci.yml": [
        "verify_files", "test_on_node", "test_on_browser",
        "test_types", "test_package_manager", "pnpm_test",
    ],
    "fastapi_test.yml": ["changes", "test", "benchmark", "coverage-combine", "test-alls-green"],
    "flask_tests.yml": ["tests", "typing"],
    "node_test_linux.yml": ["test-linux"],
    "pandas_unit_tests.yml": [
        "ubuntu", "macos-windows", "Linux-32-bit", "Linux-Musl",
        "Windows-MinGW", "Linux-Sanitizers", "python-dev", "emscripten",
    ],
    "pytorch_lint.yml": [
        "get-label-type", "get-changed-files", "lintrunner-clang",
        "lintrunner-pyrefly", "lintrunner-noclang", "quick-checks",
        "pr-sanity-checks", "workflow-checks", "toc", "test-tools",
        "test_run_test", "test_collect_env", "link-check", "doc-redirects-check",
    ],
    "rust_ci.yml": ["calculate_matrix", "job", "outcome"],
    "setup_python_test.yml": [
        "setup-versions-from-manifest", "setup-versions-from-file",
        "setup-versions-from-file-without-parameter",
        "setup-versions-from-standard-pyproject-file",
        "setup-versions-from-poetry-pyproject-file",
        "setup-versions-from-tool-versions-file",
        "setup-versions-from-pipfile-with-python_version",
        "setup-versions-from-pipfile-with-python_full_version",
        "setup-pre-release-version-from-manifest", "setup-dev-version",
        "setup-prerelease-version", "setup-versions-noenv",
        "check-latest", "setup-python-multiple-python-versions",
    ],
    "upload_artifact_test.yml": ["build", "upload-html-report", "merge", "cleanup"],
}


@pytest.mark.parametrize("filename,expected_keys", EXPECTED_JOB_KEYS.items())
def test_fixture_job_keys(filename, expected_keys):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    assert [job.name for job in pipeline.jobs] == expected_keys


# (job key -> expected runner) spot checks per fixture.
EXPECTED_RUNNERS = {
    "checkout_check_dist.yml": {"check-dist": "ubuntu-latest"},
    "eslint_ci.yml": {
        "verify_files": "ubuntu-latest",
        "test_on_node": "${{ matrix.os }}",
        "test_package_manager": None,  # reusable-workflow-call job, no runs-on
    },
    "flask_tests.yml": {
        "tests": "${{ matrix.os || 'ubuntu-latest' }}",
        "typing": "ubuntu-latest",
    },
    "pandas_unit_tests.yml": {
        "ubuntu": "${{ matrix.platform }}",
        "Linux-32-bit": "ubuntu-24.04",
        "Windows-MinGW": "windows-2025",
    },
    "pytorch_lint.yml": {
        "get-label-type": None,  # reusable-workflow-call job
        "get-changed-files": None,
        "pr-sanity-checks": "linux.24_04.4x",
        "test_collect_env": "${{ matrix.runner }}",
    },
    "upload_artifact_test.yml": {"build": "${{ matrix.runs-on }}"},
}


@pytest.mark.parametrize(
    "filename,job_key,expected_runner",
    [
        (filename, job_key, runner)
        for filename, jobs in EXPECTED_RUNNERS.items()
        for job_key, runner in jobs.items()
    ],
)
def test_fixture_job_runners(filename, job_key, expected_runner):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    job = next(j for j in pipeline.jobs if j.name == job_key)
    assert job.runner == expected_runner


def test_display_name_set_when_it_differs_from_job_key():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "eslint_ci.yml"))
    job = next(j for j in pipeline.jobs if j.name == "verify_files")
    assert job.raw_extras["display_name"] == "Verify Files"


def test_display_name_absent_when_it_matches_job_key():
    # pytorch_lint.yml's get-label-type job has `name: get-label-type` — identical
    # to the job key, so raw_extras shouldn't carry a redundant display_name.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "pytorch_lint.yml"))
    job = next(j for j in pipeline.jobs if j.name == "get-label-type")
    assert "display_name" not in job.raw_extras


def test_display_name_absent_when_job_has_no_name_field():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "fastapi_test.yml"))
    job = next(j for j in pipeline.jobs if j.name == "test")
    assert job.raw_extras == {}


def test_all_fixture_steps_have_no_condition_yet():
    # steps: name/type/value/with_args parsing landed in a later pass (see
    # tests/test_github_actions_steps.py); env/continue-on-error parsing landed
    # in a later pass still (see tests/test_github_actions_env_secrets.py).
    # `if:` conditions remain unimplemented, so every Step keeps that
    # dataclass default for now.
    for filename in EXPECTED_JOB_KEYS:
        pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
        for job in pipeline.jobs:
            for step in job.steps:
                assert step.condition is None


# ---------------------------------------------------------------------------
# `runs-on` shapes no fixture happens to use, tested directly.
# ---------------------------------------------------------------------------

def test_runner_none_when_missing():
    assert _parse_runner(None) is None


def test_runner_simple_string():
    assert _parse_runner("ubuntu-latest") == "ubuntu-latest"


def test_runner_matrix_expression_stored_unresolved():
    assert _parse_runner("${{ matrix.os }}") == "${{ matrix.os }}"


def test_runner_list_form_joined():
    assert _parse_runner(["self-hosted", "linux", "x64"]) == "self-hosted, linux, x64"


def test_runner_unexpected_shape_stringified():
    assert _parse_runner({"weird": True}) == str({"weird": True})


def test_parse_jobs_none_block():
    assert _parse_jobs(None) == []


def test_parse_jobs_non_dict_block():
    assert _parse_jobs(["not", "a", "dict"]) == []


def test_parse_jobs_reusable_workflow_call_job_has_no_runner():
    snippet = (
        "jobs:\n"
        "  call-other:\n"
        "    uses: ./.github/workflows/other.yml\n"
    )
    jobs_block = yaml.load(snippet, Loader=_GitHubActionsSafeLoader)["jobs"]
    jobs = _parse_jobs(jobs_block)
    assert jobs == [Job(name="call-other", runner=None, raw_extras={})]


def test_parse_jobs_self_hosted_labels():
    snippet = (
        "jobs:\n"
        "  build:\n"
        "    runs-on: [self-hosted, linux, x64]\n"
    )
    jobs_block = yaml.load(snippet, Loader=_GitHubActionsSafeLoader)["jobs"]
    jobs = _parse_jobs(jobs_block)
    assert jobs[0].runner == "self-hosted, linux, x64"
