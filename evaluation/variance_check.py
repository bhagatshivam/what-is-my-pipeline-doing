"""evaluation.variance_check — Tier 1 Method 4: determinism/variance of LLM
output across repeated runs.

Answers the question raised by PR 2's readability results
(`evaluation/readability_results.md`): are the per-fixture FKGL swings
between deterministic and LLM-polished text real repeatable effects of
each fixture's content, or run-to-run noise on a single call? Runs N
repeated `beautify()` calls at the tool's production temperature (0.2)
against a small set of `tests/fixtures/`, scores each response's FKGL,
and reports mean/std-dev/min/max/range plus a plain-English
interpretation from a fixed rule.

Deliberately narrow scope decisions, all approved in the PR 4 plan:
- FKGL only (not all three readability metrics) -- PR 2 already identified
  FKGL as the interesting variance signal; per-metric variance for Reading
  Ease / Gunning Fog is a marginal-information 3x-table cost. Both metrics
  are still recoverable after the fact via `SampleResult.text` without
  spending fresh quota (see below).
- Pure stochastic variance at the tool's production temperature -- not a
  temperature sweep. `GeminiProvider.__init__` accepts a temperature
  constructor arg, but `beautify()` has no per-call knob and this module
  does not add one; a temperature sweep, if ever wanted, is a separate
  future change.
- Raw prose stored per repeat, not just the float. Live API calls are
  rate-limited and finite; textstat recomputation is free once you have
  the text. If Reading Ease / Gunning Fog variance, or a different
  interpretation-threshold rule, ever becomes worth checking, that reruns
  against the stored text -- not fresh quota.

Guarded by `evaluation/_path_guard.py`, scoped to `tests/fixtures/` only.
Live LLM calls only from `scripts/run_variance_check.py` when run with a
real `GEMINI_API_KEY` -- pytest coverage uses a fake `LLMProvider`, no
live call ever from a test or CI (matching PR 2/`tests/conftest.py`).
"""

from __future__ import annotations

import os
import statistics
from dataclasses import dataclass, field
from typing import List, Optional

import textstat

from evaluation._path_guard import assert_not_held_out
from generators.text_generator import generate_text
from llm import get_default_provider
from llm.base import LLMProvider
from parsers.github_actions import GitHubActionsParser


@dataclass
class SampleResult:
    """One successful `beautify()` response's raw prose plus its FKGL.
    Storing the text (not just the score) lets a later reader recompute
    Reading Ease / Gunning Fog / any other metric without spending fresh
    quota on a re-run -- textstat is free, live API calls are not."""
    text: str
    fkgl: float


@dataclass
class VarianceResult:
    fixture: str
    deterministic_fkgl: float
    samples: List[SampleResult] = field(default_factory=list)
    mean: Optional[float] = None
    std_dev: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    range: Optional[float] = None
    interpretation: str = ""
    errors: List[str] = field(default_factory=list)


# Fixed interpretation rule -- stated explicitly in module docstring, script
# output header, and the results file, so nothing about how a result's plain-
# English label was derived is hidden.
_INTERPRETATION_RULES: List[tuple] = [
    (1.0, "essentially deterministic (range < 1 grade level)"),
    (3.0, "moderate drift (range 1-3 grade levels)"),
    (float("inf"), "large drift (range >= 3 grade levels)"),
]


def _interpret(sample_range: float) -> str:
    for threshold, label in _INTERPRETATION_RULES:
        if sample_range < threshold:
            return label
    return _INTERPRETATION_RULES[-1][1]


def score_workflow_variance(
    fixture_path: str,
    repeats: int,
    provider: Optional[LLMProvider] = None,
) -> VarianceResult:
    """Repeat `beautify()` `repeats` times against a single fixture, score
    each response's FKGL, and summarise. `provider` defaults to
    `get_default_provider()` so tests can inject a fake; callers making
    live calls (i.e. `scripts/run_variance_check.py`) let it default.

    A `_call_once` failure on any single repeat is recorded in `errors`
    (as `f"{type(exc).__name__}: {exc}"`) and does not stop the loop --
    matches `llm/base.py`'s own broad-except contract (any provider
    failure must fall back, never crash the caller), and matches PR 2's
    error-surfacing pattern. If all repeats fail, `samples` is empty and
    all numeric summary fields stay `None`.
    """
    assert_not_held_out(fixture_path)
    pipeline = GitHubActionsParser().parse(fixture_path)
    structured_text = generate_text(pipeline)
    fixture_name = os.path.basename(fixture_path)
    deterministic_fkgl = textstat.flesch_kincaid_grade(structured_text)

    result = VarianceResult(fixture=fixture_name, deterministic_fkgl=deterministic_fkgl)
    active_provider = provider if provider is not None else get_default_provider()

    if active_provider is None:
        result.errors.append("GEMINI_API_KEY not set")
        return result

    for _ in range(repeats):
        llm_result = active_provider.beautify(structured_text, pipeline)
        if llm_result.used_fallback:
            result.errors.append(llm_result.error or "unknown fallback reason")
            continue
        result.samples.append(SampleResult(
            text=llm_result.text,
            fkgl=textstat.flesch_kincaid_grade(llm_result.text),
        ))

    fkgls = [s.fkgl for s in result.samples]
    if fkgls:
        result.mean = statistics.mean(fkgls)
        result.min = min(fkgls)
        result.max = max(fkgls)
        result.range = result.max - result.min
        result.std_dev = statistics.stdev(fkgls) if len(fkgls) > 1 else 0.0
        result.interpretation = _interpret(result.range)

    return result
