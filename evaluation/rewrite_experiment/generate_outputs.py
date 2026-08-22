"""
evaluation.rewrite_experiment.generate_outputs — bounded, time-boxed
experiment (branch `experiment/beautify-rewrite-prompts`, never merged to
main) testing whether the LLM beautification layer can do a fuller
rewrite of the deterministic fact sheet -- not just prepend a short
overview -- while still passing a fact-coverage check as strict as
Tier 4's.

NOT part of the live Tier 4 evaluation. Does not write to
`evaluation/tier4_scoring/` or `evaluation/tier4_checklists/`, does not
run `evaluation/llm_condition_scoring.py`, and does not touch
`llm/gemini_provider.py`'s real `SYSTEM_PROMPT` or any other part of
main's actual generation path -- this module imports `llm.gemini_provider`
read-only and reuses its already-existing `_generate_once`/
`_build_user_prompt` helpers (the low-level plumbing that module's own
docstring says exists precisely so a caller can supply a different
`system_instruction` without going through `GeminiProvider._call_once`'s
fixed IR-fact-rewriting contract).

Fact sheet generation (`generate_text`) is identical, unmodified code to
what Tier 4 and the real pipeline use -- same one fact sheet per pipeline
feeds all 3 candidates.

Candidate 0 is the control: the real `SYSTEM_PROMPT` verbatim. Candidates
1 and 2 are experimental full-rewrite prompts (structured and narrative).

Run via: `python3 -m evaluation.rewrite_experiment.generate_outputs`
(from repo root). Makes real, billed Gemini API calls -- 3 candidates x
2 pipelines = 6 calls, up to 12 if any single call needs its one retry.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from generators.text_generator import generate_text
from ir.validate import validate_or_raise
from llm.gemini_provider import GeminiProvider
from llm.gemini_provider import SYSTEM_PROMPT as CONTROL_SYSTEM_PROMPT
from llm.gemini_provider import _build_user_prompt, _generate_once
from parsers.github_actions import GitHubActionsParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

HELD_OUT_DIR = os.path.join(REPO_ROOT, "evaluation", "held_out_workflows")
OUTPUT_DIR = os.path.join(REPO_ROOT, "evaluation", "rewrite_experiment", "outputs")

PIPELINES = ["httpie_code_style", "nextjs_build_and_test"]

CANDIDATE_1_PROMPT = """You are a technical writer producing documentation for a CI/CD pipeline.
You will be given a structured, plain-text FACT SHEET that was extracted
and validated by a separate deterministic program -- not by you. Every
fact in it is already correct and complete for this task.

Your job is to rewrite the ENTIRE fact sheet into a well-organized,
readable document for a developer who has never seen this pipeline
before -- not just a short summary sitting above the original, but a
full replacement written in your own words, organized under clear
section headings.

Use these section headings, in this order, and cover every fact from
the fact sheet under the appropriate one (skip a heading entirely if
the fact sheet has nothing for it): Overview, When It Runs, What
Happens, Dependencies, Secrets & Configuration.

Rules:
- Do not add any fact, number, name, condition, or claim that is not
  already present in the fact sheet below.
- Do not infer, guess, or speculate about intent, security
  implications, or behaviour beyond what the fact sheet states.
- Do not omit a single trigger, job, dependency, environment variable,
  secret, or linked workflow listed in the fact sheet -- every one must
  appear somewhere in your rewrite.
- Write in clear prose within each section -- you do not need to
  preserve the fact sheet's exact bullet format, but do not drop
  information for the sake of brevity.
- Do not include YAML or code blocks.
- If you are unsure how to rewrite the fact sheet safely, respond with
  exactly: NO_REWRITE
"""

CANDIDATE_2_PROMPT = """You are a technical writer producing documentation for a CI/CD pipeline.
You will be given a structured, plain-text FACT SHEET that was extracted
and validated by a separate deterministic program -- not by you. Every
fact in it is already correct and complete for this task.

Your job is to rewrite the fact sheet into a single, well-organized
narrative walkthrough for a developer who has never seen this pipeline
before -- as if you were personally explaining how it works, in the
most natural and readable order, not necessarily the fact sheet's own
order. Organize it however best serves a reader trying to understand
the pipeline quickly, using headings and short paragraphs.

Rules:
- Do not add any fact, number, name, condition, or claim that is not
  already present in the fact sheet below.
