"""
ir/validate.py — Structural validation for the CI Pipeline Documentation Tool's IR.

This checks that a built Pipeline object is internally CONSISTENT — not that it
correctly represents the original YAML (that's the parser's job, and belongs in
parser-level tests against fixtures), but that the IR itself doesn't contain
impossible states: dangling job references, circular dependencies, missing
required fields for the trigger type declared, secrets scoped to jobs that
don't exist, and so on.

This module is deliberately written to be reused, unmodified, as part of the
Tier 1 automated evaluation checks in EVALUATION_PLAN.md (the "coverage check"
family) — a pipeline that fails validation is one the tool should refuse to
silently document rather than pass along to the generators.

Usage:
    from ir.validate import validate_pipeline, is_valid

    issues = validate_pipeline(pipeline)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        raise ValueError("IR failed validation:\\n" + "\\n".join(str(e) for e in errors))
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set

from ir.schema import Pipeline, TriggerType, SecretScope


@dataclass
class ValidationIssue:
    severity: str   # "error" | "warning"
    field: str      # dotted/indexed path, e.g. "jobs[2].dependencies"
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.field}: {self.message}"


class IRValidationError(ValueError):
    """Raised when error-level findings make an IR unsafe to generate from."""

    def __init__(self, issues: List[ValidationIssue]):
        self.issues = issues
        super().__init__("IR validation failed:\n" + "\n".join(str(issue) for issue in issues))


def validate_pipeline(pipeline: Pipeline) -> List[ValidationIssue]:
    """
    Run every structural check against a Pipeline and return all issues found.
    Does not raise — callers decide what to do with errors vs warnings (e.g.
    Tool 1/2 might refuse to proceed on errors but just log warnings).
    """
    issues: List[ValidationIssue] = []

    issues += _check_top_level_fields(pipeline)
    issues += _check_job_names_unique(pipeline)
    issues += _check_job_dependencies_exist(pipeline)
    issues += _check_no_circular_dependencies(pipeline)
    issues += _check_artifact_references(pipeline)
    issues += _check_matrix_structures(pipeline)
    issues += _check_conditions(pipeline)
    issues += _check_secret_and_env_scopes(pipeline)
    issues += _check_triggers(pipeline)
    issues += _check_linked_workflows(pipeline)
    issues += _check_malformed_workflow_structures(pipeline)
    issues += _check_non_empty_pipeline(pipeline)

    return issues


def is_valid(pipeline: Pipeline) -> bool:
    """Convenience: True if there are no ERROR-level issues (warnings are fine)."""
    return not any(i.severity == "error" for i in validate_pipeline(pipeline))


def validate_or_raise(pipeline: Pipeline) -> List[ValidationIssue]:
    """Return warnings for a valid IR, or raise with all error-level findings."""
    issues = validate_pipeline(pipeline)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        raise IRValidationError(errors)
    return [issue for issue in issues if issue.severity == "warning"]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_top_level_fields(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    if not pipeline.name or not pipeline.name.strip():
        issues.append(ValidationIssue("error", "name", "Pipeline name is empty."))
    if not pipeline.source_file or not pipeline.source_file.strip():
        issues.append(ValidationIssue("error", "source_file", "Pipeline source_file is empty."))
    return issues


def _job_names(pipeline: Pipeline) -> Set[str]:
    return {j.name for j in pipeline.jobs}


def _check_job_names_unique(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    seen: Set[str] = set()
    for i, job in enumerate(pipeline.jobs):
        if job.name in seen:
            issues.append(ValidationIssue("error", f"jobs[{i}].name", f"Duplicate job name '{job.name}'."))
        seen.add(job.name)
    return issues


def _check_job_dependencies_exist(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    names = _job_names(pipeline)
    for i, job in enumerate(pipeline.jobs):
        for dep in job.dependencies:
            if dep not in names:
                issues.append(ValidationIssue(
                    "error", f"jobs[{i}].dependencies",
                    f"Job '{job.name}' depends on '{dep}', which does not exist in this pipeline."
                ))
    return issues


def _check_no_circular_dependencies(pipeline: Pipeline) -> List[ValidationIssue]:
    """
    DFS cycle detection over the job dependency graph. A cycle means the
    pipeline as parsed could never actually run — almost certainly a parser
    bug rather than a real-world pipeline, but worth catching loudly rather
    than silently generating a nonsensical Mermaid diagram from it.
    """
    issues = []
    graph = {job.name: list(job.dependencies) for job in pipeline.jobs}

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in graph}

    def visit(node: str, path: List[str]) -> Optional[List[str]]:
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if neighbor not in color:
                continue  # dangling dep already reported by _check_job_dependencies_exist
            if color[neighbor] == GRAY:
                return path + [neighbor]
            if color[neighbor] == WHITE:
                result = visit(neighbor, path + [neighbor])
                if result:
                    return result
        color[node] = BLACK
        return None

    for name in list(graph.keys()):
        if color[name] == WHITE:
            cycle = visit(name, [name])
            if cycle:
                issues.append(ValidationIssue(
                    "error", "jobs[*].dependencies",
                    f"Circular dependency detected: {' -> '.join(cycle)}"
                ))
                break  # one report is enough; don't spam once a cycle is found
    return issues


def _check_artifact_references(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    names = _job_names(pipeline)
    producers = {job.name: set(job.artifacts_produced) for job in pipeline.jobs}

    for i, job in enumerate(pipeline.jobs):
        for consumed_from in job.artifacts_consumed:
            if consumed_from not in names:
                issues.append(ValidationIssue(
                    "error", f"jobs[{i}].artifacts_consumed",
                    f"Job '{job.name}' consumes artifacts from '{consumed_from}', which does not exist."
                ))
            elif not producers.get(consumed_from):
                issues.append(ValidationIssue(
                    "warning", f"jobs[{i}].artifacts_consumed",
                    f"Job '{job.name}' consumes artifacts from '{consumed_from}', but that job "
                    f"declares no artifacts_produced. May be a parser gap rather than a real "
                    f"mismatch — worth a spot-check."
                ))
    return issues


def _check_matrix_structures(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    for i, job in enumerate(pipeline.jobs):
        if job.matrix is None:
            continue
        if not job.matrix.axes:
            issues.append(ValidationIssue(
                "warning", f"jobs[{i}].matrix",
                f"Job '{job.name}' has a matrix object with no axes defined."
            ))
            continue
        axis_names = set(job.matrix.axes.keys())
        for entry in job.matrix.include:
            unknown = set(entry.keys()) - axis_names
            if unknown:
                issues.append(ValidationIssue(
                    "warning", f"jobs[{i}].matrix.include",
                    f"Job '{job.name}' matrix 'include' entry references axes not in the matrix: {unknown}"
                ))
        for entry in job.matrix.exclude:
            unknown = set(entry.keys()) - axis_names
            if unknown:
                issues.append(ValidationIssue(
                    "warning", f"jobs[{i}].matrix.exclude",
                    f"Job '{job.name}' matrix 'exclude' entry references axes not in the matrix: {unknown}"
                ))
    return issues


def _check_conditions(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    for i, job in enumerate(pipeline.jobs):
        if job.condition is not None and not job.condition.expression.strip():
            issues.append(ValidationIssue(
                "error", f"jobs[{i}].condition",
                f"Job '{job.name}' has a Condition object but an empty 'expression'. "
                f"The raw expression must always be populated when a Condition exists."
            ))
        for si, step in enumerate(job.steps):
            if step.condition is not None and not step.condition.expression.strip():
                issues.append(ValidationIssue(
                    "error", f"jobs[{i}].steps[{si}].condition",
                    f"Step '{step.name}' in job '{job.name}' has a Condition object "
                    f"but an empty 'expression'."
                ))
    return issues


def _check_secret_and_env_scopes(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    names = _job_names(pipeline)

    def _check_scoped(items, kind: str):
        for i, item in enumerate(items):
            if item.scope == SecretScope.PIPELINE:
                continue
            if not item.scope_ref:
                issues.append(ValidationIssue(
                    "error", f"{kind}[{i}]",
                    f"'{item.name}' has scope '{item.scope.value}' but no scope_ref "
                    f"to say which job/step it belongs to."
                ))
                continue
            job_part = item.scope_ref.split(".")[0]
            if job_part not in names:
                issues.append(ValidationIssue(
                    "error", f"{kind}[{i}]",
                    f"'{item.name}' scope_ref points to job '{job_part}', which does not exist."
                ))

    _check_scoped(pipeline.secrets, "secrets")
    _check_scoped(pipeline.environment_variables, "environment_variables")
    return issues


def _check_triggers(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    for i, trigger in enumerate(pipeline.triggers):
        if trigger.type == TriggerType.SCHEDULE and not trigger.schedule:
            issues.append(ValidationIssue(
                "error", f"triggers[{i}].schedule",
                "Trigger type is SCHEDULE but no cron 'schedule' string is set."
            ))
        if trigger.type == TriggerType.WORKFLOW_RUN and not trigger.source_workflow:
            issues.append(ValidationIssue(
                "error", f"triggers[{i}].source_workflow",
                "Trigger type is WORKFLOW_RUN but no 'source_workflow' is set."
            ))
        if not trigger.raw.strip():
            issues.append(ValidationIssue(
                "warning", f"triggers[{i}].raw",
                "Trigger has no 'raw' fragment recorded — reduces traceability for "
                "debugging and for the report's 'limitations' writeup."
            ))
    return issues


def _check_linked_workflows(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    allowed = {"calls", "triggered_by", "includes"}
    for i, lw in enumerate(pipeline.linked_workflows):
        if lw.relationship not in allowed:
            issues.append(ValidationIssue(
                "warning", f"linked_workflows[{i}].relationship",
                f"Relationship '{lw.relationship}' is not one of the expected values {allowed}."
            ))
    return issues


def _check_malformed_workflow_structures(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    if "unrecognized_jobs" in pipeline.raw_extras:
        issues.append(ValidationIssue(
            "error", "jobs",
            "Workflow 'jobs' must be a mapping of job names to job definitions; "
            f"received {type(pipeline.raw_extras['unrecognized_jobs']).__name__}."
        ))
    for i, job in enumerate(pipeline.jobs):
        if "unrecognized_job" in job.raw_extras:
            issues.append(ValidationIssue(
                "error", f"jobs[{i}]",
                f"Job '{job.name}' must be a mapping; received "
                f"{type(job.raw_extras['unrecognized_job']).__name__}."
            ))
    return issues


def _check_non_empty_pipeline(pipeline: Pipeline) -> List[ValidationIssue]:
    issues = []
    if not pipeline.jobs:
        issues.append(ValidationIssue("warning", "jobs", "Pipeline has no jobs at all."))
    if not pipeline.triggers:
        issues.append(ValidationIssue("warning", "triggers", "Pipeline has no triggers at all."))
    return issues
