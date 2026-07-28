"""
scripts/run_coverage_check_direct.py — Tier 1 Method 2 (IR-to-output
coverage, manifest-free): scores all 10 real tests/fixtures/ and writes
evaluation/coverage_check_direct_results.md.

Manual, deliberate action only — never invoked by the test suite itself
(see tests/test_evaluation_coverage_check_direct.py for the pytest
regression). "Coverage" means every job/trigger/secret the parser
extracted into the IR appears somewhere in generators/text_generator.py's
output -- not a claim about whether the parser extracted everything the
source YAML contains (that's evaluation/fact_scoring.py's E1, a separate
concern).

Usage:
    python scripts/run_coverage_check_direct.py
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
RESULTS_PATH = os.path.join(REPO_ROOT, "evaluation", "coverage_check_direct_results.md")

sys.path.insert(0, REPO_ROOT)

from evaluation.coverage_check_direct import (  # noqa: E402
    DirectCoverageOutcome,
    score_workflow_coverage_direct,
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
    "IR-to-output coverage: does every job/trigger/secret the parser extracted "
    "into the IR appear somewhere in generators/text_generator.py's output? "
    "This is a Layer 3 completeness check (did the generator drop what the "
    "parser extracted), not a claim that the parser extracted everything the "
    "source YAML contains -- see evaluation/fact_scoring.py (E1) for that. "
    "Coverage means presence, not exact wording."
)


def main() -> None:
    original_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        rows = []
        total_correct = 0
        total_missing = 0
        for filename in REAL_FIXTURE_FILES:
            fixture_path = os.path.join("tests", "fixtures", filename)
            results = score_workflow_coverage_direct(fixture_path)
            correct = sum(1 for r in results if r.outcome == DirectCoverageOutcome.CORRECT)
            missing = [r for r in results if r.outcome == DirectCoverageOutcome.MISSING]
            total_correct += correct
            total_missing += len(missing)
            missing_detail = "; ".join(f"{r.category}:{r.fact_id} ({r.detail})" for r in missing)
            rows.append(f"| {filename} | {correct} | {len(missing)} | {missing_detail} |")
            print(f"{filename}: {correct} correct, {len(missing)} missing")
    finally:
        os.chdir(original_cwd)

    lines = [
        "# Coverage check results, manifest-free (Tier 1, Method 2)",
        "",
        _CAVEAT,
        "",
        f"Totals across all 10 fixtures: {total_correct} correct, {total_missing} missing.",
        "",
        "| Fixture | Correct | Missing | Missing detail |",
        "|---|---|---|---|",
        *rows,
        "",
    ]
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
