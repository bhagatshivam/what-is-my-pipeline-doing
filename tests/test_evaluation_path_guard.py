"""
Tests for evaluation/_path_guard.py: confirms Tier 1/2 evaluation code
refuses to run against evaluation/held_out_workflows/. Deliberately never
opens or reads any held-out file body -- checking that a ValueError is
raised needs no read of the file's contents.
"""

import os

import pytest

from evaluation._path_guard import HELD_OUT_ROOT, assert_not_held_out
from evaluation.error_injection.run_checks import run_one

_HELD_OUT_FILE = os.path.join(str(HELD_OUT_ROOT), "requests_lint.yml")
_FIXTURE_FILE = os.path.join(
    os.path.dirname(__file__), "fixtures", "checkout_check_dist.yml"
)


def test_raises_for_held_out_directory_itself():
    with pytest.raises(ValueError):
        assert_not_held_out(str(HELD_OUT_ROOT))


def test_raises_for_file_inside_held_out_directory():
    with pytest.raises(ValueError):
        assert_not_held_out(_HELD_OUT_FILE)


def test_raises_for_relative_path_resolving_into_held_out_directory():
    relative = os.path.join(
        os.path.dirname(__file__), "..", "evaluation", "held_out_workflows", "scipy_linux.yml"
    )
    with pytest.raises(ValueError):
        assert_not_held_out(relative)


def test_does_not_raise_for_tests_fixtures_path():
    assert_not_held_out(_FIXTURE_FILE)  # should not raise


def test_does_not_raise_for_evaluation_error_injection_path():
    eval_dir = os.path.join(os.path.dirname(__file__), "..", "evaluation", "error_injection")
    assert_not_held_out(os.path.join(eval_dir, "dangling_dependency.yml"))  # should not raise


def test_run_one_refuses_held_out_path(tmp_path):
    with pytest.raises(ValueError):
        run_one(_HELD_OUT_FILE, str(tmp_path))
