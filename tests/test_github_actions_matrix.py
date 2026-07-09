"""
Tests for the seventh slice of parsers/github_actions.py: `strategy.matrix`
(Job.matrix) via ir/schema.py's MatrixStrategy dataclass. This is the last
field before reusable workflows in BUILD_PLAN.md's ordering.

Covers all 10 real-world fixtures (every job's MatrixStrategy — axes/
include/exclude/fail_fast — checked against manual/scripted inspection of
each file) plus the shapes no fixture happens to exercise end-to-end
(a dynamic exclude:, max-parallel:, missing strategy: entirely).
"""

import os

import pytest

from ir.schema import MatrixStrategy
from ir.validate import is_valid, validate_pipeline
from parsers.github_actions import (
    GitHubActionsParser,
    _parse_matrix,
    _parse_matrix_combinations,
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
# 24 of 60 jobs across 9 of 10 fixtures have a strategy.matrix block (only
# checkout_check_dist.yml has none). 6 jobs use include:, 3 of them with
# zero declared axes (flask_tests.yml/tests, pytorch_lint.yml/
# test_collect_env, rust_ci.yml/job). 2 real jobs have include entries
# referencing axis names not in their own declared axes (fastapi_test.yml/
# test: 7 entries, pandas_unit_tests.yml/ubuntu: 10 entries). 1 job uses
# exclude: (setup_python_test.yml, keys match declared axes). fail-fast: is
# always a sibling of matrix: under strategy:, literal in 16 job-instances,
# except rust_ci.yml/job where it's a dynamic expression. rust_ci.yml/job
# also has a dynamic include: (fromJSON(...)) — the only dynamic matrix
# across all 10 fixtures. No fixture uses max-parallel:.
#
# ir.validate._check_matrix_structures produces exactly 20 warnings across
# 5 jobs in 5 distinct fixtures (verified by running validate_pipeline()
# directly, not just predicted): 3 "no axes defined" (flask_tests.yml,
# pytorch_lint.yml, rust_ci.yml) + 7 "include references unknown axes"
# (fastapi_test.yml) + 10 (pandas_unit_tests.yml). All warning-severity —
# is_valid() stays True for all 10 fixtures regardless.
# ---------------------------------------------------------------------------

# (filename, job_key) -> expected MatrixStrategy. Jobs not listed have
# job.matrix is None.
EXPECTED_JOB_MATRIX = {
    ("eslint_ci.yml", "test_on_node"): MatrixStrategy(
        axes={
            "os": ["ubuntu-latest"],
            "node": ["26.x", "24.x", "22.x", "20.x", "20.19.0"],
            "NODE_OPTIONS": [""],
        },
        include=[
            {"os": "windows-latest", "node": "lts/*"},
            {"os": "macOS-latest", "node": "lts/*"},
            {"os": "ubuntu-latest", "node": "24.x", "NODE_OPTIONS": "--experimental-transform-types"},
        ],
        exclude=[],
        fail_fast=None,
    ),
    ("fastapi_test.yml", "test"): MatrixStrategy(
        axes={
            "os": ["windows-latest", "macos-latest"],
            "python-version": ["3.14", "3.14t"],
            "deprecated-tests": ["no-deprecation"],
            "uv-resolution": ["highest"],
            "starlette-src": ["starlette-pypi", "starlette-git"],
        },
        include=[
            {"os": "macos-latest", "python-version": "3.10", "coverage": "coverage",
             "uv-resolution": "lowest-direct", "deprecated-tests": "no-deprecation"},
            {"os": "windows-latest", "python-version": "3.12", "coverage": "coverage",
             "uv-resolution": "lowest-direct", "deprecated-tests": "no-deprecation"},
            {"os": "ubuntu-latest", "python-version": "3.13", "coverage": "coverage",
             "uv-resolution": "highest", "deprecated-tests": "no-deprecation"},
            {"os": "ubuntu-latest", "python-version": "3.13", "uv-resolution": "highest",
             "codspeed": "codspeed", "deprecated-tests": "no-deprecation"},
            {"os": "ubuntu-latest", "python-version": "3.13", "uv-resolution": "highest",
             "deprecated-tests": "no-deprecation", "without-httpx2": True},
            {"os": "ubuntu-latest", "python-version": "3.14", "coverage": "coverage",
             "uv-resolution": "highest", "starlette-src": "starlette-git",
             "deprecated-tests": "test-deprecation"},
            {"os": "ubuntu-latest", "python-version": "3.14t", "coverage": "coverage",
             "uv-resolution": "highest", "deprecated-tests": "no-deprecation"},
        ],
        exclude=[],
        fail_fast=False,
    ),
    ("flask_tests.yml", "tests"): MatrixStrategy(
        axes={},
        include=[
            {"python": "3.14"},
            {"python": "3.14t"},
            {"name": "Windows", "python": "3.14", "os": "windows-latest"},
            {"name": "Mac", "python": "3.14", "os": "macos-latest"},
            {"python": "3.13"},
            {"python": "3.12"},
            {"python": "3.11"},
            {"python": "3.10"},
            {"name": "PyPy", "python": "pypy-3.11", "tox": "pypy3.11"},
            {"name": "Minimum Versions", "python": "3.14", "tox": "tests-min"},
            {"name": "Development Versions", "python": "3.10", "tox": "tests-dev"},
        ],
        exclude=[],
        fail_fast=False,
    ),
    ("node_test_linux.yml", "test-linux"): MatrixStrategy(
        axes={"os": ["ubuntu-24.04", "ubuntu-24.04-arm"]},
        include=[], exclude=[], fail_fast=False,
    ),
    ("pandas_unit_tests.yml", "ubuntu"): MatrixStrategy(
        axes={
            "platform": ["ubuntu-24.04", "ubuntu-24.04-arm"],
            "environment": ["py311", "py312", "py313", "py314"],
            "pytest_marker_expression": [""],
            "pandas_future_infer_string": ["1"],
            "pandas_future_python_scalars": ["0"],
        },
        include=[
            {"name": "Downstream Compat", "environment": "downstream",
             "pytest_marker_expression": "not slow and not network and not single_cpu",
             "pytest_target": "pandas/tests/test_downstream.py", "platform": "ubuntu-24.04"},
            {"name": "Minimum Versions", "environment": "minimum-versions",
             "pytest_marker_expression": "not slow and not network and not single_cpu",
             "platform": "ubuntu-24.04"},
            {"name": "Freethreading", "environment": "py313-freethreading",
             "pytest_marker_expression": "not slow and not network and not single_cpu",
             "platform": "ubuntu-24.04"},
            {"name": "Without PyArrow", "environment": "no-pyarrow",
             "pytest_marker_expression": "not slow and not network and not single_cpu",
             "platform": "ubuntu-24.04"},
            {"name": "Locale: it_IT", "environment": "py313",
             "pytest_marker_expression": "not slow and not network and not single_cpu",
             "extra_apt": "language-pack-it", "lang": "it_IT.utf8", "lc_all": "it_IT.utf8",
             "extra_loc": "it_IT", "platform": "ubuntu-24.04"},
            {"name": "Locale: zh_CN", "environment": "py313",
             "pytest_marker_expression": "not slow and not network and not single_cpu",
             "extra_apt": "language-pack-zh-hans", "lang": "zh_CN.utf8", "lc_all": "zh_CN.utf8",
             "extra_loc": "zh_CN", "platform": "ubuntu-24.04"},
            {"name": "PANDAS_FUTURE_INFER_STRING=0", "environment": "py313",
             "pandas_future_infer_string": "0", "platform": "ubuntu-24.04"},
            {"name": "PANDAS_FUTURE_PYTHON_SCALARS=1", "environment": "py313",
             "pandas_future_python_scalars": "1", "platform": "ubuntu-24.04"},
            {"name": "Numpy Nightly", "environment": "numpy-nightly",
             "pytest_marker_expression": "not slow and not network and not single_cpu",
             "platform": "ubuntu-24.04"},
            {"name": "Pyarrow Nightly", "environment": "pyarrow-nightly",
             "pytest_marker_expression": "not slow and not network and not single_cpu",
             "platform": "ubuntu-24.04"},
        ],
        exclude=[],
        fail_fast=False,
    ),
    ("pandas_unit_tests.yml", "macos-windows"): MatrixStrategy(
        axes={
            "os": ["macos-15-intel", "macos-15", "windows-2025"],
            "environment": ["py311", "py312", "py313", "py314"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("pandas_unit_tests.yml", "python-dev"): MatrixStrategy(
        axes={"os": ["ubuntu-24.04", "macos-15-intel", "macos-15", "windows-2025"]},
        include=[], exclude=[], fail_fast=False,
    ),
    ("pytorch_lint.yml", "test_collect_env"): MatrixStrategy(
        axes={},
        include=[
            {"test_type": "with_torch", "runner": "linux.24_04.4x"},
            {"test_type": "without_torch", "runner": "linux.24_04.4x"},
            {"test_type": "older_python_version", "runner": "linux.24_04.4x"},
        ],
        exclude=[], fail_fast=None,
    ),
    ("rust_ci.yml", "job"): MatrixStrategy(
        axes={}, include=[], exclude=[], fail_fast=None,
    ),
    ("setup_python_test.yml", "setup-versions-from-manifest"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "macos-15-intel", "ubuntu-latest", "ubuntu-24.04-arm"],
            "python": ["3.9.13", "3.10.11", "3.11.9", "3.12.3", "3.13.2"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-versions-from-file"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "macos-15-intel", "ubuntu-latest", "ubuntu-24.04-arm"],
            "python": ["3.9.13", "3.10.11", "3.11.9", "3.12.3", "3.13.2"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-versions-from-file-without-parameter"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "macos-15-intel", "ubuntu-latest", "ubuntu-24.04-arm"],
            "python": ["3.9.13", "3.10.11", "3.11.9", "3.12.3", "3.13.2"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-versions-from-standard-pyproject-file"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "macos-15-intel", "ubuntu-latest", "ubuntu-24.04-arm"],
            "python": ["3.9.13", "3.10.11", "3.11.9", "==3.12.3", "3.13.2"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-versions-from-poetry-pyproject-file"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "macos-15-intel", "ubuntu-latest", "ubuntu-24.04-arm"],
            "python": ["3.9.13", "3.10.11", "3.11.9", "3.12.3", "3.13.2"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-versions-from-tool-versions-file"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "macos-15-intel", "ubuntu-latest", "ubuntu-24.04-arm"],
            "python": ["pypy3.11-7.3.18", "graalpy-24.1.2", "3.13.2", "3.14-dev"],
        },
        include=[],
        exclude=[{"os": "windows-latest", "python": "graalpy-24.1.2"}],
        fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-versions-from-pipfile-with-python_version"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "macos-15-intel", "ubuntu-latest", "ubuntu-24.04-arm"],
            "python": ["3.9.13", "3.10.11", "3.11.9", "3.13.2"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-versions-from-pipfile-with-python_full_version"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "macos-15-intel", "ubuntu-latest", "ubuntu-24.04-arm"],
            "python": ["3.9.13", "3.10.11", "3.11.9", "3.13.2"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-pre-release-version-from-manifest"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "macos-15-intel", "ubuntu-latest", "ubuntu-24.04-arm"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-dev-version"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "ubuntu-24.04-arm", "ubuntu-latest", "macos-15-intel"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-prerelease-version"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "ubuntu-24.04-arm", "ubuntu-latest", "macos-15-intel"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-versions-noenv"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "macos-15-intel", "ubuntu-latest", "ubuntu-24.04-arm"],
            "python": ["3.9", "3.10", "3.11", "3.12", "3.13"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "check-latest"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "ubuntu-24.04-arm", "ubuntu-latest", "macos-15-intel"],
            "python-version": ["3.9", "3.10", "3.11", "3.12", "3.13"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("setup_python_test.yml", "setup-python-multiple-python-versions"): MatrixStrategy(
        axes={
            "os": ["macos-latest", "windows-latest", "ubuntu-22.04", "ubuntu-22.04-arm",
                   "ubuntu-24.04-arm", "ubuntu-latest", "macos-15-intel"],
        },
        include=[], exclude=[], fail_fast=False,
    ),
    ("upload_artifact_test.yml", "build"): MatrixStrategy(
        axes={"runs-on": ["ubuntu-latest", "macos-latest", "windows-latest"]},
        include=[], exclude=[], fail_fast=False,
    ),
}

# filename -> expected count of matrix-related validate_pipeline() warnings.
EXPECTED_MATRIX_WARNING_COUNTS = {
    "checkout_check_dist.yml": 0,
    "eslint_ci.yml": 0,
    "fastapi_test.yml": 7,
    "flask_tests.yml": 1,
    "node_test_linux.yml": 0,
    "pandas_unit_tests.yml": 10,
    "pytorch_lint.yml": 1,
    "rust_ci.yml": 1,
    "setup_python_test.yml": 0,
    "upload_artifact_test.yml": 0,
}


# ---------------------------------------------------------------------------
# Per-fixture assertions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_fixture_job_matrix(filename):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    for job in pipeline.jobs:
        expected = EXPECTED_JOB_MATRIX.get((filename, job.name))
        assert job.matrix == expected


def test_expected_job_matrix_count_matches_inspection():
    assert len(EXPECTED_JOB_MATRIX) == 24


def test_rust_ci_dynamic_matrix_preserved_in_raw_extras():
    # rust_ci.yml's `job`: matrix.include and strategy.fail-fast are both
    # dynamic expressions (fromJSON(...) / needs.*.outputs.*), not literal
    # values — can't be resolved statically, preserved instead of dropped.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "rust_ci.yml"))
    job = next(j for j in pipeline.jobs if j.name == "job")
    assert job.matrix == MatrixStrategy(axes={}, include=[], exclude=[], fail_fast=None)
    assert job.raw_extras["matrix_include_expression"] == "${{ fromJSON(needs.calculate_matrix.outputs.jobs) }}"
    assert job.raw_extras["matrix_fail_fast_expression"] == "${{ needs.calculate_matrix.outputs.run_type != 'try' }}"


@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_fixture_matrix_validation_warnings(filename):
    # First pass where validate.py's _check_matrix_structures is exercised
    # against real data — asserts the exact known-non-clean reality (20
    # warnings across 5 fixtures), not blanket cleanliness.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    issues = validate_pipeline(pipeline)
    errors = [i for i in issues if i.severity == "error"]
    matrix_warnings = [i for i in issues if i.severity == "warning" and "matrix" in i.field.lower()]
    assert errors == []
    assert len(matrix_warnings) == EXPECTED_MATRIX_WARNING_COUNTS[filename]
    assert is_valid(pipeline) is True


def test_total_matrix_warnings_across_all_fixtures():
    assert sum(EXPECTED_MATRIX_WARNING_COUNTS.values()) == 20


# ---------------------------------------------------------------------------
# `_parse_matrix_combinations` shapes, tested directly.
# ---------------------------------------------------------------------------

def test_parse_matrix_combinations_missing():
    assert _parse_matrix_combinations(None) == ([], None)


def test_parse_matrix_combinations_list():
    entries, expr = _parse_matrix_combinations([{"os": "ubuntu-latest"}, {"os": "windows-latest"}])
    assert entries == [{"os": "ubuntu-latest"}, {"os": "windows-latest"}]
    assert expr is None


def test_parse_matrix_combinations_dynamic_expression():
    entries, expr = _parse_matrix_combinations("${{ fromJSON(needs.build.outputs.matrix) }}")
    assert entries == []
    assert expr == "${{ fromJSON(needs.build.outputs.matrix) }}"


def test_parse_matrix_combinations_drops_non_dict_entries():
    entries, expr = _parse_matrix_combinations([{"os": "ubuntu-latest"}, "not-a-dict"])
    assert entries == [{"os": "ubuntu-latest"}]
    assert expr is None


# ---------------------------------------------------------------------------
# `_parse_matrix` shapes, tested directly.
# ---------------------------------------------------------------------------

def test_parse_matrix_missing_strategy():
    matrix, extras = _parse_matrix(None)
    assert matrix is None
    assert extras == {}


def test_parse_matrix_missing_matrix_key():
    matrix, extras = _parse_matrix({"fail-fast": True})
    assert matrix is None
    assert extras == {}


def test_parse_matrix_include_only_no_axes():
    matrix, extras = _parse_matrix({"matrix": {"include": [{"python": "3.11"}, {"python": "3.12"}]}})
    assert matrix == MatrixStrategy(
        axes={}, include=[{"python": "3.11"}, {"python": "3.12"}], exclude=[], fail_fast=None,
    )
    assert extras == {}


def test_parse_matrix_include_referencing_unknown_axis_still_parses():
    # No parser-side pre-validation — ir.validate._check_matrix_structures
    # catches this downstream, the parser just populates the data faithfully.
    matrix, extras = _parse_matrix({
        "matrix": {
            "os": ["ubuntu-latest"],
            "include": [{"os": "ubuntu-latest", "extra_flag": "on"}],
        },
    })
    assert matrix.axes == {"os": ["ubuntu-latest"]}
    assert matrix.include == [{"os": "ubuntu-latest", "extra_flag": "on"}]
    assert extras == {}


def test_parse_matrix_fail_fast_literal():
    matrix, extras = _parse_matrix({"fail-fast": False, "matrix": {"os": ["ubuntu-latest"]}})
    assert matrix.fail_fast is False
    assert extras == {}


def test_parse_matrix_fail_fast_expression_preserved():
    matrix, extras = _parse_matrix({
        "fail-fast": "${{ needs.build.outputs.run_type != 'try' }}",
        "matrix": {"os": ["ubuntu-latest"]},
    })
    assert matrix.fail_fast is None
    assert extras["matrix_fail_fast_expression"] == "${{ needs.build.outputs.run_type != 'try' }}"


def test_parse_matrix_dynamic_include_preserved():
    matrix, extras = _parse_matrix({"matrix": {"include": "${{ fromJSON(needs.build.outputs.matrix) }}"}})
    assert matrix.axes == {}
    assert matrix.include == []
    assert extras["matrix_include_expression"] == "${{ fromJSON(needs.build.outputs.matrix) }}"


def test_parse_matrix_dynamic_exclude_preserved():
    # No real fixture has this shape — untested against real data, added
    # symmetrically since include/exclude share identical structure.
    matrix, extras = _parse_matrix({
        "matrix": {"os": ["ubuntu-latest"], "exclude": "${{ fromJSON(needs.build.outputs.exclude) }}"},
    })
    assert matrix.exclude == []
    assert extras["matrix_exclude_expression"] == "${{ fromJSON(needs.build.outputs.exclude) }}"


def test_parse_matrix_max_parallel_preserved():
    # Not seen in any fixture — MatrixStrategy has no field for it.
    matrix, extras = _parse_matrix({"max-parallel": 4, "matrix": {"os": ["ubuntu-latest"]}})
    assert extras["max_parallel"] == "4"
    assert matrix.axes == {"os": ["ubuntu-latest"]}


def test_parse_matrix_boolean_axis_value_lowercased():
    matrix, _ = _parse_matrix({"matrix": {"flag": [True, False]}})
    assert matrix.axes == {"flag": ["true", "false"]}
