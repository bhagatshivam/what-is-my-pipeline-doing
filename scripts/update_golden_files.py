"""
scripts/update_golden_files.py — regenerate tests/golden/*.md from current
generator output, for all 10 real fixtures.

Manual, deliberate action only — never invoked by the test suite itself
(see tests/test_golden_files.py). Run this after a change to
parsers/github_actions.py, generators/text_generator.py,
generators/mermaid_generator.py, or tool1/single_pipeline.py that you've
confirmed produces correct new output, then review the diff and commit
the result.

Usage:
    python scripts/update_golden_files.py
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
GOLDEN_DIR = os.path.join(REPO_ROOT, "tests", "golden")

sys.path.insert(0, REPO_ROOT)

from parsers.github_actions import GitHubActionsParser
from tool1.single_pipeline import generate_documentation

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


def main() -> None:
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    parser = GitHubActionsParser()

    # Parse with a repo-root-relative path (chdir scoped to this block, always
    # restored) so the "Source:" line embedded in each golden file reads as a
    # portable "tests/fixtures/<file>.yml" — not an invoker-machine-specific
    # absolute path, which would make the committed golden files non-portable.
    original_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        docs = {
            filename: generate_documentation(parser.parse(os.path.join("tests", "fixtures", filename)))
            for filename in REAL_FIXTURE_FILES
        }
    finally:
        os.chdir(original_cwd)

    for filename, doc in docs.items():
        stem = filename.rsplit(".", 1)[0]
        golden_path = os.path.join(GOLDEN_DIR, f"{stem}.md")
        with open(golden_path, "w", encoding="utf-8") as f:
            f.write(doc)
        print(f"wrote {golden_path}")


if __name__ == "__main__":
    main()
