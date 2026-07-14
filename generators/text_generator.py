"""
generators.text_generator — ir.schema.Pipeline -> structured plain-text summary.

Layer 3a of PROJECT_PLAN.md: a pure-Python, deterministic, non-LLM generator.
No network calls, no model inference — this is a mechanical transform over
the IR, safe to run offline.

Contract:
- Operates ONLY on ir.schema.Pipeline / its nested dataclasses. Never reads
  raw YAML, never re-derives anything the parser already decided; if a fact
  isn't in the IR, it isn't in this output.
- `raw_extras` (on Pipeline/Job/Step) is NEVER read or surfaced here. It is
  the IR layer's own escape hatch for unmapped platform fields; promoting it
  into end-user text would bypass the schema and couple this generator to
  parser internals. A job whose only real detail lives in raw_extras (e.g. a
  `uses:`-only reusable-workflow-calling job) is described using only its
  own non-raw_extras fields (name/runner/steps/dependencies/condition/
  matrix/environment/allow_failure) — see LIMITATIONS.md.
- Never guesses at intent. A Condition.structured entry with a type this
  module doesn't specifically recognize (including the parser's own
  "unparsed" marker) always falls back to Condition.expression verbatim.
  This generator does not infer semantic meaning from job/step names either
  (e.g. it will not claim a job "checks code style" just because it's named
  "lint") — that kind of natural-language elaboration is Layer 4's job
  (LLM rewriting of already Python-verified facts), not this layer's.
- Jobs are listed in dependency (topological) order, not YAML declaration
  order, via Kahn's algorithm with declaration-order tie-breaking. See
  `_topological_job_order` below for the cycle-fallback behaviour.
- `Job.dependencies` is rendered only as "after X" (execution order), never
  as an implied success-gate ("only runs if X passes") — that runtime
  semantic isn't literally encoded in the IR's `dependencies` field, so
  asserting it would be guessing. Only an explicit `Job.condition` is ever
  rendered as a gating rule.
- Only an aggregate step count is shown per job — no step-level detail
  (per-step conditions/env/with_args are not projected into this format).
"""

from __future__ import annotations

from typing import Any, Dict, List

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

def _job_line_body(job: Job) -> str:
    clauses: List[str] = []

    if job.runner:
        clauses.append(f"runs on {job.runner}")

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

    return "; ".join(clauses)


# ---------------------------------------------------------------------------
# Secrets / linked workflows
# ---------------------------------------------------------------------------

def _secret_line(secret) -> str:
    if secret.scope != SecretScope.PIPELINE and secret.scope_ref:
        return f"- {secret.name} (used in job: {secret.scope_ref})"
    return f"- {secret.name}"


# ---------------------------------------------------------------------------
# Top-level generator
# ---------------------------------------------------------------------------

def generate_text(pipeline: Pipeline) -> str:
    """Render a structured plain-text summary of `pipeline`. See module docstring for the contract."""
    lines: List[str] = [
        f"Pipeline: {pipeline.name}",
        f"Source: {pipeline.source_file} ({_platform_display_name(pipeline.source_platform)})",
    ]

    if pipeline.triggers:
        lines.append("")
        lines.append("TRIGGERS")
        lines += [f"- {_trigger_phrase(t)}" for t in pipeline.triggers]

    if pipeline.jobs:
        lines.append("")
        lines.append("JOBS (in order)")
        ordered = _topological_job_order(pipeline.jobs)
        lines += [
            f"{i}. {job.name} — {_job_line_body(job)}"
            for i, job in enumerate(ordered, start=1)
        ]

    if pipeline.linked_workflows:
        lines.append("")
        lines.append("LINKED WORKFLOWS")
        lines += [f"- {lw.relationship} {lw.target}" for lw in pipeline.linked_workflows]

    if pipeline.secrets:
        lines.append("")
        lines.append("SECRETS REQUIRED")
        lines += [_secret_line(s) for s in pipeline.secrets]

    return "\n".join(lines) + "\n"
