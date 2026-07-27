"""evaluation.readability — Tier 1: Flesch-Kincaid (or similar) readability
metrics on generated text.

Secondary/diagnostic measure, not the headline result: these formulas
assume connected prose (real sentences), and `generators/text_generator.py`'s
deterministic output is structured header/bullet-fragment text, not prose.
Scores on that text are a rough proxy for how dense the fact-dump reads,
not a literal reading grade level — see LIMITATIONS.md. The headline
comparison is deterministic-vs-LLM-polished-prose readability, which only
reflects a genuine live measurement when `GEMINI_API_KEY` is configured;
otherwise the LLM-side score is clearly labeled as a fallback, not a
distinct data point.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import textstat

from evaluation._path_guard import assert_not_held_out
from generators.text_generator import generate_text
from llm import get_default_provider
from parsers.github_actions import GitHubActionsParser


@dataclass
class ReadabilityResult:
    fixture: str
    source: str  # "deterministic" | "llm_live" | "llm_fallback"
    flesch_kincaid_grade: float
    flesch_reading_ease: float
    gunning_fog: float


def _compute_scores(text: str) -> tuple[float, float, float]:
    return (
        textstat.flesch_kincaid_grade(text),
        textstat.flesch_reading_ease(text),
        textstat.gunning_fog(text),
    )


def score_workflow_readability(fixture_path: str) -> ReadabilityResult:
    """Deterministic Layer 3a readability — always available, no LLM call.

    Secondary/diagnostic: see module docstring's caveat about scoring
    structured fact-dump text with prose-oriented formulas.
    """
    assert_not_held_out(fixture_path)
    pipeline = GitHubActionsParser().parse(fixture_path)
    text = generate_text(pipeline)
    fkgl, ease, fog = _compute_scores(text)
    return ReadabilityResult(
        fixture=os.path.basename(fixture_path),
        source="deterministic",
        flesch_kincaid_grade=fkgl,
        flesch_reading_ease=ease,
        gunning_fog=fog,
    )


def score_workflow_readability_llm(fixture_path: str) -> ReadabilityResult:
    """LLM-polished-prose readability — the headline comparison, when a
    real GEMINI_API_KEY is configured.

    Falls back to scoring the same deterministic text (labeled
    `source="llm_fallback"`, never silently conflated with a live score)
    if no provider is configured or the provider itself falls back
    internally. Never makes an LLM call from a test — callers in
    tests/ must not invoke this function.
    """
    assert_not_held_out(fixture_path)
    pipeline = GitHubActionsParser().parse(fixture_path)
    structured_text = generate_text(pipeline)
    fixture_name = os.path.basename(fixture_path)

    provider = get_default_provider()
    if provider is None:
        fkgl, ease, fog = _compute_scores(structured_text)
        return ReadabilityResult(
            fixture=fixture_name,
            source="llm_fallback",
            flesch_kincaid_grade=fkgl,
            flesch_reading_ease=ease,
            gunning_fog=fog,
        )

    result = provider.beautify(structured_text, pipeline)
    source = "llm_fallback" if result.used_fallback else "llm_live"
    fkgl, ease, fog = _compute_scores(result.text)
    return ReadabilityResult(
        fixture=fixture_name,
        source=source,
        flesch_kincaid_grade=fkgl,
        flesch_reading_ease=ease,
        gunning_fog=fog,
    )
