"""
Tests for the final slice of parsers/github_actions.py (Phase 3): reusable-
workflow relationships -> Pipeline.linked_workflows, using ir/schema.py's
LinkedWorkflow dataclass.

Two distinct mechanisms are covered:
  - A job-level `uses:` (the job itself IS a reusable-workflow call) ->
    LinkedWorkflow(relationship="calls"), plus the call's own `uses:`/
    `with:`/`secrets:` preserved on that job's own raw_extras.
  - An `on: workflow_run` trigger (this pipeline fires when another
    workflow completes) -> LinkedWorkflow(relationship="triggered_by").

`on: workflow_call` (this pipeline being callable BY another workflow) is
deliberately NOT promoted to a LinkedWorkflow entry — the callee has no
way to learn its callers' identity from its own file. That data stays
solely on the existing Trigger(type=WORKFLOW_CALL) object; a test below
confirms this exclusion is real behavior, not just documented intent.

Only 2 of the 10 real fixtures (eslint_ci.yml, pytorch_lint.yml) use
job-level `uses:`; none uses `workflow_run`/`workflow_call` at all — those
mechanisms are covered by hand-written snippets instead.
"""

import glob
import os

import pytest
import yaml

from ir.schema import LinkedWorkflow
from ir.validate import validate_pipeline
from parsers.github_actions import (
    GitHubActionsParser,
    _GitHubActionsSafeLoader,
    _parse_jobs,
    _parse_linked_workflows,
    _parse_triggers,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
ALL_FIXTURES = sorted(glob.glob(os.path.join(FIXTURES_DIR, "*.yml")))

# Ground truth per fixture, verified directly against the parser's own
# output (post (target, relationship) dedup): 8 fixtures have none, and
# the only real mechanism exercised is job-level `uses:` (relationship
# "calls") — no fixture has an `on: workflow_run`/`workflow_call` trigger.
EXPECTED_LINKED_WORKFLOWS = {
    "checkout_check_dist.yml": [],
    "eslint_ci.yml": [
        LinkedWorkflow(
            target="eslint/workflows/.github/workflows/ci-package-manager.yml@main",
            relationship="calls",
        ),
    ],
    "fastapi_test.yml": [],
    "flask_tests.yml": [],
    "node_test_linux.yml": [],
    "pandas_unit_tests.yml": [],
    "pytorch_lint.yml": [
        LinkedWorkflow(
            target="pytorch/pytorch/.github/workflows/_runner-determinator.yml@main",
            relationship="calls",
        ),
        LinkedWorkflow(target="./.github/workflows/_get-changed-files.yml", relationship="calls"),
        LinkedWorkflow(target="./.github/workflows/_lint.yml", relationship="calls"),
        LinkedWorkflow(target="./.github/workflows/_link_check.yml", relationship="calls"),
    ],
    "rust_ci.yml": [],
    "setup_python_test.yml": [],
    "upload_artifact_test.yml": [],
}


@pytest.mark.parametrize("filename,expected", EXPECTED_LINKED_WORKFLOWS.items())
def test_fixture_linked_workflows(filename, expected):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    assert pipeline.linked_workflows == expected


def test_pytorch_lint_dedups_seven_calls_to_lint_yml_into_one_entry():
    # 7 of pytorch_lint.yml's 10 uses:-jobs point at the identical
    # ./.github/workflows/_lint.yml file (lintrunner-clang, lintrunner-pyrefly,
    # lintrunner-noclang, quick-checks, workflow-checks, toc, test-tools) —
    # LinkedWorkflow has no job-distinguishing field, so these collapse to 1.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "pytorch_lint.yml"))
    lint_yml_entries = [
        lw for lw in pipeline.linked_workflows
        if lw.target == "./.github/workflows/_lint.yml"
    ]
    assert lint_yml_entries == [
        LinkedWorkflow(target="./.github/workflows/_lint.yml", relationship="calls")
    ]


# ---------------------------------------------------------------------------
# Per-job raw_extras preservation (uses:/with:/secrets:), independent of the
# pipeline-level dedup above.
# ---------------------------------------------------------------------------

# (fixture, job_key) -> (expected uses value, expects "with" key present)
EXPECTED_JOB_RAW_EXTRAS = {
    ("eslint_ci.yml", "test_package_manager"): (
        "eslint/workflows/.github/workflows/ci-package-manager.yml@main", False,
    ),
    ("pytorch_lint.yml", "get-label-type"): (
        "pytorch/pytorch/.github/workflows/_runner-determinator.yml@main", True,
    ),
    ("pytorch_lint.yml", "get-changed-files"): ("./.github/workflows/_get-changed-files.yml", True),
    ("pytorch_lint.yml", "lintrunner-clang"): ("./.github/workflows/_lint.yml", True),
    ("pytorch_lint.yml", "lintrunner-pyrefly"): ("./.github/workflows/_lint.yml", True),
    ("pytorch_lint.yml", "lintrunner-noclang"): ("./.github/workflows/_lint.yml", True),
    ("pytorch_lint.yml", "quick-checks"): ("./.github/workflows/_lint.yml", True),
    ("pytorch_lint.yml", "workflow-checks"): ("./.github/workflows/_lint.yml", True),
    ("pytorch_lint.yml", "toc"): ("./.github/workflows/_lint.yml", True),
    ("pytorch_lint.yml", "test-tools"): ("./.github/workflows/_lint.yml", True),
    ("pytorch_lint.yml", "link-check"): ("./.github/workflows/_link_check.yml", True),
}


@pytest.mark.parametrize(
    "filename,job_key,expected", [
        (filename, job_key, expected)
        for (filename, job_key), expected in EXPECTED_JOB_RAW_EXTRAS.items()
    ],
)
def test_calling_job_raw_extras_preserve_uses_and_with(filename, job_key, expected):
    expected_uses, expects_with = expected
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    job = next(j for j in pipeline.jobs if j.name == job_key)
    assert job.raw_extras["uses"] == expected_uses
    assert ("with" in job.raw_extras) == expects_with
    assert "secrets" not in job.raw_extras  # none of the 11 real uses:-jobs has secrets:


def test_regular_step_based_jobs_never_get_uses_or_linked_workflow_entry():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "fastapi_test.yml"))
    assert pipeline.linked_workflows == []
    for job in pipeline.jobs:
        assert "uses" not in job.raw_extras


