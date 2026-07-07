"""
Tests for the third slice of parsers/github_actions.py: `steps:` parsing
(name, type/value, with_args only — env/condition/continue_on_error are
still out of scope, see module docstring in parsers/github_actions.py).

Covers all 10 real-world fixtures (per-job step counts and spot-checked
uses:/run: steps against manual inspection of each file) plus the shapes no
fixture happens to exercise (no name:, id: with no name:, with: args,
multi-line run: block scalars, a step with neither uses: nor run:, a
non-dict steps: entry).
"""

import os

import pytest
import yaml

from ir.schema import StepType
from parsers.github_actions import (
    GitHubActionsParser,
    _GitHubActionsSafeLoader,
    _parse_steps,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Exact per-job step counts, taken directly from each file's `jobs.*.steps` list.
EXPECTED_STEP_COUNTS = {
    "checkout_check_dist.yml": {"check-dist": 6},
    "eslint_ci.yml": {
        "verify_files": 14, "test_on_node": 6, "test_on_browser": 5,
        "test_types": 9, "test_package_manager": 0, "pnpm_test": 4,
    },
    "fastapi_test.yml": {
        "changes": 2, "test": 13, "benchmark": 6,
        "coverage-combine": 11, "test-alls-green": 2,
    },
    "flask_tests.yml": {"tests": 4, "typing": 5},
    "node_test_linux.yml": {"test-linux": 9},
    "pandas_unit_tests.yml": {
        "ubuntu": 8, "macos-windows": 5, "Linux-32-bit": 3, "Linux-Musl": 4,
        "Windows-MinGW": 3, "Linux-Sanitizers": 5, "python-dev": 4, "emscripten": 8,
    },
    "pytorch_lint.yml": {
        "get-label-type": 0, "get-changed-files": 0, "lintrunner-clang": 0,
        "lintrunner-pyrefly": 0, "lintrunner-noclang": 0, "quick-checks": 0,
        "pr-sanity-checks": 2, "workflow-checks": 0, "toc": 0, "test-tools": 0,
        "test_run_test": 4, "test_collect_env": 6, "link-check": 0,
        "doc-redirects-check": 2,
    },
    "rust_ci.yml": {"calculate_matrix": 3, "job": 33, "outcome": 2},
    "setup_python_test.yml": {
        "setup-versions-from-manifest": 5, "setup-versions-from-file": 6,
        "setup-versions-from-file-without-parameter": 6,
        "setup-versions-from-standard-pyproject-file": 6,
        "setup-versions-from-poetry-pyproject-file": 6,
        "setup-versions-from-tool-versions-file": 3,
        "setup-versions-from-pipfile-with-python_version": 6,
        "setup-versions-from-pipfile-with-python_full_version": 6,
        "setup-pre-release-version-from-manifest": 5, "setup-dev-version": 5,
        "setup-prerelease-version": 5, "setup-versions-noenv": 4,
        "check-latest": 3, "setup-python-multiple-python-versions": 3,
    },
    "upload_artifact_test.yml": {
        "build": 28, "upload-html-report": 6, "merge": 7, "cleanup": 1,
    },
}


@pytest.mark.parametrize("filename,expected_counts", EXPECTED_STEP_COUNTS.items())
def test_fixture_step_counts_per_job(filename, expected_counts):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    actual_counts = {job.name: len(job.steps) for job in pipeline.jobs}
    assert actual_counts == expected_counts


def test_fixture_total_step_count_matches_manual_inspection():
    total = 0
    for filename in EXPECTED_STEP_COUNTS:
        pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
        total += sum(len(job.steps) for job in pipeline.jobs)
    assert total == 299


# (job, first-uses-step value, first-run-step value-prefix) spot checks per fixture.
SPOT_CHECKS = {
    "checkout_check_dist.yml": ("check-dist", "actions/checkout@v7", "npm ci"),
    "eslint_ci.yml": (
        "verify_files", "actions/checkout@v7",
        "go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.1",
    ),
    "fastapi_test.yml": (
        "changes", "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0", None,
    ),
    "flask_tests.yml": (
        "tests", "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",
        "uv run --locked --no-default-groups --group dev tox run",
    ),
    "node_test_linux.yml": (
        "test-linux", "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0", None,
    ),
    "pandas_unit_tests.yml": (
        "ubuntu", "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0", None,
    ),
    "pytorch_lint.yml": (
        "pr-sanity-checks", "pytorch/pytorch/.github/actions/checkout-pytorch@main", None,
    ),
    "rust_ci.yml": ("calculate_matrix", "actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd", None),
    "setup_python_test.yml": ("setup-versions-from-manifest", "actions/checkout@v6", None),
    "upload_artifact_test.yml": ("build", "actions/checkout@v4", "npm ci"),
}


@pytest.mark.parametrize("filename,expected", SPOT_CHECKS.items())
def test_fixture_uses_step_spot_check(filename, expected):
    job_name, expected_uses_value, _ = expected
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    job = next(j for j in pipeline.jobs if j.name == job_name)
    uses_step = next(s for s in job.steps if s.type == StepType.ACTION)
    assert uses_step.value == expected_uses_value


@pytest.mark.parametrize(
    "filename,expected",
    [(f, e) for f, e in SPOT_CHECKS.items() if e[2] is not None],
)
def test_fixture_run_step_spot_check(filename, expected):
    job_name, _, expected_run_prefix = expected
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    job = next(j for j in pipeline.jobs if j.name == job_name)
    run_step = next(s for s in job.steps if s.type == StepType.COMMAND)
    assert run_step.value.startswith(expected_run_prefix)


def test_multiline_run_preserved_in_full_not_truncated():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "checkout_check_dist.yml"))
    job = pipeline.jobs[0]
    step = next(s for s in job.steps if s.name == "Compare the expected and actual dist/ directories")
    assert step.value.count("\n") == 5
    assert "Detected uncommitted changes after build." in step.value
    assert step.value.endswith("fi\n")


