"""
Tests for workflow-/job-level `permissions:`/`concurrency:`/`defaults:`/
`outputs:`/deployment `environment:` handling in parsers/github_actions.py.

Originally this covered the `Pipeline.raw_extras`/`Job.raw_extras` wiring
fix (`GitHubActionsParser.parse()` previously never passed `raw_extras=` at
all, so `Pipeline.raw_extras` was unconditionally `{}`). As of 2026-07-22,
`permissions`/`concurrency`/`deployment_environment` were promoted to typed
`Pipeline`/`Job` fields (see `_parse_permissions`/`_parse_concurrency`) —
those tests below now assert on the typed fields, plus assert the
corresponding raw_extras key is *absent*, proving promotion rather than
duplication. `defaults`/`outputs` have no dedicated typed field and remain
raw_extras-only by design, unchanged. Real-fixture tests cover every shape
that matters (bare-string and empty-mapping forms of `permissions:`
included); the unrecognized-shape raw_extras fallback path isn't exercised
by any real fixture, so it's covered by synthetic `tmp_path` YAML instead.
"""

import os

from parsers.github_actions import GitHubActionsParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _parse(filename):
    return GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))


# ---------------------------------------------------------------------------
# Workflow-level: permissions:/concurrency: -> typed Pipeline fields;
# defaults: -> Pipeline.raw_extras (no dedicated field, unchanged)
# ---------------------------------------------------------------------------

def test_workflow_permissions_mapping_form_preserved():
    pipeline = _parse("rust_ci.yml")
    assert pipeline.permissions == {"contents": "read", "packages": "write"}
    assert "permissions" not in pipeline.raw_extras


def test_workflow_permissions_bare_string_form_preserved():
    # pytorch_lint.yml's `permissions: read-all` — a bare string, not a
    # mapping, a distinct YAML shape from the other 7 fixtures that use it.
    pipeline = _parse("pytorch_lint.yml")
    assert pipeline.permissions == "read-all"
    assert "permissions" not in pipeline.raw_extras


def test_workflow_permissions_empty_mapping_form_preserved():
    # flask_tests.yml's `permissions: {}` — an explicit "no permissions
    # granted", not the same as permissions: being absent entirely (absent
    # would leave pipeline.permissions as None, not {}). Proves the typed
    # field is populated from a presence check, not a truthiness check.
    pipeline = _parse("flask_tests.yml")
    assert pipeline.permissions is not None
    assert pipeline.permissions == {}
    assert "permissions" not in pipeline.raw_extras


def test_workflow_concurrency_preserved():
    pipeline = _parse("flask_tests.yml")
    assert pipeline.concurrency == {
        "group": "${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}",
        "cancel-in-progress": True,
    }
    assert "concurrency" not in pipeline.raw_extras


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
# Job-level: permissions:/concurrency:/environment: -> typed Job fields;
# outputs: -> Job.raw_extras (no dedicated field, unchanged)
# ---------------------------------------------------------------------------

def test_job_permissions_preserved():
    pipeline = _parse("fastapi_test.yml")
    job = next(j for j in pipeline.jobs if j.name == "changes")
    assert job.permissions == {"pull-requests": "read"}
    assert "permissions" not in job.raw_extras


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
    assert job.concurrency["cancel-in-progress"] is True
    assert "group" in job.concurrency
    assert "concurrency" not in job.raw_extras


def test_job_deployment_environment_preserved_and_does_not_collide_with_env_vars():
    pipeline = _parse("rust_ci.yml")
    job = next(j for j in pipeline.jobs if j.name == "job")

    # The deployment environment: (protection-rules kind) is now a typed
    # field, distinct from raw_extras...
    assert job.deployment_environment == (
        "${{ ((github.repository == 'rust-lang/rust' && "
        "(github.ref == 'refs/heads/try-perf' || "
        "github.ref == 'refs/heads/automation/bors/try' || "
        "github.ref == 'refs/heads/automation/bors/auto')) && 'bors') || '' }}"
    )
    assert "deployment_environment" not in job.raw_extras
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
    assert job.deployment_environment == (
        "${{ (github.repository == 'rust-lang/rust' && 'bors') || '' }}"
    )
    assert job.environment == {}


# ---------------------------------------------------------------------------
# Unrecognized-shape fallback: no real fixture exercises these paths, so
# synthetic YAML proves the typed fields degrade to raw_extras rather than
# guessing at a shape never seen in real data.
# ---------------------------------------------------------------------------

def test_workflow_permissions_unrecognized_shape_falls_back_to_raw_extras(tmp_path):
    workflow = tmp_path / "permissions-list.yml"
    workflow.write_text(
        "name: malformed\non: push\npermissions:\n  - contents\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )

    pipeline = GitHubActionsParser().parse(str(workflow))

    assert pipeline.permissions is None
    assert pipeline.raw_extras["permissions"] == ["contents"]


def test_workflow_concurrency_bare_string_shorthand_falls_back_to_raw_extras(tmp_path):
    # GH Actions allows `concurrency: group-name` as shorthand for
    # `concurrency: {group: group-name}`, but no fixture uses it — untyped,
    # falls back rather than being guessed at.
    workflow = tmp_path / "concurrency-string.yml"
    workflow.write_text(
        "name: malformed\non: push\nconcurrency: my-group\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )

    pipeline = GitHubActionsParser().parse(str(workflow))

    assert pipeline.concurrency is None
    assert pipeline.raw_extras["concurrency"] == "my-group"


def test_job_deployment_environment_mapping_form_falls_back_to_raw_extras(tmp_path):
    # The extended {name, url} form is valid GH Actions syntax, but no
    # fixture uses it — collapsing it to one string would mean arbitrarily
    # picking name over url, so it falls back instead.
    workflow = tmp_path / "environment-mapping.yml"
    workflow.write_text(
        "name: malformed\non: push\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n"
        "    environment:\n      name: production\n      url: https://example.com\n",
        encoding="utf-8",
    )

    pipeline = GitHubActionsParser().parse(str(workflow))
    job = pipeline.jobs[0]

    assert job.deployment_environment is None
    assert job.raw_extras["deployment_environment"] == {
        "name": "production",
        "url": "https://example.com",
    }


def test_non_mapping_job_body_preserved(tmp_path):
    workflow = tmp_path / "malformed-job-body.yml"
    workflow.write_text("name: malformed\non: push\njobs:\n  build: run-this\n", encoding="utf-8")

    pipeline = GitHubActionsParser().parse(str(workflow))

    assert pipeline.jobs[0].name == "build"
    assert pipeline.jobs[0].raw_extras["unrecognized_job"] == "run-this"