- Do not infer, guess, or speculate about intent, security
  implications, or behaviour beyond what the fact sheet states.
- Do not omit a single trigger, job, dependency, environment variable,
  secret, or linked workflow listed in the fact sheet -- every one must
  appear somewhere in your rewrite, even if you choose a different
  organization than the fact sheet's own section order.
- Do not include YAML or code blocks.
- If you are unsure how to rewrite the fact sheet safely, respond with
  exactly: NO_REWRITE
"""

CANDIDATES = {
    0: CONTROL_SYSTEM_PROMPT,
    1: CANDIDATE_1_PROMPT,
    2: CANDIDATE_2_PROMPT,
}

_FAILURE_SENTINELS = {"NO_REWRITE", "NO_OVERVIEW"}

# Bump timeout only for nextjs_build_and_test's two full-rewrite candidates
# (1 and 2) -- same reasoning as evaluation/naive_baseline.py's
# NAIVE_TIMEOUT_S: these prompts ask for a fuller rewrite (more output
# tokens) of the largest fact sheet in this experiment's set, not a
# general API issue. Candidate 0 (short 2-4 paragraph control) and the
# small httpie_code_style pipeline keep the provider's own default.
LARGE_REWRITE_TIMEOUT_S = 60.0


def _timeout_for(pipeline_stem: str, candidate_id: int, default_timeout_s: float) -> float:
    if pipeline_stem == "nextjs_build_and_test" and candidate_id in (1, 2):
        return LARGE_REWRITE_TIMEOUT_S
    return default_timeout_s


def _call_with_one_retry(client, model: str, temperature: float, timeout_s: float,
                          system_instruction: str, user_content: str,
                          label: str) -> Tuple[Optional[str], int, Optional[str]]:
    """Mirrors llm.base.LLMProvider.beautify()'s retry contract (1 retry,
    empty/sentinel response counts as failure) without going through
    beautify() itself, since beautify()'s fallback (return structured_text
    unchanged) would defeat the point of scoring a *rewrite*. Returns
    (text_or_None, attempts_made, last_error)."""
    last_error = None
    for attempt in range(1, 3):
        try:
            response = _generate_once(client, model, temperature, timeout_s,
                                       system_instruction, user_content)
            text = (response.text or "").strip()
            if text and text not in _FAILURE_SENTINELS:
                return text, attempt, None
            last_error = f"unusable response: {text!r}"
        except Exception as exc:  # noqa: BLE001 -- experiment script, log and retry/report
            last_error = f"{type(exc).__name__}: {exc}"
        print(f"  [{label}] attempt {attempt} failed: {last_error}", file=sys.stderr)
    return None, 2, last_error


def main() -> None:
    provider = GeminiProvider()
    if not provider.is_available():
        print("GEMINI_API_KEY not configured -- aborting.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for stem in PIPELINES:
        yaml_path = os.path.join(HELD_OUT_DIR, f"{stem}.yml")
        pipeline = GitHubActionsParser().parse(yaml_path)
        warnings = validate_or_raise(pipeline)
        for warning in warnings:
            print(warning, file=sys.stderr)
        structured_text = generate_text(pipeline)

        fact_sheet_path = Path(OUTPUT_DIR) / f"{stem}.fact_sheet.txt"
        fact_sheet_path.write_text(structured_text, encoding="utf-8")
        print(f"wrote {fact_sheet_path}")

        user_content = _build_user_prompt(structured_text)

        for candidate_id, system_prompt in CANDIDATES.items():
            timeout_s = _timeout_for(stem, candidate_id, provider.timeout_s)
            label = f"{stem}/candidate{candidate_id}"
            start = time.monotonic()
            text, attempts, error = _call_with_one_retry(
                provider._client, provider.model_name, provider.temperature,
                timeout_s, system_prompt, user_content, label,
            )
            elapsed = time.monotonic() - start
            out_path = Path(OUTPUT_DIR) / f"{stem}.candidate{candidate_id}.txt"
            if text is None:
                out_path.write_text(f"[GENERATION FAILED after {attempts} attempt(s)] {error}\n",
                                     encoding="utf-8")
                print(f"  [{label}] FAILED after {attempts} attempt(s): {error}", file=sys.stderr)
            else:
                out_path.write_text(text, encoding="utf-8")
                print(f"  [{label}] wrote {out_path} ({elapsed:.1f}s, {attempts} attempt(s))")


if __name__ == "__main__":
    main()
