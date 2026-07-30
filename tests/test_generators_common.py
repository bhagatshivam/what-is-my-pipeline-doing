"""
Tests for generators/common.py's Phase 7.5 additions: the narrow,
truthful `_jobs_with_no_declared_dependencies` check (Revision 1), the
`_matrix_is_dynamic`/`_exact_combination_count` matrix helpers
(Revision 2), and the cross-module TriggerType coverage test
(Revision 3).
"""

from generators.common import (
    _exact_combination_count,
    _jobs_with_no_declared_dependencies,
    _matrix_is_dynamic,
    _matrix_summary,
    _TRIGGER_GLANCE_BUILDERS,
)
from generators.mermaid_generator import _TRIGGER_DISPLAY_NAMES
from generators.text_generator import _TRIGGER_PHRASE_BUILDERS
from ir.schema import Job, MatrixStrategy, TriggerType


# ---------------------------------------------------------------------------
# Revision 3 — all three TriggerType representations cover the same set.
# ---------------------------------------------------------------------------

_NAMED_TRIGGER_TYPES = set(TriggerType) - {TriggerType.OTHER}


def test_trigger_representations_cover_same_triggertype_set():
    # Guards against a future new TriggerType being wired into one of
    # these three dispatch tables and silently missed in the others.
    # TriggerType.OTHER is deliberately excluded from all three — its only
    # sensible rendering is dumping Trigger.raw, handled as a generic
    # fallback in each caller, not a dict key.
    assert set(_TRIGGER_DISPLAY_NAMES.keys()) == _NAMED_TRIGGER_TYPES
    assert set(_TRIGGER_PHRASE_BUILDERS.keys()) == _NAMED_TRIGGER_TYPES
    assert set(_TRIGGER_GLANCE_BUILDERS.keys()) == _NAMED_TRIGGER_TYPES


# ---------------------------------------------------------------------------
# Revision 1 — _jobs_with_no_declared_dependencies is narrow and truthful.
# ---------------------------------------------------------------------------

def _job(name, deps=()):
    return Job(name=name, dependencies=list(deps))


def test_jobs_with_no_declared_dependencies_excludes_declared_but_dangling():
    # A job with a real, if unresolvable, `needs:` reference has a
    # non-empty `dependencies` list — it must never be reported as having
    # "no dependencies", even though the diagram's separate, more lenient
    # entry-point notion would have tolerated it.
    jobs = [_job("A"), _job("B", deps=["A"]), _job("C", deps=["does-not-exist"])]
    independent = [j.name for j in _jobs_with_no_declared_dependencies(jobs)]
    assert independent == ["A"]


def test_jobs_with_no_declared_dependencies_all_independent():
    jobs = [_job("A"), _job("B")]
    assert [j.name for j in _jobs_with_no_declared_dependencies(jobs)] == ["A", "B"]


def test_jobs_with_no_declared_dependencies_none_independent():
    jobs = [_job("A", deps=["B"]), _job("B", deps=["A"])]
    assert _jobs_with_no_declared_dependencies(jobs) == []


# ---------------------------------------------------------------------------
# Revision 2 — _matrix_is_dynamic / _exact_combination_count.
# ---------------------------------------------------------------------------

def test_matrix_is_dynamic_true_only_when_no_axes_and_no_include():
    assert _matrix_is_dynamic(MatrixStrategy()) is True
    assert _matrix_is_dynamic(MatrixStrategy(include=[{"a": "1"}])) is False
    assert _matrix_is_dynamic(MatrixStrategy(axes={"os": ["a", "b"]})) is False


def test_matrix_summary_and_is_dynamic_agree_on_the_dynamic_case():
    # _matrix_summary's own dynamic branch must stay driven by
    # _matrix_is_dynamic, not a separately-maintained condition.
    dynamic = MatrixStrategy()
    assert _matrix_is_dynamic(dynamic) is True
    assert _matrix_summary(dynamic) == "combinations determined at runtime"


def test_exact_combination_count_axes_only():
    matrix = MatrixStrategy(axes={"os": ["a", "b"], "py": ["3.9", "3.10", "3.11"]})
    assert _exact_combination_count(matrix) == 6


def test_exact_combination_count_include_only_no_exclude():
    matrix = MatrixStrategy(include=[{"x": "1"}, {"x": "2"}, {"x": "3"}])
    assert _exact_combination_count(matrix) == 3


def test_exact_combination_count_none_when_dynamic():
    assert _exact_combination_count(MatrixStrategy()) is None


def test_exact_combination_count_none_when_axes_and_include_both_present():
    # _matrix_summary itself keeps these as two separate numbers ("N base
    # combinations + M via include") rather than asserting one total,
    # since include's merge-vs-append semantics against the axis product
    # aren't modelled — summing them would overclaim precision.
    matrix = MatrixStrategy(axes={"os": ["a", "b"]}, include=[{"x": "1"}])
    assert _exact_combination_count(matrix) is None


def test_exact_combination_count_none_when_any_exclude_present():
    # axes + exclude, no include.
    axes_exclude = MatrixStrategy(axes={"os": ["a", "b"]}, exclude=[{"os": "a"}])
    assert _exact_combination_count(axes_exclude) is None
    # include + exclude, no axes — _matrix_summary's "not axes" branch
    # ignores exclude in its own prose, but this helper is deliberately
    # stricter than that (see module docstring): any exclude -> None.
    include_exclude = MatrixStrategy(include=[{"x": "1"}], exclude=[{"x": "1"}])
    assert _exact_combination_count(include_exclude) is None
    # axes + include + exclude, all three present.
    all_three = MatrixStrategy(
        axes={"os": ["a", "b"]}, include=[{"x": "1"}], exclude=[{"os": "a"}]
    )
    assert _exact_combination_count(all_three) is None
