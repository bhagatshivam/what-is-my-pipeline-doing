"""
evaluation.coverage_check_direct — Tier 1 Method 2: IR-to-output coverage,
built directly from the IR (no hand-authored manifest).

This checks whether Layer 3 (`generators/text_generator.py`) dropped a fact
the parser already extracted into the IR — it is NOT a claim about whether
the parser extracted everything the source YAML contains (that's E1's
`evaluation/fact_scoring.py`'s job, scored against `tests/fixtures/`'s
ground truth separately). "Coverage" here means presence in the generated
text, not exact wording — same principle `evaluation/coverage_check.py`'s
module docstring already states for its manifest-driven counterpart.

Deliberately separate from `evaluation/coverage_check.py` (E2's existing
manifest-driven half): that module stays scoped to its Tier 3/4-foundation
role (non-circular scoring against `evaluation/held_out_workflows/`, see
LIMITATIONS.md). This module is new code alongside it, scoped to the 10
`tests/fixtures/` only, guarded by `evaluation/_path_guard.py`. Function
names use a `_direct` suffix throughout so the two paths are never confused.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import List

from evaluation._path_guard import assert_not_held_out
from generators.text_generator import generate_text
from ir.schema import Pipeline
from parsers.github_actions import GitHubActionsParser


class DirectCoverageOutcome(str, Enum):
    CORRECT = "correct"
    MISSING = "missing"


@dataclass
class DirectCoverageResult:
    fixture: str
    category: str  # "job" | "trigger" | "secret"
    fact_id: str
    outcome: DirectCoverageOutcome
    detail: str = ""


def _job_coverage(fixture: str, pipeline: Pipeline, text: str) -> List[DirectCoverageResult]:
    results = []
    for job in pipeline.jobs:
        # Matches generate_text()'s own literal job-line format
        # (f"{i}. {job.name} — {...}") exactly -- see generators/text_generator.py.
        marker = f"{job.name} —"
        outcome = DirectCoverageOutcome.CORRECT if marker in text else DirectCoverageOutcome.MISSING
        detail = "" if outcome == DirectCoverageOutcome.CORRECT else f"no job line found for {job.name!r}"
        results.append(DirectCoverageResult(fixture, "job", job.name, outcome, detail))
    return results


def _secret_coverage(fixture: str, pipeline: Pipeline, text: str) -> List[DirectCoverageResult]:
    results = []
    for secret in pipeline.secrets:
        marker = f"- {secret.name}"
        outcome = DirectCoverageOutcome.CORRECT if marker in text else DirectCoverageOutcome.MISSING
        detail = "" if outcome == DirectCoverageOutcome.CORRECT else f"no secret line found for {secret.name!r}"
        results.append(DirectCoverageResult(fixture, "secret", secret.name, outcome, detail))
    return results


def _trigger_coverage(fixture: str, pipeline: Pipeline, text: str) -> List[DirectCoverageResult]:
    # Trigger has no unique name field (unlike Job/Secret), so a per-trigger
    # presence check isn't expressible the same way. Coverage, not exact
    # wording: count the "- " bullet lines actually present under the
    # WHEN IT RUNS section header (renamed from TRIGGERS, Phase 7.5) and
    # compare to len(pipeline.triggers) -- this catches a silently dropped
    # or duplicated trigger without hardcoding a copy of text_generator.py's
    # private per-type phrase wording (which would drift out of sync as
    # that wording evolves).
    if not pipeline.triggers:
        return []
    lines = text.splitlines()
    if "WHEN IT RUNS" not in lines:
        return [DirectCoverageResult(
            fixture, "trigger", "triggers", DirectCoverageOutcome.MISSING,
            "no WHEN IT RUNS section found in generated text",
        )]
    start = lines.index("WHEN IT RUNS") + 1
    count = 0
    for line in lines[start:]:
        if line == "" or not line.startswith("- "):
            break
        count += 1
    expected = len(pipeline.triggers)
    outcome = DirectCoverageOutcome.CORRECT if count == expected else DirectCoverageOutcome.MISSING
    detail = "" if outcome == DirectCoverageOutcome.CORRECT else f"expected {expected} trigger line(s), found {count}"
    return [DirectCoverageResult(fixture, "trigger", "triggers", outcome, detail)]


def score_coverage_direct(fixture: str, pipeline: Pipeline, text: str) -> List[DirectCoverageResult]:
    """Pure scoring against an already-parsed Pipeline and already-generated
    text -- no file I/O, so this is testable against a hand-built Pipeline
    without needing a real fixture file."""
    return (
        _job_coverage(fixture, pipeline, text)
        + _trigger_coverage(fixture, pipeline, text)
        + _secret_coverage(fixture, pipeline, text)
    )


def score_workflow_coverage_direct(fixture_path: str) -> List[DirectCoverageResult]:
    assert_not_held_out(fixture_path)
    pipeline = GitHubActionsParser().parse(fixture_path)
    text = generate_text(pipeline)
    return score_coverage_direct(os.path.basename(fixture_path), pipeline, text)