# ---------------------------------------------------------------------------
# Mechanisms none of the 10 fixtures exercise, tested directly via
# _parse_linked_workflows against hand-written snippets.
# ---------------------------------------------------------------------------

def test_workflow_run_trigger_produces_triggered_by_linked_workflow():
    on_block = yaml.load(
        "on:\n"
        "  workflow_run:\n"
        "    workflows: [Build]\n"
        "    types: [completed]\n",
        Loader=_GitHubActionsSafeLoader,
    )["on"]
    triggers = _parse_triggers(on_block)
    linked = _parse_linked_workflows({}, triggers)
    assert linked == [LinkedWorkflow(target="Build", relationship="triggered_by")]


def test_workflow_call_trigger_produces_no_linked_workflow_entry():
    on_block = yaml.load(
        "on:\n"
        "  workflow_call:\n"
        "    inputs:\n"
        "      release_tag:\n"
        "        required: true\n"
        "        type: string\n",
        Loader=_GitHubActionsSafeLoader,
    )["on"]
    triggers = _parse_triggers(on_block)
    linked = _parse_linked_workflows({}, triggers)
    assert linked == []


def test_two_jobs_calling_identical_target_dedup_to_one_entry():
    snippet = (
        "jobs:\n"
        "  first:\n"
        "    uses: ./.github/workflows/shared.yml\n"
        "  second:\n"
        "    uses: ./.github/workflows/shared.yml\n"
    )
    data = yaml.load(snippet, Loader=_GitHubActionsSafeLoader)
    linked = _parse_linked_workflows(data, [])
    assert linked == [LinkedWorkflow(target="./.github/workflows/shared.yml", relationship="calls")]


def test_job_level_uses_with_secrets_captured_in_raw_extras():
    snippet = (
        "jobs:\n"
        "  call-other:\n"
        "    uses: ./.github/workflows/other.yml\n"
        "    secrets: inherit\n"
    )
    jobs_block = yaml.load(snippet, Loader=_GitHubActionsSafeLoader)["jobs"]
    jobs = _parse_jobs(jobs_block)
    assert jobs[0].raw_extras["secrets"] == "inherit"


def test_non_string_uses_is_skipped():
    linked = _parse_linked_workflows({"jobs": {"weird": {"uses": {"nested": True}}}}, [])
    assert linked == []


def test_empty_data_and_no_triggers_returns_empty_list():
    assert _parse_linked_workflows({}, []) == []


# ---------------------------------------------------------------------------
# Validation integration: first real exercise of ir.validate's
# _check_linked_workflows against actual parser output.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_path", ALL_FIXTURES)
def test_fixture_linked_workflows_produce_no_validation_warnings(fixture_path):
    pipeline = GitHubActionsParser().parse(fixture_path)
    issues = validate_pipeline(pipeline)
    lw_issues = [i for i in issues if i.field.startswith("linked_workflows")]
    assert lw_issues == [], f"{fixture_path}: unexpected linked_workflows warnings: {lw_issues}"
