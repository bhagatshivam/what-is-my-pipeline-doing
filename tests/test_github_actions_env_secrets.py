"""
Tests for the fifth slice of parsers/github_actions.py: environment
variables (Job.environment/Step.environment/Pipeline.environment_variables),
secret references (Pipeline.secrets), and continue-on-error
(Step.continue_on_error/Job.allow_failure). `if:` conditions and matrix
strategy remain out of scope, see module docstring in
parsers/github_actions.py.

Covers all 10 real-world fixtures (env vars at every scope, secret
references, and continue-on-error values checked against manual/scripted
inspection of each file) plus the shapes no fixture happens to exercise
(secret dedup across scope_refs, a step-level continue-on-error expression,
job-level continue-on-error as a literal bool).
"""

import os

import pytest

from ir.schema import EnvironmentVariable, Secret, SecretScope
from ir.validate import is_valid, validate_pipeline
from parsers.github_actions import (
    GitHubActionsParser,
    _extract_secret_names,
    _parse_continue_on_error,
    _parse_env_vars,
    _parse_job_continue_on_error,
    _parse_secret_references,
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
# the project's own _GitHubActionsSafeLoader (cross-checked against two
# independent research passes during planning — all three agree exactly).
#
# Top-level env: 3 fixtures (fastapi_test.yml, node_test_linux.yml,
# rust_ci.yml). Job-level env: 6 job blocks. Step-level env: 20 step blocks
# across 7 fixtures. Secret references: 8 total, in exactly 2 fixtures
# (pandas_unit_tests.yml: 1, rust_ci.yml: 7). continue-on-error: 3
# occurrences, all in rust_ci.yml (1 job-level expression, 2 step-level
# literal `true`).
# ---------------------------------------------------------------------------

EXPECTED_PIPELINE_ENV = {
    "fastapi_test.yml": {
        "UV_NO_SYNC": "true",
        "INLINE_SNAPSHOT_DEFAULT_FLAGS": "review",
    },
    "node_test_linux.yml": {
        "PYTHON_VERSION": "3.14",
        "FLAKY_TESTS": "keep_retrying",
        "CLANG_VERSION": "19",
        "CC": "${{ (github.base_ref == 'main' || github.ref_name == 'main') && 'sccache' || '' }} clang-19",
        "CXX": "${{ (github.base_ref == 'main' || github.ref_name == 'main') && 'sccache' || '' }} clang++-19",
        "SCCACHE_GHA_ENABLED": "${{ github.base_ref == 'main' || github.ref_name == 'main' }}",
        "SCCACHE_IDLE_TIMEOUT": "0",
        "RUSTC_VERSION": "1.83",
    },
    "rust_ci.yml": {
        "TOOLSTATE_REPO": "https://github.com/rust-lang-nursery/rust-toolstate",
        "TOOLSTATE_REPO_ACCESS_TOKEN": "${{ secrets.TOOLSTATE_REPO_ACCESS_TOKEN }}",
    },
}

# (filename, job_key) -> expected Job.environment. Jobs not listed have {}.
EXPECTED_JOB_ENV = {
    ("eslint_ci.yml", "test_on_browser"): {"TERM": "xterm-256color"},
    ("fastapi_test.yml", "test"): {
        "UV_PYTHON": "${{ matrix.python-version }}",
        "UV_RESOLUTION": "${{ matrix.uv-resolution }}",
        "STARLETTE_SRC": "${{ matrix.starlette-src }}",
    },
    ("fastapi_test.yml", "benchmark"): {
        "UV_PYTHON": "3.13",
        "UV_RESOLUTION": "highest",
    },
    ("pandas_unit_tests.yml", "ubuntu"): {
        "LANG": "${{ matrix.lang || 'C.UTF-8' }}",
        "LC_ALL": "${{ matrix.lc_all || '' }}",
    },
    ("pandas_unit_tests.yml", "python-dev"): {
        "PYTEST_WORKERS": "auto",
        "PATTERN": "not slow and not network and not clipboard and not single_cpu",
        "PYTEST_TARGET": "pandas",
    },
    ("rust_ci.yml", "job"): {
        "CI_JOB_NAME": "${{ matrix.name }}",
        "CI_JOB_DOC_URL": "${{ matrix.doc_url }}",
        "GITHUB_WORKFLOW_RUN_ID": "${{ github.run_id }}",
        "GITHUB_REPOSITORY": "${{ github.repository }}",
        "CARGO_REGISTRIES_CRATES_IO_PROTOCOL": "sparse",
        "HEAD_SHA": "${{ github.event.pull_request.head.sha || github.sha }}",
        "DOCKER_TOKEN": "${{ secrets.GITHUB_TOKEN }}",
        "SCCACHE_BUCKET": "rust-lang-ci-sccache2",
        "SCCACHE_REGION": "us-west-1",
        "CACHE_DOMAIN": "ci-caches.rust-lang.org",
    },
}

# (filename, job_key, step_index) -> expected Step.environment. Steps not
# listed have {}.
EXPECTED_STEP_ENV = {
    ("eslint_ci.yml", "test_on_node", 3): {"NODE_OPTIONS": "${{ matrix.NODE_OPTIONS }}"},
    ("fastapi_test.yml", "test", 0): {"GITHUB_CONTEXT": "${{ toJson(github) }}"},
    ("fastapi_test.yml", "test", 11): {
        "COVERAGE_FILE": "coverage/.coverage.${{ runner.os }}-py${{ matrix.python-version }}-${{ matrix.deprecated-tests}}",
        "CONTEXT": "${{ runner.os }}-py${{ matrix.python-version }}-${{ matrix.deprecated-tests}}",
        "PYTEST_OPTIONS": "${{ (matrix.without-httpx2 == 'true') && '-W ignore::UserWarning' || '' }}",
    },
    ("fastapi_test.yml", "benchmark", 0): {"GITHUB_CONTEXT": "${{ toJson(github) }}"},
    ("fastapi_test.yml", "coverage-combine", 0): {"GITHUB_CONTEXT": "${{ toJson(github) }}"},
    ("fastapi_test.yml", "test-alls-green", 0): {"GITHUB_CONTEXT": "${{ toJson(github) }}"},
    ("flask_tests.yml", "tests", 3): {
        "TOX_ENV": "${{ matrix.tox || format('py{0}', matrix.python) }}",
    },
    ("node_test_linux.yml", "test-linux", 8): {
        "DIR": "dir%20with $unusual\"chars?'åß∂ƒ©∆¬…`",
    },
    ("pandas_unit_tests.yml", "ubuntu", 5): {"PANDAS_MOTO_URL": "http://localhost:5000"},
    ("pandas_unit_tests.yml", "ubuntu", 6): {"PANDAS_MOTO_URL": "http://localhost:5000"},
    ("pandas_unit_tests.yml", "Linux-Sanitizers", 4): {
        "LD_PRELOAD": "${{ env.ASAN_LIB_PATH }}",
        "ASAN_OPTIONS": "detect_leaks=0",
        "UBSAN_OPTIONS": "halt_on_error=1:suppressions=${{ github.workspace }}/ci/suppressions/ubsan.txt",
    },
    ("pytorch_lint.yml", "pr-sanity-checks", 1): {
        "BASE": "${{ github.event.pull_request.base.sha }}",
        "HEAD": "${{ github.event.pull_request.head.sha }}",
    },
    ("pytorch_lint.yml", "doc-redirects-check", 1): {
        "BASE_REF": "${{ github.event.pull_request.base.ref }}",
    },
    ("rust_ci.yml", "calculate_matrix", 2): {
        "COMMIT_MESSAGE": "${{ github.event.head_commit.message }}",
    },
    ("rust_ci.yml", "job", 5): {"num": "${{ github.event.number }}"},
    ("rust_ci.yml", "job", 6): {"EXTRA_VARIABLES": "${{ toJson(matrix.env) }}"},
    ("rust_ci.yml", "job", 26): {
        "AWS_ACCESS_KEY_ID": "${{ secrets.CACHES_AWS_ACCESS_KEY_ID }}",
        "AWS_SECRET_ACCESS_KEY": "${{ secrets.CACHES_AWS_SECRET_ACCESS_KEY }}",
    },
    ("rust_ci.yml", "job", 30): {
        "AWS_ACCESS_KEY_ID": "${{ secrets.ARTIFACTS_AWS_ACCESS_KEY_ID }}",
        "AWS_SECRET_ACCESS_KEY": "${{ secrets.ARTIFACTS_AWS_SECRET_ACCESS_KEY }}",
    },
    ("rust_ci.yml", "job", 32): {
        "DATADOG_API_KEY": "${{ secrets.DATADOG_API_KEY }}",
        "DD_GITHUB_JOB_NAME": "${{ matrix.full_name }}",
    },
    ("rust_ci.yml", "outcome", 1): {
        "TOOLSTATE_ISSUES_API_URL": "https://api.github.com/repos/rust-lang/rust/issues",
        "TOOLSTATE_PUBLISH": "1",
    },
}

# (filename, job_key, step_index) -> expected Step.continue_on_error. Steps
# not listed default to False.
EXPECTED_STEP_CONTINUE_ON_ERROR = {
    ("rust_ci.yml", "job", 31): True,
    ("rust_ci.yml", "job", 32): True,
}

# filename -> list of (name, scope, scope_ref) for Pipeline.secrets. Not
# listed -> [].
EXPECTED_SECRETS = {
    "pandas_unit_tests.yml": [
        ("CODECOV_TOKEN", SecretScope.STEP, "ubuntu.7"),
    ],
    "rust_ci.yml": [
        ("TOOLSTATE_REPO_ACCESS_TOKEN", SecretScope.PIPELINE, None),
        ("GITHUB_TOKEN", SecretScope.JOB, "job"),
        ("CACHES_AWS_ACCESS_KEY_ID", SecretScope.STEP, "job.26"),
        ("CACHES_AWS_SECRET_ACCESS_KEY", SecretScope.STEP, "job.26"),
        ("ARTIFACTS_AWS_ACCESS_KEY_ID", SecretScope.STEP, "job.30"),
        ("ARTIFACTS_AWS_SECRET_ACCESS_KEY", SecretScope.STEP, "job.30"),
        ("DATADOG_API_KEY", SecretScope.STEP, "job.32"),
    ],
}


# ---------------------------------------------------------------------------
# Per-fixture assertions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_fixture_pipeline_environment_variables(filename):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    pipeline_env = {
        e.name: e.value for e in pipeline.environment_variables if e.scope == SecretScope.PIPELINE
    }
    assert pipeline_env == EXPECTED_PIPELINE_ENV.get(filename, {})


