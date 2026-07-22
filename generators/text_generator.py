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
"""

from __future__ import annotations

from typing import Any, Dict, List, Union

from generators.common import _condition_phrase, _matrix_summary, _topological_job_order
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


def _plural(n: int, word: str) -> str:
    return word if n == 1 else word + "s"


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


def _trigger_phrase(trigger: Trigger) -> str:
    t = trigger.type
    if t == TriggerType.PUSH:
        return _combine("Runs on every push", _ref_qualifiers(trigger, "to"))
    if t == TriggerType.PULL_REQUEST:
        return _combine("Runs on every pull request", _ref_qualifiers(trigger, "targeting"))
    if t == TriggerType.RELEASE:
        return _combine("Runs on every release event", _ref_qualifiers(trigger, "to"))
    if t == TriggerType.SCHEDULE:
        return f"Runs on a schedule ({trigger.schedule or 'schedule not specified'})"
    if t == TriggerType.MANUAL:
        phrase = "Can be triggered manually"
        return phrase + (f" — inputs: {_input_names(trigger.inputs)}" if trigger.inputs else "")
    if t == TriggerType.WORKFLOW_CALL:
        phrase = "Can be called by other workflows as a reusable workflow"
        return phrase + (f" — inputs: {_input_names(trigger.inputs)}" if trigger.inputs else "")
    if t == TriggerType.WORKFLOW_RUN:
        return f"Runs after the '{trigger.source_workflow or 'an unspecified workflow'}' workflow completes"
    # TriggerType.OTHER, or any future enum member this module doesn't know.
    return f"Runs on trigger: {trigger.raw}" if trigger.raw else "Runs on an unrecognized trigger type"


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

    if pipeline.triggers:
        lines.append("")
        lines.append("TRIGGERS")
        lines += [f"- {_trigger_phrase(t)}" for t in pipeline.triggers]

    if pipeline.jobs:
        lines.append("")
        lines.append("JOBS (in order)")
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
