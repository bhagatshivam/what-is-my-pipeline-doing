"""
evaluation.error_injection.run_checks — E4: feeds each malformed workflow
YAML in this directory through the actual CLI (subprocess, matching
tests/test_single_pipeline.py's `_run_cli` pattern), records exit code and
stderr, classifies against expectations.yml (pre-registered BEFORE this
script was run), and reports any mismatch loudly.

Usage:
    python -m evaluation.error_injection.run_checks
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, List

import yaml

from evaluation._path_guard import assert_not_held_out

_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_DIR))
_CLI_PATH = os.path.join(_REPO_ROOT, "cli.py")


def _classify(returncode: int, stderr: str) -> str:
    if returncode == 0:
        return "accepts_correctly"
    if returncode in (2, 3):
        return "rejects_correctly"
    return "silently_misrepresents"


def run_one(workflow_path: str, tmp_dir: str) -> Dict[str, Any]:
    assert_not_held_out(workflow_path)
    result = subprocess.run(
        [sys.executable, _CLI_PATH, "tool1", workflow_path],
        cwd=tmp_dir,
        capture_output=True,
        text=True,
    )
    return {
        "exit_code": result.returncode,
        "stderr": result.stderr.strip(),
        "outcome": _classify(result.returncode, result.stderr),
    }


def run_all(tmp_dir: str) -> List[Dict[str, Any]]:
    with open(os.path.join(_DIR, "expectations.yml"), encoding="utf-8") as f:
        expectations = yaml.safe_load(f)

    reports = []
    for filename, expected in expectations.items():
        workflow_path = os.path.join(_DIR, filename)
        actual = run_one(workflow_path, tmp_dir)
        mismatch = (
            actual["outcome"] != expected["outcome"]
            or actual["exit_code"] != expected["exit_code"]
        )
        reports.append({
            "filename": filename,
            "expected": expected,
            "actual": actual,
            "mismatch": mismatch,
        })
    return reports


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        reports = run_all(tmp_dir)

    any_mismatch = False
    for r in reports:
        status = "MISMATCH" if r["mismatch"] else "ok"
        print(f"[{status}] {r['filename']}: expected {r['expected']['outcome']} "
              f"(exit {r['expected']['exit_code']}), got {r['actual']['outcome']} "
              f"(exit {r['actual']['exit_code']})")
        if r["mismatch"]:
            any_mismatch = True
            print(f"    stderr: {r['actual']['stderr']!r}")

    return 1 if any_mismatch else 0


if __name__ == "__main__":
    sys.exit(main())