def test_id_no_name_step_falls_back_to_uses_and_preserves_step_id():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "fastapi_test.yml"))
    job = next(j for j in pipeline.jobs if j.name == "changes")
    step = next(s for s in job.steps if "paths-filter" in s.value)
    assert step.name == step.value  # fallback: name == the uses: value
    assert step.raw_extras["step_id"] == "filter"


def test_working_directory_preserved_in_raw_extras():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "eslint_ci.yml"))
    job = next(j for j in pipeline.jobs if j.name == "verify_files")
    step = next(s for s in job.steps if s.name == "Install Docs Packages")
    assert step.raw_extras["working-directory"] == "docs"


def test_shell_preserved_in_raw_extras():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "rust_ci.yml"))
    job = next(j for j in pipeline.jobs if j.name == "outcome")
    step = next(s for s in job.steps if s.name == "publish toolstate")
    assert step.raw_extras["shell"] == "bash"


# ---------------------------------------------------------------------------
# Shapes no fixture happens to exercise, tested directly via _parse_steps.
# ---------------------------------------------------------------------------

def _load_steps(yaml_snippet: str):
    data = yaml.load(yaml_snippet, Loader=_GitHubActionsSafeLoader)
    return data["steps"]


def test_no_name_uses_step_falls_back_to_uses_value():
    steps = _parse_steps(_load_steps("steps:\n  - uses: actions/checkout@v4\n"))
    assert steps[0].name == "actions/checkout@v4"
    assert steps[0].type == StepType.ACTION


def test_no_name_run_step_falls_back_to_truncated_first_line():
    long_command = "echo " + ("x" * 80)
    steps = _parse_steps(_load_steps(f"steps:\n  - run: {long_command}\n"))
    assert steps[0].name == long_command[:60] + "..."
    assert steps[0].type == StepType.COMMAND
    assert steps[0].value == long_command  # value itself is never truncated


def test_no_name_multiline_run_step_falls_back_to_first_non_empty_line():
    snippet = (
        "steps:\n"
        "  - run: |\n"
        "      \n"
        "      echo first\n"
        "      echo second\n"
    )
    steps = _parse_steps(_load_steps(snippet))
    assert steps[0].name == "echo first"
    assert steps[0].value == "\necho first\necho second\n"


def test_with_args_populated_as_is():
    snippet = (
        "steps:\n"
        "  - name: Setup Python\n"
        "    uses: actions/setup-python@v5\n"
        "    with:\n"
        "      python-version: '3.12'\n"
        "      cache: pip\n"
    )
    steps = _parse_steps(_load_steps(snippet))
    assert steps[0].with_args == {"python-version": "3.12", "cache": "pip"}


def test_step_with_neither_uses_nor_run_preserves_raw_extras():
    snippet = "steps:\n  - name: mystery step\n    foo: bar\n"
    steps = _parse_steps(_load_steps(snippet))
    assert steps[0].name == "mystery step"
    assert steps[0].type == StepType.COMMAND
    assert steps[0].value == ""
    assert steps[0].raw_extras["unrecognized_step"] == {"name": "mystery step", "foo": "bar"}


def test_non_dict_step_entry_preserved_not_raised():
    steps = _parse_steps(["just a string"])
    assert steps[0].raw_extras["unrecognized_step"] == "just a string"


def test_empty_steps_block():
    assert _parse_steps(None) == []
    assert _parse_steps([]) == []


def test_multiline_run_value_never_truncated_even_when_long():
    long_line = "x" * 200
    snippet = f"steps:\n  - run: |\n      {long_line}\n      second line\n"
    steps = _parse_steps(_load_steps(snippet))
    assert long_line in steps[0].value
    assert "second line" in steps[0].value
    # only the derived *name* is truncated, never Step.value
    assert steps[0].name == long_line[:60] + "..."
