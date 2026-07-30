"""
generators.text_generator — ir.schema.Pipeline -> structured plain-text summary.

Layer 3a of PROJECT_PLAN.md: a pure-Python, deterministic, non-LLM generator.
No network calls, no model inference — this is a mechanical transform over
the IR, safe to run offline.

Contract:
- Operates ONLY on ir.schema.Pipeline / its nested dataclasses. Never reads
  raw YAML, never re-derives anything the parser already decided; if a fact
  isn't in the IR, it isn't in this output.
- `raw_extras` (on Pipeline/Job/Step) is not read here, with one narrow,
  deliberate exception: `Job.raw_extras["uses"]` is read to state that a
  `uses:`-only reusable-workflow-calling job delegates to that workflow,
  rather than letting its necessarily-zero own step count read as "does
  nothing" (see `_job_line_body`). This is the parser's own
  already-established, single-job-scoped convention for exactly this fact
  (see LIMITATIONS.md's "Reusable workflows" section) — not a general
  opening of raw_extras into this generator's output. Every other
  raw_extras key on every dataclass remains unread; promoting the rest
  would bypass the schema and couple this generator to parser internals.
- Never guesses at intent. A Condition.structured entry with a type this
  module doesn't specifically recognize (including the parser's own
  "unparsed" marker) always falls back to Condition.expression verbatim.
  This generator does not infer semantic meaning from job/step names either
  (e.g. it will not claim a job "checks code style" just because it's named
  "lint") — that kind of natural-language elaboration is Layer 4's job
  (LLM rewriting of facts this layer already deterministically extracted
  and structurally validated), not this layer's.
- Jobs are listed in dependency (topological) order, not YAML declaration
  order, via Kahn's algorithm with declaration-order tie-breaking. See
  `_topological_job_order` below for the cycle-fallback behaviour.
- `Job.dependencies` is rendered only as "after X" (execution order), never
  as an implied success-gate ("only runs if X passes") — that runtime
  semantic isn't literally encoded in the IR's `dependencies` field, so
  asserting it would be guessing. Only an explicit `Job.condition` is ever
  rendered as a gating rule.
- Each job's aggregate step count is always shown, plus a per-job listing
  of `Step.name` (capped, with an overflow indicator on long jobs — see
  `_step_lines`). No other step-level detail is projected into this
  format (per-step conditions/env/with_args stay out of scope).
- `permissions`/`concurrency`/`deployment_environment` are read directly
  (not via raw_extras) as of 2026-07-22 — these are now dedicated typed IR
  fields, not an opening of the raw_extras exception above. See
  BUILD_PLAN.md's 2026-07-22 changelog entry for the promotion this
  followed.
- generate_text()'s ```text``` block has five sections (Phase 7.5,
  2026-07-30): AT A GLANCE (new, deterministic, zero inference — see
  below), WHEN IT RUNS (renamed from TRIGGERS, same per-trigger content),
  EXECUTION SUMMARY (new — which jobs are independent vs. depend on
  others), IMPLEMENTATION DETAILS (renamed from "JOBS (in order)", content
  unchanged), then LINKED WORKFLOWS / SECRETS REQUIRED as before. This
  replaced a flat fact-inventory structure with no "big picture" framing
  before the detail — supervisor feedback on Tool 1's real output.
- AT A GLANCE is held to the exact same "never guess at intent" rule as
  the rest of this generator, stated explicitly because it's new: every
  sentence is built only from structured IR fields already on
  Trigger/Job/MatrixStrategy (trigger types + their branch/schedule
  qualifiers, job counts, `Job.dependencies` presence/absence via the
  narrow `_jobs_with_no_declared_dependencies` check — never conflated
  with any diagram-only "entry point" notion — and `MatrixStrategy`
  combination counts via `_exact_combination_count`, which only states a
  number for the two cases `_matrix_summary` itself treats as exact). It
  never reads `Job.name`/`Step.name` to guess at semantic purpose — see
  LIMITATIONS.md's "Tool 1 'At a glance' summary" section.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Union

from generators.common import (
    _and_join,
    _condition_phrase,
    _exact_combination_count,
    _jobs_with_no_declared_dependencies,
    _matrix_summary,
    _plural,
    _topological_job_order,
    _TRIGGER_GLANCE_BUILDERS,
    _glance_other,
)
from ir.schema import (
    Job,
    Pipeline,
    SecretScope,
    SourcePlatform,
    Trigger,
    TriggerType,
)

_PLATFORM_DISPLAY_NAMES: Dict[SourcePlatform, str] = {
    SourcePlatform.GITHUB_ACTIONS: "GitHub Actions",
    SourcePlatform.GITLAB_CI: "GitLab CI",
    SourcePlatform.CIRCLECI: "CircleCI",
    SourcePlatform.JENKINS: "Jenkins",
}


def _platform_display_name(platform: SourcePlatform) -> str:
    return _PLATFORM_DISPLAY_NAMES.get(platform, platform.value.replace("_", " ").title())


def _branch_word(n: int) -> str:
    return "branch" if n == 1 else "branches"


def _or_join(items: List[str]) -> str:
    return " or ".join(items)


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

def _ref_qualifiers(trigger: Trigger, branch_word: str) -> List[str]:
    parts: List[str] = []
    if trigger.branches:
        parts.append(f"{branch_word} {_or_join(trigger.branches)} {_branch_word(len(trigger.branches))}")
    if trigger.branches_ignore:
        parts.append(f"except {_branch_word(len(trigger.branches_ignore))} {_or_join(trigger.branches_ignore)}")
    if trigger.tags:
        parts.append(f"with tag matching {_or_join(trigger.tags)}")
    if trigger.tags_ignore:
        parts.append(f"excluding tags matching {_or_join(trigger.tags_ignore)}")
    if trigger.paths:
        parts.append(f"touching path {_or_join(trigger.paths)}")
    if trigger.paths_ignore:
        parts.append(f"excluding paths {_or_join(trigger.paths_ignore)}")
    return parts


def _combine(base: str, parts: List[str]) -> str:
    return f"{base} {'; '.join(parts)}" if parts else base


def _input_names(inputs: List[Dict[str, Any]]) -> str:
    return ", ".join(i.get("name", "?") for i in inputs)


def _push_phrase(trigger: Trigger) -> str:
    return _combine("Runs on every push", _ref_qualifiers(trigger, "to"))


def _pull_request_phrase(trigger: Trigger) -> str:
    return _combine("Runs on every pull request", _ref_qualifiers(trigger, "targeting"))


def _release_phrase(trigger: Trigger) -> str:
    return _combine("Runs on every release event", _ref_qualifiers(trigger, "to"))


def _schedule_phrase(trigger: Trigger) -> str:
    return f"Runs on a schedule ({trigger.schedule or 'schedule not specified'})"


def _manual_phrase(trigger: Trigger) -> str:
    phrase = "Can be triggered manually"
    return phrase + (f" — inputs: {_input_names(trigger.inputs)}" if trigger.inputs else "")


def _workflow_call_phrase(trigger: Trigger) -> str:
    phrase = "Can be called by other workflows as a reusable workflow"
    return phrase + (f" — inputs: {_input_names(trigger.inputs)}" if trigger.inputs else "")


def _workflow_run_phrase(trigger: Trigger) -> str:
    return f"Runs after the '{trigger.source_workflow or 'an unspecified workflow'}' workflow completes"


def _other_trigger_phrase(trigger: Trigger) -> str:
    # TriggerType.OTHER, or any future enum member this module doesn't know.
    return f"Runs on trigger: {trigger.raw}" if trigger.raw else "Runs on an unrecognized trigger type"


# Dict-driven (not if/elif) so tests/test_generators_common.py's coverage
# test can introspect `.keys()` against mermaid_generator._TRIGGER_DISPLAY_NAMES
# and generators.common._TRIGGER_GLANCE_BUILDERS — all three must cover the
# same TriggerType set (Phase 7.5 Revision 3), so a future new TriggerType
# can't be silently wired into one and missed in the others.
# TriggerType.OTHER is deliberately not a key — its only sensible rendering
# is dumping `trigger.raw`, handled by the `_other_trigger_phrase` fallback.
_TRIGGER_PHRASE_BUILDERS: Dict[TriggerType, Callable[[Trigger], str]] = {
    TriggerType.PUSH: _push_phrase,
    TriggerType.PULL_REQUEST: _pull_request_phrase,
    TriggerType.RELEASE: _release_phrase,
    TriggerType.SCHEDULE: _schedule_phrase,
    TriggerType.MANUAL: _manual_phrase,
    TriggerType.WORKFLOW_CALL: _workflow_call_phrase,
    TriggerType.WORKFLOW_RUN: _workflow_run_phrase,
}


def _trigger_phrase(trigger: Trigger) -> str:
    builder = _TRIGGER_PHRASE_BUILDERS.get(trigger.type, _other_trigger_phrase)
    return builder(trigger)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

_STEP_LIST_CAP = 10


def _step_lines(job: Job) -> List[str]:
    """
    Per-job step name listing — PROJECT_PLAN.md's Tool 1 deliverable list
    normatively includes "What each step in each job does"; the aggregate
    count alone (this generator's prior behaviour) didn't satisfy it. Only
    `Step.name` is surfaced, nothing else (no with_args/env/raw_extras, no
    step-level Condition) — mechanical and factual, matching this
    generator's existing never-fabricate-intent principle.

    Capped at `_STEP_LIST_CAP` with an overflow line rather than listed in
    full: across all 10 real fixtures (58 jobs), the median job has 4-5
    steps and 53 of 58 have 10 or fewer — a cap of 10 shows the vast
    majority of jobs in full while still bounding the few outliers
    (rust_ci.yml's `job` has 33 steps, upload_artifact_test.yml's `build`
    has 28) so they don't turn into a wall of text. The aggregate count in
    the job line itself (see `_job_line_body`) is never affected by this
    cap and always reflects the true total.
    """
    if not job.steps:
        return []
    shown = job.steps[:_STEP_LIST_CAP]
    lines = [f"   - {step.name}" for step in shown]
    remaining = len(job.steps) - len(shown)
    if remaining > 0:
        lines.append(f"   - ... and {remaining} more {_plural(remaining, 'step')}")
    return lines


def _permissions_phrase(value: Union[Dict[str, str], str]) -> str:
    if isinstance(value, str):
        return value
    if not value:
        return "none (all permissions explicitly disabled)"
    return ", ".join(f"{k}: {v}" for k, v in value.items())


def _concurrency_phrase(value: Dict[str, Any]) -> str:
    phrase = f"group {value.get('group', '?')}"
    if value.get("cancel-in-progress"):
        phrase += "; cancels in-progress runs"
    return phrase


def _job_line_body(job: Job) -> str:
    clauses: List[str] = []

    if job.runner:
        clauses.append(f"runs on {job.runner}")

    uses = job.raw_extras.get("uses")
    if uses:
        # A job whose own `uses:` makes it a reusable-workflow call has no
        # `steps:` of its own — GH Actions treats `uses:`/`steps:` as
        # mutually exclusive at job level. "0 steps" would misleadingly
        # read as "this job does nothing"; state the delegation instead.
        # This is the one deliberate raw_extras exception documented in
        # the module docstring.
        clauses.append(f"delegates to reusable workflow {uses}")
    else:
        n = len(job.steps)
        clauses.append(f"{n} {_plural(n, 'step')}")

    if job.matrix is not None:
        clauses.append(f"matrix: {_matrix_summary(job.matrix)}")

    if job.dependencies:
        clauses.append(f"after {', '.join(job.dependencies)}")

    if job.artifacts_produced:
        clauses.append(f"produces {', '.join(job.artifacts_produced)}")

    if job.artifacts_consumed:
        clauses.append(f"uses artifacts from {', '.join(job.artifacts_consumed)}")

    if job.condition is not None:
        clauses.append(f"condition: {_condition_phrase(job.condition)}")

    if job.allow_failure:
        clauses.append("allowed to fail")

    if job.permissions is not None:
        clauses.append(f"permissions: {_permissions_phrase(job.permissions)}")

    if job.concurrency is not None:
        clauses.append(f"concurrency: {_concurrency_phrase(job.concurrency)}")

    if job.deployment_environment is not None:
        clauses.append(f"deployment environment: {job.deployment_environment}")

    return "; ".join(clauses)


# ---------------------------------------------------------------------------
# Secrets / linked workflows
# ---------------------------------------------------------------------------

def _secret_line(secret, jobs_by_name: Dict[str, Job]) -> str:
    """
    PIPELINE-scope secrets have no scope_ref at all. JOB-scope's scope_ref
    is the job key verbatim — already human-readable, shown as-is. STEP-
    scope's scope_ref is the parser's internal `f"{job_key}.{step_index}"`
    convention (0-based index) — decoded here into the real step name via
    `jobs_by_name`, rather than leaking the raw "job.26" form to the
    reader. Splitting on "." is safe because GH Actions job-key syntax
    forbids the character (see LIMITATIONS.md). Branches on `secret.scope`
    directly rather than inferring shape from the string, so PIPELINE/JOB
    are each handled on their own terms, not just STEP.
    """
    if secret.scope == SecretScope.PIPELINE or not secret.scope_ref:
        return f"- {secret.name}"

    if secret.scope == SecretScope.JOB:
        return f"- {secret.name} (used in job: {secret.scope_ref})"

    job_key, _, index_str = secret.scope_ref.partition(".")
    job = jobs_by_name.get(job_key)
    step_index = int(index_str) if index_str.isdigit() else None
    if job is not None and step_index is not None and 0 <= step_index < len(job.steps):
        return f"- {secret.name} (used in job: {job_key}, step: {job.steps[step_index].name})"
    # Defensive fallback — shouldn't happen against real parser output,
    # but a hand-built Secret/Pipeline pairing (e.g. in a test) could have
    # a scope_ref that doesn't resolve. Degrade to the job-only reference
    # rather than crash or show a broken index.
    return f"- {secret.name} (used in job: {job_key})"


# ---------------------------------------------------------------------------
# At a glance (Phase 7.5, new) / Execution summary (Phase 7.5, new)
# ---------------------------------------------------------------------------

def _at_a_glance_triggers_sentence(triggers: List[Trigger]) -> str:
    phrases = [_TRIGGER_GLANCE_BUILDERS.get(t.type, _glance_other)(t) for t in triggers]
    return f"This workflow runs on {_and_join(phrases)}."


def _at_a_glance_jobs_sentence(jobs: List[Job]) -> str:
    n = len(jobs)
    independent = _jobs_with_no_declared_dependencies(jobs)
    if len(independent) == n:
        return f"It contains {n} {_plural(n, 'job')}, with no job dependencies, so GitHub may run them in parallel."
    if not independent:
        return f"It contains {n} {_plural(n, 'job')}, all of which depend on other jobs."
    dependent = n - len(independent)
    return (
        f"It contains {n} {_plural(n, 'job')}: {len(independent)} with no declared dependencies, "
        f"{dependent} depending on other jobs."
    )


def _at_a_glance_matrix_sentence(jobs: List[Job]) -> str:
    matrix_jobs = [j for j in jobs if j.matrix is not None]
    n = len(jobs)
    sentence = f"{len(matrix_jobs)} of {n} {_plural(n, 'job')} use a build matrix"

    counts = [_exact_combination_count(j.matrix) for j in matrix_jobs]
    known = [c for c in counts if c is not None]
    unresolved = len(counts) - len(known)

    if known and not unresolved:
        return sentence + f"; together these define {sum(known)} configured combinations."
    if known and unresolved:
        possessive = "job's" if unresolved == 1 else "jobs'"
        return sentence + (
            f"; {len(known)} of them define {sum(known)} configured combinations between them "
            f"({unresolved} more {possessive} matrix "
            f"{_plural(unresolved, 'size')} not reflected in that total)."
        )
    return sentence + "."  # no matrix-using job's count is statically resolvable


def _at_a_glance_lines(pipeline: Pipeline) -> List[str]:
    """Deterministic, Layer 3-only "big picture" summary — zero inference
    from job/step names, see module docstring and LIMITATIONS.md's "Tool 1
    'At a glance' summary" section for the boundary this holds to."""
    lines: List[str] = []

    if pipeline.triggers:
        lines.append(_at_a_glance_triggers_sentence(pipeline.triggers))

    if pipeline.jobs:
        lines.append(_at_a_glance_jobs_sentence(pipeline.jobs))

    if any(j.matrix is not None for j in pipeline.jobs):
        lines.append(_at_a_glance_matrix_sentence(pipeline.jobs))

    return lines


def _execution_summary_lines(pipeline: Pipeline) -> List[str]:
    """Which jobs are independent (no declared dependencies) vs. which
    depend on others — the narrow, truthful `_jobs_with_no_declared_dependencies`
    check, never the diagram's dangling-tolerant one. A job whose only
    `needs:` reference is dangling still has a non-empty `dependencies`
    list, so it's listed here under "runs after", not among the
    independent jobs — see generators.common._jobs_with_no_declared_dependencies."""
    jobs = pipeline.jobs
    if not jobs:
        return []

    lines: List[str] = []
    independent = _jobs_with_no_declared_dependencies(jobs)
    if independent:
        lines.append(f"Independent jobs (no dependencies): {', '.join(j.name for j in independent)}")

    independent_names = {j.name for j in independent}
    ordered = _topological_job_order(jobs)
    for job in ordered:
        if job.name in independent_names:
            continue
        lines.append(f"{job.name} runs after {', '.join(job.dependencies)}")

    return lines


# ---------------------------------------------------------------------------
# Top-level generator
# ---------------------------------------------------------------------------

def generate_text(pipeline: Pipeline) -> str:
    """Render a structured plain-text summary of `pipeline`. See module docstring for the contract."""
    lines: List[str] = [
        f"Pipeline: {pipeline.name}",
        f"Source: {pipeline.source_file} ({_platform_display_name(pipeline.source_platform)})",
    ]

    if pipeline.permissions is not None:
        lines.append(f"Permissions: {_permissions_phrase(pipeline.permissions)}")

    if pipeline.concurrency is not None:
        lines.append(f"Concurrency: {_concurrency_phrase(pipeline.concurrency)}")

    glance = _at_a_glance_lines(pipeline)
    if glance:
        lines.append("")
        lines.append("AT A GLANCE")
        lines += glance

    if pipeline.triggers:
        lines.append("")
        lines.append("WHEN IT RUNS")
        lines += [f"- {_trigger_phrase(t)}" for t in pipeline.triggers]

    execution_summary = _execution_summary_lines(pipeline)
    if execution_summary:
        lines.append("")
        lines.append("EXECUTION SUMMARY")
        lines += execution_summary

    if pipeline.jobs:
        lines.append("")
        lines.append("IMPLEMENTATION DETAILS")
        ordered = _topological_job_order(pipeline.jobs)
        for i, job in enumerate(ordered, start=1):
            lines.append(f"{i}. {job.name} — {_job_line_body(job)}")
            lines.extend(_step_lines(job))

    if pipeline.linked_workflows:
        lines.append("")
        lines.append("LINKED WORKFLOWS")
        lines += [f"- {lw.relationship} {lw.target}" for lw in pipeline.linked_workflows]

    if pipeline.secrets:
        lines.append("")
        lines.append("SECRETS REQUIRED")
        jobs_by_name = {j.name: j for j in pipeline.jobs}
        lines += [_secret_line(s, jobs_by_name) for s in pipeline.secrets]

    return "\n".join(lines) + "\n"
