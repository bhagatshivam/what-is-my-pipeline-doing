"""
scripts/update_golden_files_multi.py — regenerate tests/golden/multi/*.md
from current generator output, for the real multi-workflow fixtures under
tests/fixtures/multi/.

Manual, deliberate action only — never invoked by the test suite itself
(see tests/test_golden_files_multi.py), mirroring
scripts/update_golden_files.py's existing precedent. Always regenerates
with use_llm=False: the committed golden output must contain no
non-deterministic LLM prose, matching check_repository()'s own rationale.

Usage:
    python scripts/update_golden_files_multi.py
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
FIXTURES_DIR = os.path.join(REPO_ROOT, "tests", "fixtures", "multi")
GOLDEN_DIR = os.path.join(REPO_ROOT, "tests", "golden", "multi")

sys.path.insert(0, REPO_ROOT)

from tool2.multi_pipeline import _build_documentation  # noqa: E402

REAL_MULTI_FIXTURE_REPOS = ["black", "tox", "starlette"]


def main() -> None:
    os.makedirs(GOLDEN_DIR, exist_ok=True)

    # Same portable-relative-path reasoning as update_golden_files.py: chdir
    # scoped to this block, always restored, so each doc's "Source:" line
    # reads as "tests/fixtures/multi/<repo>/.github/workflows", not an
    # invoker-machine-specific absolute path.
    original_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        docs = {
            repo: _build_documentation(os.path.join("tests", "fixtures", "multi", repo), use_llm=False)
            for repo in REAL_MULTI_FIXTURE_REPOS
        }
    finally:
        os.chdir(original_cwd)

    for repo, doc in docs.items():
        golden_path = os.path.join(GOLDEN_DIR, f"{repo}.md")
        with open(golden_path, "w", encoding="utf-8") as f:
            f.write(doc)
        print(f"wrote {golden_path}")


if __name__ == "__main__":
    main()
