"""
Tests for evaluation/error_injection/ (E4): confirms every malformed
workflow YAML in that directory produces the outcome pre-registered in
expectations.yml (written before this suite was run against them --
mirrors EVALUATION_PLAN.md's "commit timestamp is evidence of
pre-registration" discipline). Any mismatch here means the tool's actual
behavior drifted from what was verified during design, which is the real
finding, not a test-harness bug.
"""

import os

from evaluation.error_injection.run_checks import run_all

_EXPECTATIONS_COUNT = 8


def test_all_error_injection_cases_match_pre_registered_expectations(tmp_path):
    reports = run_all(str(tmp_path))
    mismatches = [r for r in reports if r["mismatch"]]
    assert mismatches == [], f"behavior drifted from pre-registered expectations: {mismatches}"
    assert len(reports) == _EXPECTATIONS_COUNT


def test_rejects_correctly_cases_use_exit_code_3():
    eval_dir = os.path.join(os.path.dirname(__file__), "..", "evaluation", "error_injection")
    import yaml
    with open(os.path.join(eval_dir, "expectations.yml"), encoding="utf-8") as f:
        expectations = yaml.safe_load(f)
    for filename, expected in expectations.items():
        if expected["outcome"] == "rejects_correctly":
            assert expected["exit_code"] == 3, f"{filename} expects rejects_correctly but exit_code != 3"


def test_accepts_correctly_case_uses_exit_code_0():
    eval_dir = os.path.join(os.path.dirname(__file__), "..", "evaluation", "error_injection")
    import yaml
    with open(os.path.join(eval_dir, "expectations.yml"), encoding="utf-8") as f:
        expectations = yaml.safe_load(f)
    accepts = [f for f, e in expectations.items() if e["outcome"] == "accepts_correctly"]
    assert accepts == ["unrecognized_trigger_type.yml"]
    assert expectations["unrecognized_trigger_type.yml"]["exit_code"] == 0


def test_no_case_is_silently_misrepresents():
    eval_dir = os.path.join(os.path.dirname(__file__), "..", "evaluation", "error_injection")
    import yaml
    with open(os.path.join(eval_dir, "expectations.yml"), encoding="utf-8") as f:
        expectations = yaml.safe_load(f)
    outcomes = {e["outcome"] for e in expectations.values()}
    assert "silently_misrepresents" not in outcomes