@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_fixture_job_environment(filename):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    for job in pipeline.jobs:
        expected = EXPECTED_JOB_ENV.get((filename, job.name), {})
        assert job.environment == expected


@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_fixture_step_environment_and_continue_on_error(filename):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    for job in pipeline.jobs:
        for i, step in enumerate(job.steps):
            expected_env = EXPECTED_STEP_ENV.get((filename, job.name, i), {})
            assert step.environment == expected_env
            expected_coe = EXPECTED_STEP_CONTINUE_ON_ERROR.get((filename, job.name, i), False)
            assert step.continue_on_error == expected_coe


@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_fixture_secrets(filename):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    actual = [(s.name, s.scope, s.scope_ref) for s in pipeline.secrets]
    assert actual == EXPECTED_SECRETS.get(filename, [])


def test_rust_ci_job_level_continue_on_error_expression_preserved():
    # rust_ci.yml's `job` job: `continue-on-error: ${{ matrix.continue_on_error || false }}`
    # is an expression, not a literal bool — Job.allow_failure can't
    # faithfully represent it, so it stays at its safe default and the raw
    # expression is preserved instead of silently dropped.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "rust_ci.yml"))
    job = next(j for j in pipeline.jobs if j.name == "job")
    assert job.allow_failure is False
    assert job.raw_extras["continue_on_error_expression"] == "${{ matrix.continue_on_error || false }}"


