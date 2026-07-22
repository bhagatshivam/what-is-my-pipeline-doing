"""
evaluation.fact_scoring — E1: checks a held-out workflow's hand-authored
fact manifest against this project's actual parsed IR (Pipeline/Job).

Manifests are never generated from this parser's own output (see
evaluation/held_out_workflows/*.manifest.yml and
evaluation/scorer_self_test_manifests/*.manifest.yml for the authoring
discipline) -- this module only SCORES: does the parser correctly extract
what a human reader already independently confirmed is there?

`score_workflow()` scores the RAW parsed IR, deliberately BEFORE
`ir.validate.validate_or_raise()` runs. E1 tests parser/extraction fidelity
specifically -- a separate concern from E4 (evaluation/error_injection/),
which tests validation/rejection behavior on deliberately malformed input.
This is a deliberate boundary between the two scorers, not an oversight:
E1's held-out workflows are expected to be structurally valid (they're real
production CI files), so there's nothing for validate_or_raise() to reject
in the first place -- inserting a validation step here would just add a
redundant no-op for every held-out workflow, while conflating "did the
parser extract this fact correctly" with "did the validator run," which
E4 already covers on its own dedicated malformed-input set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List

import yaml

from ir.schema import Job, Pipeline
from parsers.github_actions import GitHubActionsParser


class FactOutcome(str, Enum):
    CORRECT = "correct"
    MISSING = "missing"
    INCORRECT = "incorrect"


@dataclass
class FactResult:
    fact_id: str
    category: str
    outcome: FactOutcome
    detail: str = ""


def load_manifest(manifest_path: str) -> Dict[str, Any]:
    with open(manifest_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _find_job(pipeline: Pipeline, name: str) -> Job | None:
    return next((j for j in pipeline.jobs if j.name == name), None)


def _resolve_secret_scope_ref(pipeline: Pipeline, scope_ref: str) -> tuple[str, str | None]:
    """Mirrors text_generator._secret_line's STEP scope_ref decoding:
    "job_key.step_index" -> (job_key, real step name), or (job_key, None)
    if it doesn't resolve."""
    job_key, _, index_str = scope_ref.partition(".")
    job = _find_job(pipeline, job_key)
    step_index = int(index_str) if index_str.isdigit() else None
    if job is not None and step_index is not None and 0 <= step_index < len(job.steps):
        return job_key, job.steps[step_index].name
    return job_key, None


def _check_trigger_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    candidates = [t for t in pipeline.triggers if t.type.value == expected["type"]]
    if not candidates:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"no trigger of type {expected['type']!r}")
    for t in candidates:
        mismatches = []
        for field_name in ("branches", "branches_ignore", "tags", "tags_ignore", "paths", "paths_ignore"):
            if field_name in expected and set(getattr(t, field_name)) != set(expected[field_name]):
                mismatches.append(field_name)
        if "schedule" in expected and t.schedule != expected["schedule"]:
            mismatches.append("schedule")
        if not mismatches:
            return FactResult(fact_id, category, FactOutcome.CORRECT)
    return FactResult(fact_id, category, FactOutcome.INCORRECT,
                       f"trigger(s) of type {expected['type']!r} found but none matched expected fields")


def _check_job_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    job = _find_job(pipeline, expected["name"])
    if job is None:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"no job named {expected['name']!r} in parsed IR")
    if "runner" in expected and job.runner != expected["runner"]:
        return FactResult(fact_id, category, FactOutcome.INCORRECT,
                           f"expected runner {expected['runner']!r}, got {job.runner!r}")
    return FactResult(fact_id, category, FactOutcome.CORRECT)


def _check_dependency_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    job = _find_job(pipeline, expected["job"])
    if job is None:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"no job named {expected['job']!r} in parsed IR")
    if expected["depends_on"] not in job.dependencies:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"job {expected['job']!r} does not depend on {expected['depends_on']!r} "
                           f"(actual dependencies: {job.dependencies})")
    return FactResult(fact_id, category, FactOutcome.CORRECT)


def _check_step_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    job = _find_job(pipeline, expected["job"])
    if job is None:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"no job named {expected['job']!r} in parsed IR")
    if not any(s.name == expected["step_name"] for s in job.steps):
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"job {expected['job']!r} has no step named {expected['step_name']!r}")
    return FactResult(fact_id, category, FactOutcome.CORRECT)


