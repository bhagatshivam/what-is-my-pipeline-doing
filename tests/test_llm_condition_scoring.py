"""
Tests for evaluation/llm_condition_scoring.py — Tier 4 Method 9's
blind-labeling/rendering logic only. No real API calls, no held-out
pipeline generation (that requires a real GEMINI_API_KEY and is
deliberately not exercised in the automated test suite — this module is
a manual, deliberately-run script, never invoked by pytest/CI).
"""

from evaluation.llm_condition_scoring import (
    ConditionOutput,
    _render_answer_key,
    _render_scoring_document,
)


def _sample_conditions():
    # Deliberately no "Condition N" text in the fake bodies themselves --
    # that would be a self-inflicted collision with the blind-labeling
    # assertions below, not something real generate_text()/beautify()
    # output would ever say.
    return [
        ConditionOutput(condition_number=2, text="This workflow runs on pushes and pull requests."),
        ConditionOutput(condition_number=1, text="AT A GLANCE\nThis workflow runs on pushes."),
        ConditionOutput(condition_number=3, text="This pipeline appears to run tests on every push."),
    ]


def test_render_scoring_document_labels_are_blind():
    doc = _render_scoring_document("example_pipeline", _sample_conditions())

    assert "## Condition A" in doc
    assert "## Condition B" in doc
    assert "## Condition C" in doc
    # No real condition number/identity anywhere in the scoring doc itself.
    assert "Condition 1" not in doc
    assert "Condition 2" not in doc
    assert "Condition 3" not in doc
    assert "answer_key" in doc  # tells the reader where the mapping lives, without revealing it


def test_render_scoring_document_contains_all_three_texts_in_order():
    conditions = _sample_conditions()
    doc = _render_scoring_document("example_pipeline", conditions)

    # Order in the doc must match the order passed in (the caller does the
    # shuffling; this function renders whatever order it's given).
    idx_a = doc.index("## Condition A")
    idx_b = doc.index("## Condition B")
    idx_c = doc.index("## Condition C")
    assert idx_a < idx_b < idx_c

    assert conditions[0].text in doc
    assert conditions[1].text in doc
    assert conditions[2].text in doc


def test_render_scoring_document_references_the_right_checklist_filename():
    doc = _render_scoring_document("pre_commit_main", _sample_conditions())
    assert "evaluation/tier4_checklists/pre_commit_main.checklist.yml" in doc


def test_render_answer_key_maps_labels_back_to_real_condition_numbers():
    conditions = _sample_conditions()  # A=2, B=1, C=3, in this order
    key = _render_answer_key("example_pipeline", conditions, model="gemini-2.5-flash", temperature=0.2)

    assert "Condition A = Condition 2" in key
    assert "Condition B = Condition 1" in key
    assert "Condition C = Condition 3" in key
    assert "gemini-2.5-flash" in key
    assert "0.2" in key
    assert "DO NOT OPEN" in key
    assert "pre_commit_main" not in key  # this key is for example_pipeline, not a different one


def test_render_answer_key_does_not_leak_condition_text():
    # The answer key is only the mapping + metadata -- never the
    # generated prose itself (that lives only in the scoring doc).
    conditions = _sample_conditions()
    key = _render_answer_key("example_pipeline", conditions, model="gemini-2.5-flash", temperature=0.2)

    for condition in conditions:
        assert condition.text not in key


def test_render_scoring_document_flags_fallback_without_revealing_condition_number():
    conditions = _sample_conditions()
    conditions[2].used_fallback = True  # condition_number=3 in _sample_conditions' order
    conditions[2].error = "empty response"
    doc = _render_scoring_document("example_pipeline", conditions)

    assert "GENERATION FAILED" in doc
    assert "empty response" in doc
    # The failed condition's own text (raw fallback content) must still be
    # shown, just clearly flagged -- never silently dropped.
    assert conditions[2].text in doc
    # Still no real condition-number identity leaked by the warning itself.
    assert "Condition 1" not in doc
    assert "Condition 2" not in doc
    assert "Condition 3" not in doc


def test_render_scoring_document_no_warning_when_no_fallback():
    doc = _render_scoring_document("example_pipeline", _sample_conditions())
    assert "GENERATION FAILED" not in doc
