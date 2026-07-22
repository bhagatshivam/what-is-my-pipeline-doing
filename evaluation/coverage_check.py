"""
evaluation.coverage_check — E2 (deterministic half): does every manifest
fact appear in Tool 1's generated TEXT output? Coverage, not exact wording.

Strengthens this module's original one-line scope (IR-field presence in
output) to check against independently-authored manifest facts instead —
this also catches a fact the parser silently dropped before it reached the
IR, which an IR-driven scan could never detect (that fact would never even
be in the IR for an IR-driven scan to look for). The LLM-output half
(scoring the tool's fully polished output and the naive-raw-YAML baseline,
per EVALUATION_PLAN.md Method 9's three conditions) is deferred until
Phase 5 exists -- see `score_llm_conditions` below.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List

from evaluation.fact_scoring import load_manifest
from generators.text_generator import generate_text
from parsers.github_actions import GitHubActionsParser


class CoverageOutcome(str, Enum):
    CORRECT = "correct"                      # fact appears in the generated text
    MISSING = "missing"                      # fact does not appear at all
    UNSUPPORTED_CLAIM = "unsupported_claim"   # reserved for Phase 5: text claims
                                              # something the manifest says is false --
                                              # not checkable pre-Phase-5, since today's
                                              # text generator never fabricates facts not
                                              # in the IR (by its own module docstring's
                                              # "never guesses at intent" contract)


@dataclass
class CoverageResult:
    fact_id: str
    category: str
    outcome: CoverageOutcome
    detail: str = ""


def _job_line(text: str, job_name: str) -> str | None:
    """The single line beginning "N. {job_name} —", or None if absent."""
    marker = f" {job_name} —"
    for line in text.splitlines():
        if line.split(". ", 1)[-1].startswith(f"{job_name} —") or marker in line:
            return line
    return None


def _check_trigger_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    branches = expected.get("branches", [])
    missing = [b for b in branches if b not in text]
    if missing:
        return CoverageResult(fact["fact_id"], fact["category"], CoverageOutcome.MISSING,
                               f"branch(es) not found in text: {missing}")
    return CoverageResult(fact["fact_id"], fact["category"], CoverageOutcome.CORRECT)


def _check_job_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    line = _job_line(text, expected["name"])
    outcome = CoverageOutcome.CORRECT if line else CoverageOutcome.MISSING
    return CoverageResult(fact["fact_id"], fact["category"], outcome,
                           "" if line else f"no job line found for {expected['name']!r}")


def _check_dependency_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    line = _job_line(text, expected["job"])
    if line is None:
        return CoverageResult(fact["fact_id"], fact["category"], CoverageOutcome.MISSING,
                               f"no job line found for {expected['job']!r}")
    if "after" not in line or expected["depends_on"] not in line:
        return CoverageResult(fact["fact_id"], fact["category"], CoverageOutcome.MISSING,
                               f"job line for {expected['job']!r} doesn't mention "
                               f"depending on {expected['depends_on']!r}: {line!r}")
    return CoverageResult(fact["fact_id"], fact["category"], CoverageOutcome.CORRECT)


def _check_step_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    needle = f"- {expected['step_name']}"
    outcome = CoverageOutcome.CORRECT if needle in text else CoverageOutcome.MISSING
    return CoverageResult(fact["fact_id"], fact["category"], outcome,
                           "" if outcome == CoverageOutcome.CORRECT else
                           "not found -- note: per-job step listing is capped at 10 with an "
                           "overflow line, so a real step past the cap is expected to be "
                           "MISSING here, not a scorer bug")


def _check_condition_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    outcome = CoverageOutcome.CORRECT if expected["expression_substring"] in text else CoverageOutcome.MISSING
    return CoverageResult(fact["fact_id"], fact["category"], outcome)


def _check_matrix_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    line = _job_line(text, expected["job"])
    if line is None:
        return CoverageResult(fact["fact_id"], fact["category"], CoverageOutcome.MISSING,
                               f"no job line found for {expected['job']!r}")
    outcome = CoverageOutcome.CORRECT if "matrix:" in line else CoverageOutcome.MISSING
    return CoverageResult(fact["fact_id"], fact["category"], outcome)


def _check_secret_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    needle = f"- {expected['name']}"
    outcome = CoverageOutcome.CORRECT if needle in text else CoverageOutcome.MISSING
    return CoverageResult(fact["fact_id"], fact["category"], outcome)


def _check_env_var_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    # generators/text_generator.py has no environment-variable section at
    # all today -- confirmed by reading its generate_text() in full (only
    # TRIGGERS/JOBS/LINKED WORKFLOWS/SECRETS REQUIRED sections exist). This
    # is a genuine, real finding about the tool's current output
    # completeness, not a bug in this scorer -- every environment_variable
    # fact is expected to be MISSING until a future generator change adds
    # such a section.
    return CoverageResult(fact["fact_id"], fact["category"], CoverageOutcome.MISSING,
                           "generators/text_generator.py has no environment-variable "
                           "section -- expected MISSING, not a scorer defect")


def _check_linked_workflow_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    outcome = CoverageOutcome.CORRECT if expected["target"] in text else CoverageOutcome.MISSING
    return CoverageResult(fact["fact_id"], fact["category"], outcome)


def _check_permissions_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    if expected["scope"] == "workflow":
        outcome = CoverageOutcome.CORRECT if "Permissions:" in text else CoverageOutcome.MISSING
    else:
        line = _job_line(text, expected["job"])
        outcome = CoverageOutcome.CORRECT if (line and "permissions:" in line) else CoverageOutcome.MISSING
    return CoverageResult(fact["fact_id"], fact["category"], outcome)


def _check_concurrency_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    if expected["scope"] == "workflow":
        outcome = CoverageOutcome.CORRECT if "Concurrency:" in text else CoverageOutcome.MISSING
    else:
        line = _job_line(text, expected["job"])
        outcome = CoverageOutcome.CORRECT if (line and "concurrency:" in line) else CoverageOutcome.MISSING
    return CoverageResult(fact["fact_id"], fact["category"], outcome)


def _check_deployment_environment_coverage(fact: Dict[str, Any], text: str) -> CoverageResult:
    expected = fact["expected"]
    line = _job_line(text, expected["job"])
    outcome = CoverageOutcome.CORRECT if (line and "deployment environment:" in line) else CoverageOutcome.MISSING
    return CoverageResult(fact["fact_id"], fact["category"], outcome)


_CATEGORY_CHECKERS: Dict[str, Callable[[Dict[str, Any], str], CoverageResult]] = {
    "trigger": _check_trigger_coverage,
    "job": _check_job_coverage,
    "dependency": _check_dependency_coverage,
    "step": _check_step_coverage,
    "condition": _check_condition_coverage,
    "matrix": _check_matrix_coverage,
    "secret": _check_secret_coverage,
    "environment_variable": _check_env_var_coverage,
    "linked_workflow": _check_linked_workflow_coverage,
    "permissions": _check_permissions_coverage,
    "concurrency": _check_concurrency_coverage,
    "deployment_environment": _check_deployment_environment_coverage,
}


def score_coverage(manifest: Dict[str, Any], generated_text: str) -> List[CoverageResult]:
    """Category-specific substring/pattern check against generated_text, mirroring
    fact_scoring.py's per-category dispatch table but checking TEXT presence
    instead of IR field values."""
    results = []
    for fact in manifest["facts"]:
        checker = _CATEGORY_CHECKERS.get(fact["category"])
        if checker is None:
            raise ValueError(f"Unknown fact category: {fact['category']!r} ({fact['fact_id']})")
        results.append(checker(fact, generated_text))
    return results


def score_workflow_coverage(manifest_path: str) -> List[CoverageResult]:
    manifest = load_manifest(manifest_path)
    manifest_dir = os.path.dirname(manifest_path)
    local_file = os.path.join(manifest_dir, manifest["local_file"])
    pipeline = GitHubActionsParser().parse(local_file)
    text = generate_text(pipeline)
    return score_coverage(manifest, text)


def aggregate_by_category(results: List[CoverageResult]) -> Dict[str, Dict[str, int]]:
    aggregate: Dict[str, Dict[str, int]] = {}
    for result in results:
        counts = aggregate.setdefault(result.category, {"correct": 0, "missing": 0, "unsupported_claim": 0})
        counts[result.outcome.value] += 1
    return aggregate


def score_llm_conditions(*args, **kwargs):
    """Placeholder for EVALUATION_PLAN.md Method 9's full 3-condition scoring
    (plain text / LLM-polished / naive-raw-YAML baseline) -- raises
    NotImplementedError until Phase 5 exists. Kept here, not deleted, so the
    reusable manifest-driven scoring plumbing above doesn't need to change
    when Phase 5 lands -- only this function gets implemented."""
    raise NotImplementedError("Phase 5 (LLM layer) does not exist yet")
