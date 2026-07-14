"""
generators.mermaid_generator — ir.schema.Pipeline job graph -> Mermaid
flowchart syntax.

Layer 3b of PROJECT_PLAN.md: a pure-Python, deterministic, non-LLM
generator. No network calls, no model inference — this is a mechanical
transform over the IR, safe to run offline. Shares its topological-order,
matrix-summary, and condition-phrase logic with `generators.text_generator`
via `generators.common`, so both generators stay consistent by
construction rather than by convention.

Contract:
- Operates ONLY on ir.schema.Pipeline / its nested dataclasses. Never reads
  raw YAML, never re-derives anything the parser already decided; if a fact
  isn't in the IR, it isn't in this diagram.
- `raw_extras` (on Pipeline/Job/Step) is NEVER read or surfaced here, same
  rule as `text_generator`. A `uses:`-only reusable-workflow-calling job is
  drawn using only its own non-raw_extras fields — see LIMITATIONS.md.
- Never guesses at intent. A Condition.structured entry with a type this
  module doesn't specifically recognize (including the parser's own
  "unparsed" marker) always falls back to Condition.expression verbatim,
  via the same `_condition_phrase` `text_generator` uses.
- Jobs are declared in dependency (topological) order, not YAML declaration
  order, via the shared `_topological_job_order` (Kahn's algorithm,
  declaration-order tie-breaking, cycle-safe fallback to declaration
  order).
- Node IDs are `Job.name` verbatim — every parsed `Job.name` is a real
  GitHub Actions job *key*, constrained to `[A-Za-z_][A-Za-z0-9_-]*`, so it
  is always a safe bare Mermaid node ID with no sanitization needed.
- A matrix job renders as a single node annotated with the matrix summary
  (reusing `_matrix_summary`'s combination-count approximation), never
  fanned out into one node per combination — resolving concrete matrix
  combinations is a deferred downstream concern (see LIMITATIONS.md), and
  this generator defers it again rather than reintroducing that
  complexity.
- Job node labels carry only name + compact annotations (matrix/condition/
  allow_failure) — no step count, runner, or artifact detail. That level
  of detail stays `text_generator`-only; a diagram with every fact from
  the text summary crammed into node labels stops being readable on
  larger graphs (e.g. the 14-job pytorch_lint.yml fixture).
- One node per `Trigger`, connected to every "entry" job (a job with no
  dependency that resolves to a real job in this pipeline — including a
  job whose only `needs:` reference is dangling, mirroring
  `_topological_job_order`'s own dangling-dependency handling). Trigger
  node IDs are `trigger_<index>` (0-based position in `pipeline.triggers`)
  — never derived from `TriggerType`, since a pipeline can have multiple
  triggers of the same type (e.g. several `schedule:` entries) which would
  otherwise collide on a type-derived ID.
- `Pipeline.secrets`, `Pipeline.environment_variables`, and
  `Pipeline.linked_workflows` are out of scope for this diagram — it is
  specifically the job dependency graph. `LinkedWorkflow` in particular has
  no per-job attribution after the parser's `(target, relationship)` dedup,
  so it can't be placed accurately on the graph even if it were in scope.
- `Job.dependencies` edges represent execution order only, same as
  `text_generator` — no success-gating semantic is implied by the edge
  itself; only an explicit `Job.condition` (rendered as a node annotation)
  represents a gating rule.
"""

from __future__ import annotations

from typing import List

from generators.common import _condition_phrase, _matrix_summary, _topological_job_order
from ir.schema import Job, Pipeline, Trigger, TriggerType

_TRIGGER_DISPLAY_NAMES = {
    TriggerType.PUSH: "Push",
    TriggerType.PULL_REQUEST: "Pull request",
    TriggerType.SCHEDULE: "Schedule",
    TriggerType.MANUAL: "Manual dispatch",
    TriggerType.RELEASE: "Release",
    TriggerType.WORKFLOW_CALL: "Workflow call",
    TriggerType.WORKFLOW_RUN: "Workflow run",
}


def _escape_label(text: str) -> str:
    """
    Make arbitrary IR text safe to embed inside a quoted Mermaid node
    label. Newlines are converted rather than stripped (a real case:
    pytorch_lint.yml's `lintrunner-clang`/`lintrunner-pyrefly` jobs have a
    ~10-line block-scalar `if:` condition that falls through to
    `_condition_phrase`'s verbatim fallback) — faithful to the "never
    silently drop content" rule the parser and text_generator already
    established, just adapted to Mermaid's specific syntax constraints.
    """
    return text.replace('"', "#quot;").replace("\r\n", "<br/>").replace("\n", "<br/>")


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

def _trigger_node_label(trigger: Trigger) -> str:
    return _TRIGGER_DISPLAY_NAMES.get(trigger.type, trigger.raw or "Trigger")


def _entry_jobs(jobs: List[Job]) -> List[Job]:
    """
    Jobs with no dependency that resolves to a real job in this pipeline —
    either `dependencies` is empty, or every listed dependency is dangling.
    Mirrors `_topological_job_order`'s own dangling-dependency skip, so a
    job whose only `needs:` reference doesn't exist still gets at least one
    incoming edge (from the trigger nodes) instead of floating disconnected.
    """
    names = {j.name for j in jobs}
    return [j for j in jobs if not any(dep in names for dep in j.dependencies)]


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def _job_node_label(job: Job) -> str:
    annotations: List[str] = []

    if job.matrix is not None:
        annotations.append(f"matrix: {_matrix_summary(job.matrix)}")

    if job.condition is not None:
        annotations.append(f"if: {_condition_phrase(job.condition)}")

    if job.allow_failure:
        annotations.append("allow to fail")

    if not annotations:
        return job.name
    return f"{job.name} [{', '.join(annotations)}]"


# ---------------------------------------------------------------------------
# Top-level generator
# ---------------------------------------------------------------------------

def generate_mermaid(pipeline: Pipeline) -> str:
    """Render a Mermaid `flowchart` of `pipeline`'s job graph. See module docstring for the contract."""
    lines: List[str] = ["flowchart LR"]

    if not pipeline.jobs:
        return "\n".join(lines) + "\n"

    ordered_jobs = _topological_job_order(pipeline.jobs)
    entry_jobs = _entry_jobs(pipeline.jobs)
    job_names = {j.name for j in pipeline.jobs}

    for i, trigger in enumerate(pipeline.triggers):
        lines.append(f'    trigger_{i}(["{_escape_label(_trigger_node_label(trigger))}"])')

    for job in ordered_jobs:
        lines.append(f'    {job.name}["{_escape_label(_job_node_label(job))}"]')

    for i in range(len(pipeline.triggers)):
        for job in entry_jobs:
            lines.append(f"    trigger_{i} --> {job.name}")

    for job in ordered_jobs:
        for dep in job.dependencies:
            if dep not in job_names:
                continue  # dangling dependency; ir.validate flags this separately
            lines.append(f"    {dep} --> {job.name}")

    return "\n".join(lines) + "\n"
