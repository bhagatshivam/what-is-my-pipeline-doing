"""
Tests for the `Pipeline.raw_extras`/`Job.raw_extras` wiring fix in
parsers/github_actions.py: workflow-level `permissions:`/`concurrency:`/
`defaults:` (see `_parse_pipeline_raw_extras`) and job-level
`permissions:`/`outputs:`/`concurrency:`/deployment `environment:` (see
the raw_extras block in `_parse_jobs`).

Fixes the gap documented in LIMITATIONS.md's "Consciously unmodeled
concepts" section: `GitHubActionsParser.parse()` previously never passed
`raw_extras=` at all, so `Pipeline.raw_extras` was unconditionally `{}`
regardless of what workflow-level YAML existed. Covers all 10 real
fixtures' actual usage of these concepts (no synthetic snippets, since
real data already exercises every shape that matters, including the
bare-string and empty-mapping forms of `permissions:`).
"""

import os

from parsers.github_actions import GitHubActionsParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _parse(filename):
    return GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))


# ---------------------------------------------------------------------------
# Workflow-level: permissions:/concurrency:/defaults: -> Pipeline.raw_extras
# ---------------------------------------------------------------------------

def test_workflow_permissions_mapping_form_preserved():
    pipeline = _parse("rust_ci.yml")
    assert pipeline.raw_extras["permissions"] == {"contents": "read", "packages": "write"}


def test_workflow_permissions_bare_string_form_preserved():
    # pytorch_lint.yml's `permissions: read-all` — a bare string, not a
    # mapping, a distinct YAML shape from the other 7 fixtures that use it.
    pipeline = _parse("pytorch_lint.yml")
    assert pipeline.raw_extras["permissions"] == "read-all"


def test_workflow_permissions_empty_mapping_form_preserved():
    # flask_tests.yml's `permissions: {}` — an explicit "no permissions
    # granted", not the same as permissions: being absent entirely. Proves
    # the capture is presence-checked, not truthiness-checked.
    pipeline = _parse("flask_tests.yml")
    assert "permissions" in pipeline.raw_extras
    assert pipeline.raw_extras["permissions"] == {}


def test_workflow_concurrency_preserved():
    pipeline = _parse("flask_tests.yml")
    assert pipeline.raw_extras["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}",
        "cancel-in-progress": True,
    }


def test_workflow_defaults_preserved():
    pipeline = _parse("rust_ci.yml")
    assert pipeline.raw_extras["defaults"] == {"run": {"shell": "bash"}}


def test_workflow_raw_extras_absent_keys_not_present():
    # checkout_check_dist.yml has none of permissions:/concurrency:/defaults:
    # at workflow level — raw_extras should stay empty, not fabricate keys.
    pipeline = _parse("checkout_check_dist.yml")
    assert pipeline.raw_extras == {}


def test_non_mapping_jobs_value_preserved(tmp_path):
    workflow = tmp_path / "malformed-jobs.yml"
    workflow.write_text("name: malformed\non: push\njobs:\n  - build\n", encoding="utf-8")

    pipeline = GitHubActionsParser().parse(str(workflow))

    assert pipeline.raw_extras["unrecognized_jobs"] == ["build"]
    assert pipeline.jobs == []


# ---------------------------------------------------------------------------
# Job-level: permissions:/outputs:/concurrency:/environment: -> Job.raw_extras
# ---------------------------------------------------------------------------

def test_job_permissions_preserved():
    pipeline = _parse("fastapi_test.yml")
    job = next(j for j in pipeline.jobs if j.name == "changes")
    assert job.raw_extras["permissions"] == {"pull-requests": "read"}


def test_job_outputs_preserved_single():
    pipeline = _parse("fastapi_test.yml")
    job = next(j for j in pipeline.jobs if j.name == "changes")
    assert job.raw_extras["outputs"] == {"src": "${{ steps.filter.outputs.src }}"}


def test_job_outputs_preserved_multiple():
    pipeline = _parse("rust_ci.yml")
    job = next(j for j in pipeline.jobs if j.name == "calculate_matrix")
    assert job.raw_extras["outputs"] == {
        "jobs": "${{ steps.jobs.outputs.jobs }}",
        "run_type": "${{ steps.jobs.outputs.run_type }}",
    }


def test_job_concurrency_preserved():
    pipeline = _parse("pandas_unit_tests.yml")
    job = next(j for j in pipeline.jobs if j.name == "ubuntu")
    assert job.raw_extras["concurrency"]["cancel-in-progress"] is True
    assert "group" in job.raw_extras["concurrency"]


def test_job_deployment_environment_preserved_and_does_not_collide_with_env_vars():
    pipeline = _parse("rust_ci.yml")
    job = next(j for j in pipeline.jobs if j.name == "job")

    # The deployment environment: (protection-rules kind) is preserved
    # under its own distinctly named key...
    assert job.raw_extras["deployment_environment"] == (
        "${{ ((github.repository == 'rust-lang/rust' && "
        "(github.ref == 'refs/heads/try-perf' || "
        "github.ref == 'refs/heads/automation/bors/try' || "
        "github.ref == 'refs/heads/automation/bors/auto')) && 'bors') || '' }}"
    )
    # ...and is a completely different thing from Job.environment (env
    # vars, from env:), which this same job also has real data for. Both
    # must be present and neither may have clobbered the other.
    assert job.environment["CI_JOB_NAME"] == "${{ matrix.name }}"
    assert "deployment_environment" not in job.environment
    assert "CI_JOB_NAME" not in job.raw_extras


def test_job_deployment_environment_on_second_job_with_no_env_vars():
    # outcome has deployment environment: but no env: block at all — proves
    # the capture doesn't depend on Job.environment being non-empty.
    pipeline = _parse("rust_ci.yml")
    job = next(j for j in pipeline.jobs if j.name == "outcome")
    assert job.raw_extras["deployment_environment"] == (
        "${{ (github.repository == 'rust-lang/rust' && 'bors') || '' }}"
    )
    assert job.environment == {}


def test_non_mapping_job_body_preserved(tmp_path):
    workflow = tmp_path / "malformed-job-body.yml"
    workflow.write_text("name: malformed\non: push\njobs:\n  build: run-this\n", encoding="utf-8")

    pipeline = GitHubActionsParser().parse(str(workflow))

    assert pipeline.jobs[0].name == "build"
    assert pipeline.jobs[0].raw_extras["unrecognized_job"] == "run-this"
