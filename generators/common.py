"""
generators.common — shared, non-LLM helpers used by more than one Layer 3
generator (`text_generator.py`, `mermaid_generator.py`).

These functions operate purely on `ir.schema` dataclasses, following the
same contract as every Layer 3 generator: no raw YAML, no network calls,
deterministic output. They live here (rather than in one generator module
with the other importing its "private" functions) so the leading
underscore on each name keeps meaning what it's supposed to mean —
private to this module, not to a specific generator.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from ir.schema import Condition, Job, MatrixStrategy, Trigger, TriggerType


def _plural(n: int, word: str) -> str:
    return word if n == 1 else word + "s"


def _and_join(items: List[str]) -> str:
    """Oxford-comma "and" join — shared by text_generator's At a glance
    trigger-summary sentence and tool2/relationships.py's relationship
    table ("Runs when" column), so both use the same conjunction/format
    for the same underlying trigger-glance phrases."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------

def _matrix_is_dynamic(matrix: MatrixStrategy) -> bool:
    """True when the matrix's combination count can't be statically
    resolved (e.g. `include: ${{ fromJSON(...) }}`) — no `axes` and no
    `include` list at all. Factored out of `_matrix_summary`'s own first
    branch so its "combinations determined at runtime" prose and any other
    caller's dynamic-matrix check (e.g. text_generator's At a glance
    summary) share one definition instead of the latter pattern-matching
    the former's return string."""
    return not matrix.axes and not matrix.include


def _exact_combination_count(matrix: MatrixStrategy) -> Optional[int]:
    """A single exact combination count only for the two cases
    `_matrix_summary` itself states as one unhedged number: axes-only (no
    `include`, no `exclude`) -> the axis product; include-only (no `axes`,
    no `exclude`) -> `len(include)`. Every other case returns `None` rather
    than approximate a total `_matrix_summary` doesn't itself assert:
    - dynamic (no axes, no include) — `_matrix_is_dynamic` is `True`.
    - axes AND include both present — `_matrix_summary`'s own phrase keeps
      these as two separate numbers ("N base combinations + M via
      include"), since `include`'s merge-vs-append semantics against the
      axis product aren't modelled (see LIMITATIONS.md); summing them
      would assert a precision `_matrix_summary` never claims.
    - any `exclude` present, with or without `include` — `_matrix_summary`
      itself says "up to" in every such case, never a bare total.
    Used only by text_generator's At a glance matrix sentence and Tool 2's
    relationship-table job-behaviour summary; `_matrix_summary`'s own
    per-job prose is untouched by this function."""
    axes, include, exclude = matrix.axes, matrix.include, matrix.exclude
    if exclude:
        return None
    if axes and not include:
        base = 1
        for values in axes.values():
            base *= len(values)
        return base
    if include and not axes:
        return len(include)
    return None  # dynamic, or axes+include both present


def _matrix_summary(matrix: MatrixStrategy) -> str:
    axes, include, exclude = matrix.axes, matrix.include, matrix.exclude

    if _matrix_is_dynamic(matrix):
        # A genuinely dynamic matrix (e.g. `include: ${{ fromJSON(...) }}`) —
        # the parser can't resolve this statically, so neither can we.
        return "combinations determined at runtime"

    if not axes:
        n = len(include)
        return f"{n} {_plural(n, 'combination')} (via include)"

    base = 1
    for values in axes.values():
        base *= len(values)
    axis_names = ", ".join(axes.keys())

    if not include and not exclude:
        return f"{base} {_plural(base, 'combination')} ({axis_names})"

    if include and not exclude:
        return f"{base} base {_plural(base, 'combination')} ({axis_names}) + {len(include)} via include"

    if exclude and not include:
        return f"up to {base} {_plural(base, 'combination')} ({axis_names}), {len(exclude)} excluded"

    # axes AND include AND exclude all present — the genuinely ambiguous case.
    return (f"up to {base} base {_plural(base, 'combination')} ({axis_names}), "
            f"+{len(include)} via include, {len(exclude)} excluded")


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

def _condition_phrase(condition: Condition) -> str:
    structured = condition.structured
    if structured:
        ctype = structured.get("type")
        if ctype == "status_check":
            fn = structured.get("function", "")
            negated = structured.get("negated", False)
            return f"{'not ' if negated else ''}{fn}()"
        if ctype == "ref_equals":
            return f"ref == '{structured.get('value', '')}'"
        if ctype == "event_equals":
            return f"event name == '{structured.get('value', '')}'"
        if ctype == "branch_equals":
            return f"branch == '{structured.get('value', '')}'"
        # "unparsed", or any type this module doesn't recognize (present or
        # future) — fall through to the raw expression, never guess.
    return condition.expression


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def _topological_job_order(jobs: List[Job]) -> List[Job]:
    """
    Order jobs by dependency (topological order), not YAML declaration
    order, via Kahn's algorithm. Ties (jobs with no ordering constraint
    between them) are broken by original declaration order, for
    deterministic/reproducible output.

    Falls back to declaration order if a cycle is detected — reporting
    cycles is ir.validate._check_no_circular_dependencies's job; this
    generator's only obligation is to never crash or hang on one.
    """
    by_name = {j.name: j for j in jobs}
    order_index = {j.name: i for i, j in enumerate(jobs)}
    in_degree = {j.name: 0 for j in jobs}
    dependents: Dict[str, List[str]] = {j.name: [] for j in jobs}
    for job in jobs:
        for dep in job.dependencies:
            if dep not in by_name:
                continue  # dangling dependency; ir.validate flags this separately
            in_degree[job.name] += 1
            dependents[dep].append(job.name)

    ready = [name for name, deg in in_degree.items() if deg == 0]
    result: List[str] = []
    while ready:
        ready.sort(key=lambda n: order_index[n])
        name = ready.pop(0)
        result.append(name)
        for dependent in dependents[name]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)

    if len(result) != len(jobs):
        return list(jobs)
    return [by_name[name] for name in result]