def _check_condition_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    job = _find_job(pipeline, expected["job"])
    if job is None:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"no job named {expected['job']!r} in parsed IR")
    if job.condition is None:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"job {expected['job']!r} has no condition")
    if expected["expression_substring"] not in job.condition.expression:
        return FactResult(fact_id, category, FactOutcome.INCORRECT,
                           f"expected substring {expected['expression_substring']!r} not in "
                           f"{job.condition.expression!r}")
    return FactResult(fact_id, category, FactOutcome.CORRECT)


def _check_matrix_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    job = _find_job(pipeline, expected["job"])
    if job is None:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"no job named {expected['job']!r} in parsed IR")
    if job.matrix is None:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"job {expected['job']!r} has no matrix")
    if "axes" in expected:
        if set(job.matrix.axes.keys()) != set(expected["axes"]):
            return FactResult(fact_id, category, FactOutcome.INCORRECT,
                               f"expected axes {expected['axes']!r}, got {list(job.matrix.axes.keys())!r}")
        return FactResult(fact_id, category, FactOutcome.CORRECT)
    if "axis" in expected:
        axis = expected["axis"]
        if axis not in job.matrix.axes:
            return FactResult(fact_id, category, FactOutcome.INCORRECT,
                               f"axis {axis!r} not in matrix axes {list(job.matrix.axes.keys())!r}")
        if len(job.matrix.axes[axis]) != expected["value_count"]:
            return FactResult(fact_id, category, FactOutcome.INCORRECT,
                               f"expected {expected['value_count']} values for axis {axis!r}, "
                               f"got {len(job.matrix.axes[axis])}")
        return FactResult(fact_id, category, FactOutcome.CORRECT)
    return FactResult(fact_id, category, FactOutcome.CORRECT)


def _check_secret_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    candidates = [s for s in pipeline.secrets if s.name == expected["name"]
                  and s.scope.value == expected["scope"]]
    if not candidates:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"no secret {expected['name']!r} with scope {expected['scope']!r}")
    if expected["scope"] == "pipeline":
        return FactResult(fact_id, category, FactOutcome.CORRECT)
    if expected["scope"] == "job":
        if any(s.scope_ref == expected["scope_job"] for s in candidates):
            return FactResult(fact_id, category, FactOutcome.CORRECT)
        return FactResult(fact_id, category, FactOutcome.INCORRECT,
                           f"expected scope_ref {expected['scope_job']!r}, "
                           f"got {[s.scope_ref for s in candidates]!r}")
    if expected["scope"] == "step":
        for s in candidates:
            job_key, step_name = _resolve_secret_scope_ref(pipeline, s.scope_ref or "")
            if job_key == expected["scope_job"] and step_name == expected["scope_step"]:
                return FactResult(fact_id, category, FactOutcome.CORRECT)
        return FactResult(fact_id, category, FactOutcome.INCORRECT,
                           f"no candidate resolved to job {expected['scope_job']!r}, "
                           f"step {expected['scope_step']!r}")
    return FactResult(fact_id, category, FactOutcome.INCORRECT, f"unknown scope {expected['scope']!r}")


def _check_env_var_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    if expected["scope"] == "pipeline":
        match = next((e for e in pipeline.environment_variables
                      if e.name == expected["name"] and e.scope.value == "pipeline"), None)
        if match is None:
            return FactResult(fact_id, category, FactOutcome.MISSING,
                               f"no pipeline-scope env var {expected['name']!r}")
        if "value" in expected and match.value != expected["value"]:
            return FactResult(fact_id, category, FactOutcome.INCORRECT,
                               f"expected value {expected['value']!r}, got {match.value!r}")
        return FactResult(fact_id, category, FactOutcome.CORRECT)
    if expected["scope"] == "job":
        job = _find_job(pipeline, expected["scope_job"])
        if job is None:
            return FactResult(fact_id, category, FactOutcome.MISSING,
                               f"no job named {expected['scope_job']!r} in parsed IR")
        if expected["name"] not in job.environment:
            return FactResult(fact_id, category, FactOutcome.MISSING,
                               f"job {expected['scope_job']!r} has no env var {expected['name']!r}")
        if "value" in expected and job.environment[expected["name"]] != expected["value"]:
            return FactResult(fact_id, category, FactOutcome.INCORRECT,
                               f"expected value {expected['value']!r}, "
                               f"got {job.environment[expected['name']]!r}")
        return FactResult(fact_id, category, FactOutcome.CORRECT)
    return FactResult(fact_id, category, FactOutcome.INCORRECT, f"unknown scope {expected['scope']!r}")


