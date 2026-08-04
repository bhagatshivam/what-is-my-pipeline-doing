"""
evaluation.llm_condition_scoring — Tier 4 Method 9 (EVALUATION_PLAN.md):
generates the three pre-registered conditions for a held-out pipeline and
writes a blind-labeled scoring document, for MANUAL scoring against the
pre-registered fact checklist (evaluation/tier4_checklists/*.checklist.yml).

Does NOT open, read, or reference any *.checklist.yml content -- the
checklist stays frozen and unseen by this script; only the pipeline's own
filename stem is used to name the output file that pairs with it, for the
human scorer to open separately. Does NOT score anything itself -- no
automated fact-checking, no hallucination detection. That's the
pre-registered protocol's whole point.

Condition 2's scored output is the FULL assembled
`tool1.single_pipeline.generate_documentation(pipeline, llm_result=result)`
document (title + Overview + fact sheet + diagram) -- not
`beautify(...).text` in isolation. EVALUATION_PLAN.md's own existing
bias-mitigation note ("condition 2's tool output is visually distinctive
-- Mermaid fences, the 'JOBS (in order)' heading style") already
describes the full document, not the isolated prose -- those elements
don't exist in `beautify()`'s output alone. Same one `beautify()` call
either way; only which text gets scored changes.

Makes real, billed Gemini API calls (conditions 2 and 3) -- unlike every
other evaluation/ script in this project, this is not free or offline.
Run deliberately, not in an automated test/CI loop; never invoked by
pytest.

Randomization (per-pipeline condition order in the blind scoring doc) is
unseeded -- fresh system randomness each run, since this is bias
mitigation for a human scorer, not something that needs the
reproducibility deterministic document generation elsewhere in this
project requires.

Conditions 2 and 3 each carry their underlying `LLMResult.used_fallback`/
`.error` through to `ConditionOutput` (condition 1 never sets these -- it
makes no LLM call, so it can't fall back). When `used_fallback` is True,
`_render_scoring_document` prepends a clearly-flagged warning (including
the real `.error` string) to that condition's section instead of silently
rendering fallback/raw output as if it were a genuine generated result.
The warning wording is deliberately architecture-agnostic -- it never says
whether it's condition 2 or 3 that failed, since either can, so blinding
stays intact.
"""

from __future__ import annotations

import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from evaluation.naive_baseline import generate_naive_baseline
from generators.text_generator import generate_text
from ir.validate import validate_or_raise
from llm.gemini_provider import GeminiProvider
from parsers.github_actions import GitHubActionsParser
from tool1.single_pipeline import _log_llm_call, generate_documentation

# No sys.path manipulation here -- this module is import-side-effect-free.
# Run it via `python -m evaluation.llm_condition_scoring` (from the repo
# root, or with the repo root already on PYTHONPATH), not by executing
# this file directly -- a direct `python evaluation/llm_condition_scoring.py`
# would put this file's own directory on sys.path[0], not the repo root,
# and these absolute-package imports would fail to resolve.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

HELD_OUT_DIR = os.path.join(REPO_ROOT, "evaluation", "held_out_workflows")
OUTPUT_DIR = os.path.join(REPO_ROOT, "evaluation", "tier4_scoring")

# Deliberately only these 3 for this sanity check -- the other 7 held-out
# pipelines are a separate, later task, only after this run's mechanics
# and file format are confirmed to actually work for manual scoring.
PIPELINES_FOR_THIS_SANITY_CHECK = [
    "pre_commit_main",
    "httpie_code_style",
    "nextjs_build_and_test",
]

_CONDITION_LABELS = {
    1: "Plain structured text (no LLM)",
    2: "Full tool output (structured text -> LLM-polished)",
    3: "Naive baseline (raw YAML -> LLM)",
}


@dataclass
class ConditionOutput:
    condition_number: int   # 1, 2, or 3 -- the real identity, kept out of the scoring doc
    text: str                 # what actually gets shown, blind-labeled, in the scoring doc
    used_fallback: bool = False   # True => text is NOT a real generated result (see below)
    error: Optional[str] = None   # LLMResult.error, only meaningful when used_fallback is True


def _generate_condition_1(pipeline) -> ConditionOutput:
    # No LLM call at all -- can't fall back, used_fallback stays False.
    return ConditionOutput(condition_number=1, text=generate_text(pipeline))


def _generate_condition_2(pipeline, provider: GeminiProvider, yaml_path: str) -> ConditionOutput:
    structured_text = generate_text(pipeline)
    result = provider.beautify(structured_text, pipeline)
    _log_llm_call(yaml_path, pipeline.name, result)
    # Scored as the full assembled document (title + Overview + fact sheet
    # + diagram), not result.text in isolation -- see module docstring for
    # why. Same one beautify() call either way; only which text gets
    # handed to the scoring doc changes. Note: when result.used_fallback
    # is True, beautify()'s fallback is the ORIGINAL structured_text
    # unchanged (llm/base.py's documented contract), so full_document here
    # still reflects that fallback text, not a real LLM rewrite.
    full_document = generate_documentation(pipeline, llm_result=result)
    return ConditionOutput(
        condition_number=2, text=full_document,
        used_fallback=result.used_fallback, error=result.error,
    )


