"""
tests/test_tier4_checklists_not_yet_scored.py — Tier 4 pre-registration
integrity check (EVALUATION_PLAN.md Method 9).

Asserts every evaluation/tier4_checklists/*.checklist.yml fact's three
condition slots are outcome: null -- mechanical proof that no scoring has
happened yet, rather than relying on a manual diff-read to confirm it.

IMPORTANT, read before "fixing" a failure here: this test is only valid
for the window between committing the checklists and actually running
Method 9. The moment real scoring begins and outcome values get filled
in, this test is EXPECTED to start failing -- that failure is the correct,
intended signal that scoring has started, not a bug. Whoever lands the
first real scores must delete or rewrite this test as part of that same
PR (e.g. to assert scored facts are one of correct/missing/incorrect
instead of asserting null) -- see BUILD_PLAN.md Section 6's open item.
"""

import glob
import os

import pytest
import yaml

_CHECKLISTS_DIR = os.path.join(os.path.dirname(__file__), "..", "evaluation", "tier4_checklists")
_CONDITION_KEYS = ("condition_1_deterministic", "condition_2_llm_polished", "condition_3_naive_baseline")


def _checklist_paths():
    return sorted(glob.glob(os.path.join(_CHECKLISTS_DIR, "*.checklist.yml")))


def test_ten_checklists_exist():
    paths = _checklist_paths()
    assert len(paths) == 10, f"expected 10 checklists, found {len(paths)}: {paths}"


@pytest.mark.parametrize("checklist_path", _checklist_paths())
def test_checklist_all_condition_slots_are_null(checklist_path):
    with open(checklist_path, encoding="utf-8") as f:
        checklist = yaml.safe_load(f)

    assert checklist["scoring"] == "manual"
    facts = checklist["facts"]
    assert facts, f"{checklist_path} has no facts"

    for fact in facts:
        for key in _CONDITION_KEYS:
            assert key in fact, f"{checklist_path}: fact {fact['fact_id']} missing {key}"
            slot = fact[key]
            assert slot["outcome"] is None, (
                f"{checklist_path}: fact {fact['fact_id']}'s {key} has a non-null outcome "
                f"({slot['outcome']!r}) -- Method 9 scoring appears to have started. If that's "
                "correct and intentional, this test must be deleted/rewritten as part of that "
                "same change, not left failing (see this file's module docstring)."
            )


def test_grand_total_fact_count_across_all_ten():
    total = 0
    for path in _checklist_paths():
        with open(path, encoding="utf-8") as f:
            total += len(yaml.safe_load(f)["facts"])
    assert total == 201, f"expected 201 total pre-registered facts across all 10 checklists, got {total}"