def _check_linked_workflow_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    match = any(lw.target == expected["target"] and lw.relationship == expected["relationship"]
                for lw in pipeline.linked_workflows)
    if not match:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"no linked workflow {expected['relationship']!r} {expected['target']!r}")
    return FactResult(fact_id, category, FactOutcome.CORRECT)


def _check_permissions_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    if expected["scope"] == "workflow":
        actual = pipeline.permissions
    else:
        job = _find_job(pipeline, expected["job"])
        if job is None:
            return FactResult(fact_id, category, FactOutcome.MISSING,
                               f"no job named {expected['job']!r} in parsed IR")
        actual = job.permissions
    if actual is None:
        return FactResult(fact_id, category, FactOutcome.MISSING, "permissions not set in parsed IR")
    if actual != expected["value"]:
        return FactResult(fact_id, category, FactOutcome.INCORRECT,
                           f"expected {expected['value']!r}, got {actual!r}")
    return FactResult(fact_id, category, FactOutcome.CORRECT)


def _check_concurrency_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    if expected["scope"] == "workflow":
        actual = pipeline.concurrency
    else:
        job = _find_job(pipeline, expected["job"])
        if job is None:
            return FactResult(fact_id, category, FactOutcome.MISSING,
                               f"no job named {expected['job']!r} in parsed IR")
        actual = job.concurrency
    if actual is None:
        return FactResult(fact_id, category, FactOutcome.MISSING, "concurrency not set in parsed IR")
    if "has_cancel_in_progress" in expected and bool(actual.get("cancel-in-progress")) != expected["has_cancel_in_progress"]:
        return FactResult(fact_id, category, FactOutcome.INCORRECT,
                           f"expected cancel-in-progress={expected['has_cancel_in_progress']}, "
                           f"got {actual.get('cancel-in-progress')!r}")
    return FactResult(fact_id, category, FactOutcome.CORRECT)


def _check_deployment_environment_fact(fact: Dict[str, Any], pipeline: Pipeline) -> FactResult:
    expected = fact["expected"]
    fact_id, category = fact["fact_id"], fact["category"]
    job = _find_job(pipeline, expected["job"])
    if job is None:
        return FactResult(fact_id, category, FactOutcome.MISSING,
                           f"no job named {expected['job']!r} in parsed IR")
    is_set = job.deployment_environment is not None
    if is_set != expected["is_set"]:
        return FactResult(fact_id, category, FactOutcome.INCORRECT,
                           f"expected is_set={expected['is_set']}, got {is_set}")
    return FactResult(fact_id, category, FactOutcome.CORRECT)


_CATEGORY_CHECKERS: Dict[str, Callable[[Dict[str, Any], Pipeline], FactResult]] = {
    "trigger": _check_trigger_fact,
    "job": _check_job_fact,
    "dependency": _check_dependency_fact,
    "step": _check_step_fact,
    "condition": _check_condition_fact,
    "matrix": _check_matrix_fact,
    "secret": _check_secret_fact,
    "environment_variable": _check_env_var_fact,
    "linked_workflow": _check_linked_workflow_fact,
    "permissions": _check_permissions_fact,
    "concurrency": _check_concurrency_fact,
    "deployment_environment": _check_deployment_environment_fact,
}


def score_manifest_against_ir(manifest: Dict[str, Any], pipeline: Pipeline) -> List[FactResult]:
    """One category-specific checker per `category` value — see _CATEGORY_CHECKERS."""
    results = []
    for fact in manifest["facts"]:
        checker = _CATEGORY_CHECKERS.get(fact["category"])
        if checker is None:
            raise ValueError(f"Unknown fact category: {fact['category']!r} ({fact['fact_id']})")
        results.append(checker(fact, pipeline))
    return results


def score_workflow(manifest_path: str) -> List[FactResult]:
    manifest = load_manifest(manifest_path)
    manifest_dir = os.path.dirname(manifest_path)
    local_file = os.path.join(manifest_dir, manifest["local_file"])
    pipeline = GitHubActionsParser().parse(local_file)
    return score_manifest_against_ir(manifest, pipeline)


def aggregate_by_category(results: List[FactResult]) -> Dict[str, Dict[str, int]]:
    """category -> {"correct": n, "missing": n, "incorrect": n}"""
    aggregate: Dict[str, Dict[str, int]] = {}
    for result in results:
        counts = aggregate.setdefault(result.category, {"correct": 0, "missing": 0, "incorrect": 0})
        counts[result.outcome.value] += 1
    return aggregate