def _generate_condition_3(yaml_path: str, provider: GeminiProvider) -> ConditionOutput:
    # generate_naive_baseline already calls _log_llm_call internally --
    # no separate logging call needed here (see its own module docstring).
    result = generate_naive_baseline(yaml_path, provider=provider)
    return ConditionOutput(
        condition_number=3, text=result.text,
        used_fallback=result.used_fallback, error=result.error,
    )


def _render_scoring_document(pipeline_stem: str, blind_ordered: List[ConditionOutput]) -> str:
    labels = "ABC"
    if len(blind_ordered) != len(labels):
        # zip() would otherwise silently truncate/ignore a length mismatch,
        # producing an incomplete scoring doc instead of failing loudly --
        # Tier 4 requires exactly 3 conditions, no more, no fewer.
        raise ValueError(
            f"expected exactly {len(labels)} conditions to render, got {len(blind_ordered)}"
        )
    lines = [
        f"# Tier 4 scoring — {pipeline_stem}",
        "",
        f"Pre-registered checklist: `evaluation/tier4_checklists/{pipeline_stem}.checklist.yml` "
        "(open separately -- not duplicated here).",
        "",
        "Score each condition fact-by-fact against the checklist: present / missing / false "
        "(hallucination). Presentation order below is randomized per EVALUATION_PLAN.md's Method 9 "
        f"bias mitigation -- the mapping back to conditions 1/2/3 is in "
        f"`{pipeline_stem}.answer_key.md`, intentionally kept out of this file.",
        "",
        "---",
        "",
    ]
    for label, condition in zip(labels, blind_ordered):
        lines.append(f"## Condition {label}")
        lines.append("")
        if condition.used_fallback:
            # Deliberately architecture-agnostic wording -- conditions 2
            # and 3 can both fall back, condition 1 never can, so this
            # alone doesn't leak which of the three this is. Flags the
            # text below as not a real generated result, so it isn't
            # scored as though it were one.
            lines.append(
                "> **⚠ GENERATION FAILED -- this condition's tool call did not "
                "succeed. The text below is fallback/unprocessed output, not a real "
                "generated result. Score it as unavailable/failed, not as a "
                "legitimate output of its underlying method.**"
            )
            lines.append(f"> Error: {condition.error}")
            lines.append("")
        lines.append(condition.text.strip())
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _render_answer_key(pipeline_stem: str, blind_ordered: List[ConditionOutput],
                        model: str, temperature: float) -> str:
    labels = "ABC"
    if len(blind_ordered) != len(labels):
        raise ValueError(
            f"expected exactly {len(labels)} conditions to render, got {len(blind_ordered)}"
        )
    lines = [
        f"# Tier 4 answer key — {pipeline_stem}",
        "",
        f"DO NOT OPEN until scoring of `{pipeline_stem}.scoring.md` is complete.",
        "",
    ]
    for label, condition in zip(labels, blind_ordered):
        lines.append(
            f"- Condition {label} = Condition {condition.condition_number} "
            f"({_CONDITION_LABELS[condition.condition_number]})"
        )
    lines += [
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Model: {model} (temperature {temperature})",
    ]
    return "\n".join(lines)


def generate_tier4_scoring_materials(pipeline_stem: str, provider: GeminiProvider) -> None:
    yaml_path = os.path.join(HELD_OUT_DIR, f"{pipeline_stem}.yml")
    pipeline = GitHubActionsParser().parse(yaml_path)
    # Same fail-closed boundary as tool1/tool2: raises on errors. Warnings
    # (non-fatal) are printed to stderr at generation time, same convention
    # as tool1/single_pipeline.py -- never surfaced in the scoring doc or
    # answer key themselves, which stay clean for blind manual scoring.
    warnings = validate_or_raise(pipeline)
    for warning in warnings:
        print(warning, file=sys.stderr)

    conditions = [
        _generate_condition_1(pipeline),
        _generate_condition_2(pipeline, provider, yaml_path),
        _generate_condition_3(yaml_path, provider),
    ]
    blind_ordered = conditions[:]
    random.shuffle(blind_ordered)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    scoring_path = Path(OUTPUT_DIR) / f"{pipeline_stem}.scoring.md"
    answer_key_path = Path(OUTPUT_DIR) / f"{pipeline_stem}.answer_key.md"
    scoring_path.write_text(_render_scoring_document(pipeline_stem, blind_ordered), encoding="utf-8")
    answer_key_path.write_text(
        _render_answer_key(pipeline_stem, blind_ordered, provider.model_name, provider.temperature),
        encoding="utf-8",
    )
    print(f"wrote {scoring_path}")
    print(f"wrote {answer_key_path}")


def main() -> None:
    provider = GeminiProvider()
    if not provider.is_available():
        print(
            "GEMINI_API_KEY not configured -- aborting before running a "
            "fallback-only, wasted-effort pass. Set a real key and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

    for stem in PIPELINES_FOR_THIS_SANITY_CHECK:
        generate_tier4_scoring_materials(stem, provider=provider)


if __name__ == "__main__":
    main()
