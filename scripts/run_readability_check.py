"""
scripts/run_readability_check.py — Tier 1 readability check (Method 5):
scores all 10 real tests/fixtures/ and writes evaluation/readability_results.md.

Manual, deliberate action only — never invoked by the test suite itself
(see tests/test_evaluation_readability.py, which only exercises the
deterministic path). Deterministic (Layer 3a) scores are always computed;
the LLM-polished column is the headline comparison but only reflects a
genuine live measurement if GEMINI_API_KEY is set in the environment this
script runs in — otherwise each row is clearly labeled "llm_fallback" and
duplicates the deterministic score, not a distinct data point. Making a
live LLM call costs real API usage; that only happens here, never in CI
or the pytest suite.

Usage:
    python scripts/run_readability_check.py
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
RESULTS_PATH = os.path.join(REPO_ROOT, "evaluation", "readability_results.md")

sys.path.insert(0, REPO_ROOT)

from evaluation.readability import (  # noqa: E402
    ReadabilityResult,
    score_workflow_readability,
    score_workflow_readability_llm,
)

REAL_FIXTURE_FILES = [
    "checkout_check_dist.yml",
    "eslint_ci.yml",
    "fastapi_test.yml",
    "flask_tests.yml",
    "node_test_linux.yml",
    "pandas_unit_tests.yml",
    "pytorch_lint.yml",
    "rust_ci.yml",
    "setup_python_test.yml",
    "upload_artifact_test.yml",
]

_CAVEAT = (
    "Caveat: Flesch-Kincaid-family formulas assume connected prose. The "
    "'deterministic' column scores generators/text_generator.py's structured "
    "header/bullet-fragment output, not prose -- treat it as a rough density "
    "proxy, not a literal reading grade level. The 'llm' column is the "
    "headline comparison (does LLM polish help or hurt readability), but "
    "only reflects a genuine live measurement when source=llm_live; "
    "source=llm_fallback means either no GEMINI_API_KEY was available or the "
    "live call itself failed -- the 'LLM error' column distinguishes the two "
    "('GEMINI_API_KEY not set' vs. the real exception), and the row duplicates "
    "the deterministic score either way."
)


def _format_row(det: ReadabilityResult, llm: ReadabilityResult) -> str:
    error_cell = llm.error if llm.error else ""
    return (
        f"| {det.fixture} "
        f"| {det.flesch_kincaid_grade:.2f} | {det.flesch_reading_ease:.2f} | {det.gunning_fog:.2f} "
        f"| {llm.source} "
        f"| {llm.flesch_kincaid_grade:.2f} | {llm.flesch_reading_ease:.2f} | {llm.gunning_fog:.2f} "
        f"| {error_cell} |"
    )


def main() -> None:
    original_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        rows = []
        for filename in REAL_FIXTURE_FILES:
            fixture_path = os.path.join("tests", "fixtures", filename)
            det = score_workflow_readability(fixture_path)
            llm = score_workflow_readability_llm(fixture_path)
            rows.append(_format_row(det, llm))
            error_suffix = f" [{llm.error}]" if llm.error else ""
            print(f"{filename}: deterministic FKGL={det.flesch_kincaid_grade:.2f}, "
                  f"llm({llm.source}) FKGL={llm.flesch_kincaid_grade:.2f}{error_suffix}")
    finally:
        os.chdir(original_cwd)

    lines = [
        "# Readability results (Tier 1, Method 5)",
        "",
        _CAVEAT,
        "",
        "| Fixture | Det. FKGL | Det. Reading Ease | Det. Gunning Fog "
        "| LLM source | LLM FKGL | LLM Reading Ease | LLM Gunning Fog | LLM error |",
        "|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
    ]
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