@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_fixture_pipeline_is_valid(filename):
    # First pass where validate.py's _check_secret_and_env_scopes is
    # exercised against real multi-scope data.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    issues = validate_pipeline(pipeline)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []
    assert is_valid(pipeline) is True


# ---------------------------------------------------------------------------
# `_parse_env_vars` shapes, tested directly.
# ---------------------------------------------------------------------------

def test_parse_env_vars_missing():
    assert _parse_env_vars(None, SecretScope.PIPELINE, None) == []


def test_parse_env_vars_non_dict():
    assert _parse_env_vars(["not", "a", "dict"], SecretScope.PIPELINE, None) == []


def test_parse_env_vars_expression_value_stored_as_is():
    entries = _parse_env_vars({"SHA": "${{ github.sha }}"}, SecretScope.JOB, "build")
    assert entries == [
        EnvironmentVariable(name="SHA", value="${{ github.sha }}", scope=SecretScope.JOB, scope_ref="build")
    ]


def test_parse_env_vars_boolean_value_lowercased():
    entries = _parse_env_vars({"FLAG": True, "OTHER": False}, SecretScope.PIPELINE, None)
    assert entries[0].value == "true"
    assert entries[1].value == "false"


def test_parse_env_vars_null_value_stays_none():
    entries = _parse_env_vars({"EMPTY": None}, SecretScope.PIPELINE, None)
    assert entries[0].value is None