def _jobs_with_no_declared_dependencies(jobs: List[Job]) -> List[Job]:
    """Jobs whose `dependencies` list is literally empty — a narrow,
    truthful check, deliberately distinct from any "diagram entry point"
    notion. A job with a declared but dangling `needs:` reference (e.g.
    `needs: nonexistent-job`) has a real, non-empty `dependencies` list —
    it is NOT "independent"/"has no dependencies", even though such a job
    would need special handling to place on a dependency diagram. That
    distinct, separate concern is `ir.validate`'s (a dangling dependency is
    a validation warning), not this function's. Used only by prose that
    makes a truthful independence claim (text_generator's At a glance /
    Execution summary, tool2/relationships.py's job-behaviour summary) —
    never for diagram wiring."""
    return [j for j in jobs if not j.dependencies]


def _has_dependency_edges(jobs: List[Job]) -> bool:
    """True iff at least one job has a `dependencies` entry that resolves
    to a real job in this pipeline — i.e. iff `generate_mermaid()` would
    draw at least one job-dependency edge for this job list. Mirrors
    `generate_mermaid()`'s own edge-drawing condition (a name in
    `Job.dependencies` counts only if it matches another job's `name`)
    exactly, so this stays consistent with what the diagram itself would
    actually contain — a third, deliberately distinct notion from
    `_jobs_with_no_declared_dependencies` above (a narrow, per-job,
    truthful-independence check for prose) and the now-deleted
    `mermaid_generator._entry_jobs` (a per-job, dangling-tolerant,
    diagram-wiring check). This one is document-assembly-level and
    pipeline-wide: not "which jobs", but "would this pipeline's diagram
    have any real edges in it at all". Used by `tool1/single_pipeline.py`
    and `tool2/relationships.py` to decide whether to show a Mermaid
    diagram at all, or a one-line note instead — see LIMITATIONS.md."""
    names = {j.name for j in jobs}
    return any(dep in names for job in jobs for dep in job.dependencies)


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

def _glance_push(trigger: Trigger) -> str:
    if trigger.branches:
        return f"pushes to {', '.join(f'`{b}`' for b in trigger.branches)}"
    return "pushes"


def _glance_pull_request(trigger: Trigger) -> str:
    return "pull requests"


def _glance_schedule(trigger: Trigger) -> str:
    if trigger.schedule:
        return f"a scheduled run (cron `{trigger.schedule}`)"
    return "a scheduled run"


def _glance_manual(trigger: Trigger) -> str:
    return "manual dispatch"


def _glance_release(trigger: Trigger) -> str:
    return "releases"


def _glance_workflow_call(trigger: Trigger) -> str:
    return "being called by another workflow"


def _glance_workflow_run(trigger: Trigger) -> str:
    if trigger.source_workflow:
        return f"completion of `{trigger.source_workflow}`"
    return "completion of another workflow"


def _glance_other(trigger: Trigger) -> str:
    return trigger.raw if trigger.raw else "an unrecognized trigger"


# Dict-driven (not if/elif) specifically so the coverage test in
# tests/test_generators_common.py can introspect `.keys()` against
# text_generator._TRIGGER_PHRASE_BUILDERS and
# mermaid_generator._TRIGGER_DISPLAY_NAMES — see LIMITATIONS.md/BUILD_PLAN.md
# Phase 7.5. TriggerType.OTHER is deliberately excluded: its only sensible
# rendering is dumping `trigger.raw`, which is inherently generic and not
# something a future-new-TriggerType coverage risk applies to — callers use
# `_TRIGGER_GLANCE_BUILDERS.get(trigger.type, _glance_other)`.
_TRIGGER_GLANCE_BUILDERS: Dict[TriggerType, Callable[[Trigger], str]] = {
    TriggerType.PUSH: _glance_push,
    TriggerType.PULL_REQUEST: _glance_pull_request,
    TriggerType.SCHEDULE: _glance_schedule,
    TriggerType.MANUAL: _glance_manual,
    TriggerType.RELEASE: _glance_release,
    TriggerType.WORKFLOW_CALL: _glance_workflow_call,
    TriggerType.WORKFLOW_RUN: _glance_workflow_run,
}
