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

from typing import Dict, List

from ir.schema import Condition, Job, MatrixStrategy


def _plural(n: int, word: str) -> str:
    return word if n == 1 else word + "s"


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------

def _matrix_summary(matrix: MatrixStrategy) -> str:
    axes, include, exclude = matrix.axes, matrix.include, matrix.exclude

    if not axes and not include:
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