# ---------------------------------------------------------------------------
# Secret scanning shapes, tested directly.
# ---------------------------------------------------------------------------

def test_extract_secret_names_from_run_string():
    text = "echo ${{ secrets.MY_TOKEN }} | some-cli login"
    assert _extract_secret_names(text) == ["MY_TOKEN"]


def test_secret_reference_inside_run_string_is_caught():
    snippet = {
        "jobs": {
            "deploy": {
                "steps": [
                    {"name": "Deploy", "run": "curl -H 'Authorization: ${{ secrets.DEPLOY_TOKEN }}' https://example.com"},
                ],
            },
        },
    }
    secrets = _parse_secret_references(snippet)
    assert secrets == [Secret(name="DEPLOY_TOKEN", scope=SecretScope.STEP, scope_ref="deploy.0")]


def test_secret_reference_inside_with_arg_is_caught():
    snippet = {
        "jobs": {
            "upload": {
                "steps": [
                    {"name": "Upload", "uses": "some/action@v1", "with": {"token": "${{ secrets.UPLOAD_TOKEN }}"}},
                ],
            },
        },
    }
    secrets = _parse_secret_references(snippet)
    assert secrets == [Secret(name="UPLOAD_TOKEN", scope=SecretScope.STEP, scope_ref="upload.0")]


def test_secret_referenced_twice_in_same_scope_dedupes_to_one_entry():
    snippet = {
        "jobs": {
            "build": {
                "steps": [
                    {
                        "name": "Two refs, same step",
                        "run": "echo ${{ secrets.SAME_TOKEN }}",
                        "env": {"TOKEN": "${{ secrets.SAME_TOKEN }}"},
                    },
                ],
            },
        },
    }
    secrets = _parse_secret_references(snippet)
    assert secrets == [Secret(name="SAME_TOKEN", scope=SecretScope.STEP, scope_ref="build.0")]


def test_secret_referenced_from_two_different_jobs_stays_two_entries():
    snippet = {
        "env": {"SHARED": "${{ secrets.SHARED_TOKEN }}"},
        "jobs": {
            "job_a": {"env": {"TOKEN": "${{ secrets.SHARED_TOKEN }}"}},
            "job_b": {"env": {"TOKEN": "${{ secrets.SHARED_TOKEN }}"}},
        },
    }
    secrets = _parse_secret_references(snippet)
    assert secrets == [
        Secret(name="SHARED_TOKEN", scope=SecretScope.PIPELINE, scope_ref=None),
        Secret(name="SHARED_TOKEN", scope=SecretScope.JOB, scope_ref="job_a"),
        Secret(name="SHARED_TOKEN", scope=SecretScope.JOB, scope_ref="job_b"),
    ]


# ---------------------------------------------------------------------------
# continue-on-error shapes, tested directly.
# ---------------------------------------------------------------------------

def test_parse_continue_on_error_true():
    assert _parse_continue_on_error(True) is True


def test_parse_continue_on_error_missing_defaults_false():
    assert _parse_continue_on_error(None) is False


def test_parse_continue_on_error_expression_defaults_false():
    # LIMITATION: Step.continue_on_error is strictly bool-typed with no raw
    # fallback — an expression can't be faithfully represented.
    assert _parse_continue_on_error("${{ matrix.allow_failure }}") is False


def test_parse_job_continue_on_error_literal_bool():
    assert _parse_job_continue_on_error(True) == (True, None)
    assert _parse_job_continue_on_error(False) == (False, None)


def test_parse_job_continue_on_error_missing():
    assert _parse_job_continue_on_error(None) == (False, None)


def test_parse_job_continue_on_error_expression_preserved():
    allow_failure, expr = _parse_job_continue_on_error("${{ matrix.continue_on_error || false }}")
    assert allow_failure is False
    assert expr == "${{ matrix.continue_on_error || false }}"


def test_step_with_continue_on_error_true_end_to_end():
    snippet = {
        "jobs": {
            "flaky": {
                "steps": [
                    {"name": "Flaky test", "run": "pytest --flaky", "continue-on-error": True},
                ],
            },
        },
    }
    from parsers.github_actions import _parse_jobs

    jobs = _parse_jobs(snippet["jobs"])
    assert jobs[0].steps[0].continue_on_error is True
