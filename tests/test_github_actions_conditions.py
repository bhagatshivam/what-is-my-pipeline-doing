"""
Tests for the sixth slice of parsers/github_actions.py: `if:` conditions
(Job.condition/Step.condition) via ir/schema.py's Condition dataclass, plus
the resolution of the env/secrets pass's deferred if:-secret-scanning.
Matrix strategy remains out of scope, see module docstring in
parsers/github_actions.py.

Covers all 10 real-world fixtures (every job/step's Condition.expression
and Condition.structured checked against manual/scripted inspection of
each file) plus the shapes no fixture happens to exercise end-to-end
(event_equals, negated status checks, a secret reference inside an if:).
"""

import os

import pytest

from ir.schema import Condition, Secret, SecretScope
from ir.validate import is_valid, validate_pipeline
from parsers.github_actions import (
    GitHubActionsParser,
    _classify_condition,
    _parse_condition,
    _parse_secret_references,
    _strip_expression_wrapper,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

ALL_FIXTURES = [
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

# ---------------------------------------------------------------------------
# Ground truth, taken directly from a script run against all 10 fixtures via
# the project's own _GitHubActionsSafeLoader (cross-checked against an
# independent research pass during planning — both agree exactly).
#
# 44 total if: occurrences: 19 job-level, 25 step-level. 12 wrapped in
# ${{ }}, 32 bare. Zero contain a secret reference. Only 3 real expressions
# match a recognized structured pattern (2x bare always() -> status_check,
# 1x bare github.ref == 'X' -> ref_equals); the other 41 -> unparsed,
# including 9 github.repository_owner/github.repository equality checks
# that don't match the narrow github.ref/github.event_name pattern.
# ---------------------------------------------------------------------------

# (filename, job_key) -> expected job-level Condition. Jobs not listed have
# condition is None.
EXPECTED_JOB_CONDITIONS = {
    ("fastapi_test.yml", "test"): Condition(
        expression="needs.changes.outputs.src == 'true' || github.ref == 'refs/heads/master'",
        structured={"type": "unparsed"},
    ),
    ("fastapi_test.yml", "benchmark"): Condition(
        expression="needs.changes.outputs.src == 'true' || github.ref == 'refs/heads/master'",
        structured={"type": "unparsed"},
    ),
    ("fastapi_test.yml", "test-alls-green"): Condition(
        expression="always()",
        structured={"type": "status_check", "function": "always", "negated": False},
    ),
    ("node_test_linux.yml", "test-linux"): Condition(
        expression="github.event.pull_request.draft == false",
        structured={"type": "unparsed"},
    ),
    ("pandas_unit_tests.yml", "python-dev"): Condition(
        expression="false",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "get-label-type"): Condition(
        expression="github.repository_owner == 'pytorch'",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "get-changed-files"): Condition(
        expression="github.repository_owner == 'pytorch'",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "lintrunner-clang"): Condition(
        expression=(
            "github.repository_owner == 'pytorch' && (\n"
            "  needs.get-changed-files.outputs.changed-files == '*' ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.h') ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.cpp') ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.cc') ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.cxx') ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.hpp') ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.hxx') ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.cu') ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.cuh') ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.mm') ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.metal')\n"
            ")\n"
        ),
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "lintrunner-pyrefly"): Condition(
        expression=(
            "github.repository_owner == 'pytorch' && (\n"
            "  needs.get-changed-files.outputs.changed-files == '*' ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.py') ||\n"
            "  contains(needs.get-changed-files.outputs.changed-files, '.pyi')\n"
            ")\n"
        ),
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "quick-checks"): Condition(
        expression="github.repository_owner == 'pytorch'",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "pr-sanity-checks"): Condition(
        expression=(
            "${{ github.event_name == 'pull_request' && "
            "!contains(github.event.pull_request.labels.*.name, 'skip-pr-sanity-checks') && "
            "github.repository_owner == 'pytorch' }}"
        ),
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "workflow-checks"): Condition(
        expression="github.repository_owner == 'pytorch'",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "toc"): Condition(
        expression="github.repository_owner == 'pytorch'",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "test-tools"): Condition(
        expression="${{ github.repository == 'pytorch/pytorch' }}",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "test_run_test"): Condition(
        expression="${{ github.repository == 'pytorch/pytorch' }}",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "test_collect_env"): Condition(
        expression="${{ github.repository == 'pytorch/pytorch' }}",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "link-check"): Condition(
        expression="github.repository_owner == 'pytorch'",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "doc-redirects-check"): Condition(
        expression="github.event_name == 'pull_request' && github.repository_owner == 'pytorch'",
        structured={"type": "unparsed"},
    ),
    ("rust_ci.yml", "outcome"): Condition(
        expression="${{ needs.calculate_matrix.outputs.run_type == 'auto' }}",
        structured={"type": "unparsed"},
    ),
}

# (filename, job_key, step_index) -> expected step-level Condition. Steps
# not listed have condition is None.
EXPECTED_STEP_CONDITIONS = {
    ("checkout_check_dist.yml", "check-dist", 5): Condition(
        expression="${{ failure() && steps.diff.conclusion == 'failure' }}",
        structured={"type": "unparsed"},
    ),
    ("fastapi_test.yml", "test", 5): Condition(
        expression="matrix.uv-resolution == 'lowest-direct'",
        structured={"type": "unparsed"},
    ),
    ("fastapi_test.yml", "test", 6): Condition(
        expression="matrix.starlette-src == 'starlette-git'",
        structured={"type": "unparsed"},
    ),
    ("fastapi_test.yml", "test", 7): Condition(
        expression="matrix.deprecated-tests == 'test-deprecation'",
        structured={"type": "unparsed"},
    ),
    ("fastapi_test.yml", "test", 8): Condition(
        expression="matrix.without-httpx2 == 'true'",
        structured={"type": "unparsed"},
    ),
    ("fastapi_test.yml", "test", 9): Condition(
        expression="matrix.python-version == '3.14t' && matrix.os == 'ubuntu-latest'",
        structured={"type": "unparsed"},
    ),
    ("fastapi_test.yml", "test", 12): Condition(
        expression="matrix.coverage == 'coverage'",
        structured={"type": "unparsed"},
    ),
    ("node_test_linux.yml", "test-linux", 4): Condition(
        expression="github.base_ref == 'main' || github.ref_name == 'main'",
        structured={"type": "unparsed"},
    ),
    ("pandas_unit_tests.yml", "ubuntu", 1): Condition(
        expression="${{ matrix.extra_loc && matrix.extra_apt }}",
        structured={"type": "unparsed"},
    ),
    ("pandas_unit_tests.yml", "ubuntu", 6): Condition(
        expression="${{ matrix.pytest_marker_expression == '' && (always() && steps.build.outcome == 'success')}}",
        structured={"type": "unparsed"},
    ),
    ("pandas_unit_tests.yml", "ubuntu", 7): Condition(
        expression="${{ steps.test-not-single-cpu.outcome == 'success' && steps.test-single-cpu.outcome == 'success' }}",
        structured={"type": "unparsed"},
    ),
    ("pandas_unit_tests.yml", "macos-windows", 2): Condition(
        expression="${{ matrix.os == 'windows-2025' }}",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "test_collect_env", 1): Condition(
        expression="matrix.test_type == 'older_python_version'",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "test_collect_env", 2): Condition(
        expression="matrix.test_type == 'older_python_version'",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "test_collect_env", 3): Condition(
        expression="matrix.test_type != 'older_python_version'",
        structured={"type": "unparsed"},
    ),
    ("pytorch_lint.yml", "test_collect_env", 4): Condition(
        expression="matrix.test_type == 'with_torch'",
        structured={"type": "unparsed"},
    ),
    ("rust_ci.yml", "calculate_matrix", 1): Condition(
        expression="${{ github.ref == 'refs/heads/automation/bors/auto' }}",
        structured={"type": "ref_equals", "value": "refs/heads/automation/bors/auto"},
    ),
    ("rust_ci.yml", "job", 0): Condition(
        expression="matrix.codebuild",
        structured={"type": "unparsed"},
    ),
    ("rust_ci.yml", "job", 3): Condition(
        expression="matrix.free_disk",
        structured={"type": "unparsed"},
    ),
    ("rust_ci.yml", "job", 4): Condition(
        expression="matrix.free_disk == false",
        structured={"type": "unparsed"},
    ),
    ("rust_ci.yml", "job", 5): Condition(
        expression="needs.calculate_matrix.outputs.run_type == 'pr'",
        structured={"type": "unparsed"},
    ),
    ("rust_ci.yml", "job", 19): Condition(
        expression="${{ !matrix.codebuild }}",
        structured={"type": "unparsed"},
    ),
    ("rust_ci.yml", "job", 28): Condition(
        expression="always()",
        structured={"type": "status_check", "function": "always", "negated": False},
    ),
    ("rust_ci.yml", "job", 30): Condition(
        expression="github.event_name == 'push' || env.DEPLOY == '1' || env.DEPLOY_ALT == '1'",
        structured={"type": "unparsed"},
    ),
    ("rust_ci.yml", "job", 32): Condition(
        expression="needs.calculate_matrix.outputs.run_type != 'pr'",
        structured={"type": "unparsed"},
    ),
}


# ---------------------------------------------------------------------------
# Per-fixture assertions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_fixture_job_conditions(filename):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    for job in pipeline.jobs:
        expected = EXPECTED_JOB_CONDITIONS.get((filename, job.name))
        assert job.condition == expected


@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_fixture_step_conditions(filename):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    for job in pipeline.jobs:
        for i, step in enumerate(job.steps):
            expected = EXPECTED_STEP_CONDITIONS.get((filename, job.name, i))
            assert step.condition == expected


def test_no_real_condition_has_wrong_guess_structured():
    # All 44 real conditions across all 10 fixtures must have structured
    # equal to either a recognized shape or exactly {"type": "unparsed"} —
    # never None (once a Condition exists) and never a partial/incorrect guess.
    all_expected = list(EXPECTED_JOB_CONDITIONS.values()) + list(EXPECTED_STEP_CONDITIONS.values())
    assert len(all_expected) == 44
    for condition in all_expected:
        assert condition.structured is not None
        assert condition.structured["type"] in {"status_check", "ref_equals", "event_equals", "unparsed"}


def test_no_secret_reference_in_any_real_if_condition():
    # Confirmed by direct inspection: none of the 44 real if: expressions
    # reference a secret. This test guards that assumption rather than
    # re-deriving it.
    for condition in list(EXPECTED_JOB_CONDITIONS.values()) + list(EXPECTED_STEP_CONDITIONS.values()):
        assert "secrets." not in condition.expression


@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_fixture_pipeline_is_valid(filename):
    # First pass where validate.py's _check_conditions is exercised against
    # real data (every Condition's expression must be non-empty).
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    issues = validate_pipeline(pipeline)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []
    assert is_valid(pipeline) is True


# ---------------------------------------------------------------------------
# `_parse_condition`/`_classify_condition` shapes, tested directly.
# ---------------------------------------------------------------------------

def test_condition_missing_is_none():
    assert _parse_condition(None) is None


def test_condition_empty_string_is_none():
    assert _parse_condition("") is None
    assert _parse_condition("   ") is None


def test_condition_expression_preserves_wrapper_verbatim():
    assert _parse_condition("${{ always() }}").expression == "${{ always() }}"
    assert _parse_condition("always()").expression == "always()"


def test_condition_literal_bool_lowercased():
    assert _parse_condition(True).expression == "true"
    assert _parse_condition(False).expression == "false"


def test_condition_unexpected_shape_stringified():
    condition = _parse_condition(123)
    assert condition.expression == "123"
    assert condition.structured == {"type": "unparsed"}


def test_classify_bare_status_check():
    assert _classify_condition("always()") == {
        "type": "status_check", "function": "always", "negated": False,
    }
    assert _classify_condition("success()") == {
        "type": "status_check", "function": "success", "negated": False,
    }


def test_classify_negated_status_check():
    # No real fixture has this shape — untested against real data, per
    # LIMITATIONS.md.
    assert _classify_condition("!failure()") == {
        "type": "status_check", "function": "failure", "negated": True,
    }
    assert _classify_condition("!cancelled()") == {
        "type": "status_check", "function": "cancelled", "negated": True,
    }


def test_classify_ref_equals():
    assert _classify_condition("github.ref == 'refs/heads/main'") == {
        "type": "ref_equals", "value": "refs/heads/main",
    }


def test_classify_event_equals():
    # No real fixture has this bare (every github.event_name occurrence is
    # combined with && / || in the 10 fixtures) — snippet test per plan.
    assert _classify_condition("github.event_name == 'push'") == {
        "type": "event_equals", "value": "push",
    }


def test_classify_compound_expression_does_not_falsely_match_equals():
    # Regression test for a real bug caught in design review: a
    # non-greedy value-group regex previously let compound expressions
    # backtrack past && / || boundaries and misclassify as a clean
    # event_equals/ref_equals with a corrupted value.
    compound = "github.event_name == 'pull_request' && github.repository_owner == 'pytorch'"
    assert _classify_condition(compound) == {"type": "unparsed"}

    compound2 = "github.event_name == 'push' || env.DEPLOY == '1'"
    assert _classify_condition(compound2) == {"type": "unparsed"}


def test_classify_github_repository_owner_stays_unparsed():
    # Not github.ref / github.event_name specifically — narrow pattern set
    # intentionally doesn't recognize this, even though it's a simple bare
    # equality (9 real occurrences across pytorch_lint.yml).
    assert _classify_condition("github.repository_owner == 'pytorch'") == {"type": "unparsed"}


def test_classify_needs_outputs_stays_unparsed():
    # Meaningfully common real shape (7 occurrences) that isn't
    # structured-parsed this pass — see LIMITATIONS.md.
    assert _classify_condition("needs.calculate_matrix.outputs.run_type == 'auto'") == {"type": "unparsed"}


def test_strip_expression_wrapper():
    assert _strip_expression_wrapper("${{ always() }}") == "always()"
    assert _strip_expression_wrapper("always()") == "always()"
    assert _strip_expression_wrapper("  ${{ github.ref == 'main' }}  ") == "github.ref == 'main'"


# ---------------------------------------------------------------------------
# if:-secret-scanning wiring (resolving PR #8's deferral).
# ---------------------------------------------------------------------------

def test_secret_reference_inside_job_level_if_is_caught():
    snippet = {
        "jobs": {
            "deploy": {
                "if": "${{ secrets.DEPLOY_ENABLED == 'true' }}",
                "steps": [{"name": "Deploy", "run": "./deploy.sh"}],
            },
        },
    }
    secrets = _parse_secret_references(snippet)
    assert secrets == [Secret(name="DEPLOY_ENABLED", scope=SecretScope.JOB, scope_ref="deploy")]


def test_secret_reference_inside_step_level_if_is_caught():
    snippet = {
        "jobs": {
            "build": {
                "steps": [
                    {
                        "name": "Conditional step",
                        "run": "echo hi",
                        "if": "${{ secrets.SHOULD_RUN == 'yes' }}",
                    },
                ],
            },
        },
    }
    secrets = _parse_secret_references(snippet)
    assert secrets == [Secret(name="SHOULD_RUN", scope=SecretScope.STEP, scope_ref="build.0")]
