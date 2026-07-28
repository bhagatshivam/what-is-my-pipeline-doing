"""
scripts/run_diagram_diff_direct.py — Tier 1 Method 3 (IR-to-diagram
structure check, manifest-free): scores all 10 real tests/fixtures/ and
writes evaluation/diagram_diff_direct_results.md.

Manual, deliberate action only — never invoked by the test suite itself
(see tests/test_evaluation_diagram_diff_direct.py for the pytest
regression). Confirms the Mermaid graph's job nodes and dependency edges
match pipeline.jobs/Job.dependencies exactly -- the job dependency graph
specifically, not trigger-to-job entry edges (same scope as
evaluation/diagram_diff.py's existing manifest-driven E3).

Usage:
    python scripts/run_diagram_diff_direct.py
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
RESULTS_PATH = os.path.join(REPO_ROOT, "evaluation", "diagram_diff_direct_results.md")

sys.path.insert(0, REPO_ROOT)

from evaluation.diagram_diff_direct import score_workflow_diagram_direct  # noqa: E402

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
    "IR-to-diagram structure check: do generators/mermaid_generator.py's job "
    "nodes and dependency edges match pipeline.jobs/Job.dependencies exactly? "
    "Scope is the job dependency graph specifically, not trigger-to-job entry "
    "edges -- same scope decision as evaluation/diagram_diff.py's existing "
    "manifest-driven counterpart."
)


def _format_set(items) -> str:
    return ", ".join(sorted(str(i) for i in items)) if items else "-"


def main() -> None:
    original_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        rows = []
        exact_count = 0
        for filename in REAL_FIXTURE_FILES:
            fixture_path = os.path.join("tests", "fixtures", filename)
            diff = score_workflow_diagram_direct(fixture_path)
            exact_count += int(diff.exact_match)
            rows.append(
                f"| {filename} | {diff.exact_match} "
                f"| {_format_set(diff.missing_nodes)} | {_format_set(diff.extra_nodes)} "
                f"| {_format_set(diff.missing_edges)} | {_format_set(diff.extra_edges)} |"
            )
            print(f"{filename}: exact_match={diff.exact_match}")
    finally:
        os.chdir(original_cwd)

    lines = [
        "# Diagram-structure check results, manifest-free (Tier 1, Method 3)",
        "",
        _CAVEAT,
        "",
        f"Totals: {exact_count}/{len(REAL_FIXTURE_FILES)} fixtures exact match.",
        "",
        "| Fixture | Exact match | Missing nodes | Extra nodes | Missing edges | Extra edges |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ]
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
