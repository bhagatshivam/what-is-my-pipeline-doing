"""
tests/test_tier4_checklists_scored.py — Tier 4 scoring integrity check
(EVALUATION_PLAN.md Method 9).

Asserts every evaluation/tier4_checklists/*.checklist.yml fact's three
condition slots carry a real outcome (present/missing/false) -- mechanical
proof that Method 9 scoring has actually been completed, rather than relying
on a manual diff-read to confirm it.

This file supersedes tests/test_tier4_checklists_not_yet_scored.py, which
asserted the opposite (outcome: null everywhere) during the pre-registration
window before scoring began. That window is over: outcome values were
transcribed from evaluation/tier4_scoring/*.scoring.md in the PR that
renamed this file, per the retirement plan recorded in this file's own
former docstring and in BUILD_PLAN.md Section 6.
"""

import glob
import os

import pytest
import yaml

_CHECKLISTS_DIR = os.path.join(os.path.dirname(__file__), "..", "evaluation", "tier4_checklists")
_CONDITION_KEYS = ("condition_1_deterministic", "condition_2_llm_polished", "condition_3_naive_baseline")
_VALID_OUTCOMES = ("present", "missing", "false")


def _checklist_paths():
    return sorted(glob.glob(os.path.join(_CHECKLISTS_DIR, "*.checklist.yml")))


def test_ten_checklists_exist():
    paths = _checklist_paths()
    assert len(paths) == 10, f"expected 10 checklists, found {len(paths)}: {paths}"


@pytest.mark.parametrize("checklist_path", _checklist_paths())
def test_checklist_all_condition_slots_are_scored(checklist_path):
    with open(checklist_path, encoding="utf-8") as f:
        checklist = yaml.safe_load(f)

    assert checklist["scoring"] == "manual"
    facts = checklist["facts"]
    assert facts, f"{checklist_path} has no facts"

    for fact in facts:
        for key in _CONDITION_KEYS:
            assert key in fact, f"{checklist_path}: fact {fact['fact_id']} missing {key}"
            slot = fact[key]
            assert slot["outcome"] in _VALID_OUTCOMES, (
                f"{checklist_path}: fact {fact['fact_id']}'s {key} has outcome "
                f"{slot['outcome']!r}, expected one of {_VALID_OUTCOMES}"
            )
            if slot["outcome"] != "present":
                assert slot["detail"], (
                    f"{checklist_path}: fact {fact['fact_id']}'s {key} is "
                    f"{slot['outcome']!r} but has an empty detail field"
                )


def test_grand_total_fact_count_across_all_ten():
    total = 0
    for path in _checklist_paths():
        with open(path, encoding="utf-8") as f:
            total += len(yaml.safe_load(f)["facts"])
    assert total == 201, f"expected 201 total pre-registered facts across all 10 checklists, got {total}"
