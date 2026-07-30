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
- This diagram shows job dependencies only — no trigger nodes (Phase 7.5,
  2026-07-30, resolves the origin-scoped trigger-wiring exception this
  docstring used to document). Before this change, every `Trigger` got its
  own node wired to every "entry" job, which fanned out into a
  near-meaningless number of edges on pipelines with many independent jobs
  and few triggers (e.g. 14 jobs x 4 triggers = 56 edges on
  `tests/fixtures/setup_python_test.yml`). Triggers are covered as text in
  `text_generator.generate_text()`'s "WHEN IT RUNS" / "AT A GLANCE"
  sections instead — this diagram is purely the job dependency graph.
- `Pipeline.secrets`, `Pipeline.environment_variables`, and
  `Pipeline.linked_workflows` are out of scope for this diagram — it is
  specifically the job dependency graph. `LinkedWorkflow` in particular has
  no per-job attribution after the parser's `(target, relationship)` dedup,
  so it can't be placed accurately on the graph even if it were in scope.
- `Job.dependencies` edges represent execution order only, same as
  `text_generator` — no success-gating semantic is implied by the edge
  itself; only an explicit `Job.condition` (rendered as a node annotation)
  represents a gating rule. A job with a dangling `needs:` reference (its
  only listed dependency doesn't resolve to a real job in this pipeline)
  gets no incoming edge at all — it renders as a disconnected node, same
  as a job with no dependencies, since neither has a real edge to draw;
  `ir.validate` is what flags the dangling reference itself, not this
  diagram.
- A job condition's diagram annotation is truncated past
  `_MERMAID_CONDITION_MAX_LEN` chars (or at its first line, if multi-line)
  — see `_condition_annotation`. This is a diagram-only readability
  trade-off: `text_generator.generate_text()` still renders
  `Condition.expression` verbatim in the same document's text section, so
  "never silently drop content" holds at the document level even though
  this one diagram annotation is intentionally lossy.
"""

from __future__ import annotations

from typing import List

from generators.common import _condition_phrase, _matrix_summary, _topological_job_order
from ir.schema import Condition, Job, Pipeline, TriggerType

# Kept as a dict (not folded away with the trigger-node removal below) so it
# stays the second of three cross-checked TriggerType -> representation
# mappings that must cover the same TriggerType set — see
# text_generator._TRIGGER_PHRASE_BUILDERS, generators.common._TRIGGER_GLANCE_BUILDERS,
# and tests/test_generators_common.py's coverage test (Phase 7.5 Revision 3).
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
# Jobs
# ---------------------------------------------------------------------------

_MERMAID_CONDITION_MAX_LEN = 80


def _condition_annotation(condition: Condition) -> str:
    """
    Diagram-only truncation of a job condition's annotation text. Real
    data across all 10 fixtures' 19 job-level conditions: 16 are 75 chars
    or fewer and single-line; exactly 3 are not —
    pytorch_lint.yml's `lintrunner-clang`/`lintrunner-pyrefly` (a ~12-line
    block-scalar `if:`, 786/236 chars total once rendered, but only 41
    chars on their first line) and `pr-sanity-checks` (161 chars, single
    line, no embedded newline for `_escape_label` to convert). 80 is the
    natural cut point separating the 16 normal conditions from those 3
    oversized ones, not an arbitrary round number. Untruncated, the
    block-scalar pair produce enormous nodes that dominate the graph.

    generate_text() renders Condition.expression verbatim regardless — see
    the module docstring's "never silently drop content" note. This
    function only ever shortens the diagram's own annotation text.
    """
    phrase = _condition_phrase(condition)
    if len(phrase) <= _MERMAID_CONDITION_MAX_LEN and "\n" not in phrase:
        return phrase
    first_line = phrase.split("\n", 1)[0]
    if len(first_line) > _MERMAID_CONDITION_MAX_LEN:
        first_line = first_line[:_MERMAID_CONDITION_MAX_LEN].rstrip()
    return f"{first_line}..."


def _job_node_label(job: Job) -> str:
    annotations: List[str] = []

    if job.matrix is not None:
        annotations.append(f"matrix: {_matrix_summary(job.matrix)}")

    if job.condition is not None:
        annotations.append(f"if: {_condition_annotation(job.condition)}")

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
    job_names = {j.name for j in pipeline.jobs}

    for job in ordered_jobs:
        lines.append(f'    {job.name}["{_escape_label(_job_node_label(job))}"]')

    for job in ordered_jobs:
        for dep in job.dependencies:
            if dep not in job_names:
                continue  # dangling dependency; ir.validate flags this separately
            lines.append(f"    {dep} --> {job.name}")

    return "\n".join(lines) + "\n"
