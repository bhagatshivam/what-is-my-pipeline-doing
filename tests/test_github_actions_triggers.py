"""
Tests for the first slice of parsers/github_actions.py: `on:` trigger parsing.

Covers both the 10 real-world fixtures in tests/fixtures/ (which only
exercise push/pull_request/schedule/workflow_dispatch in practice) and the
remaining `on:` shapes the task requires support for but that none of the
fixtures happen to use (bare string, list form, release, workflow_call,
workflow_run, inputs) via small hand-written YAML snippets.
"""

import glob
import os

import pytest
import yaml

from ir.schema import TriggerType
from parsers.github_actions import (
    GitHubActionsParser,
    _GitHubActionsSafeLoader,
    _parse_triggers,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
ALL_FIXTURES = sorted(glob.glob(os.path.join(FIXTURES_DIR, "*.yml")))


def _load_on_block(yaml_snippet: str):
    data = yaml.load(yaml_snippet, Loader=_GitHubActionsSafeLoader)
    return data.get("on")


# ---------------------------------------------------------------------------
# All 10 real fixtures: must parse without raising, produce at least one
# trigger, and never silently hit an unmapped/unexpected event type.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_path", ALL_FIXTURES)
def test_fixture_triggers_parse_without_unexpected_events(fixture_path):
    pipeline = GitHubActionsParser().parse(fixture_path)
    assert pipeline.triggers, f"{fixture_path} produced no triggers at all"

    for trigger in pipeline.triggers:
        if trigger.type == TriggerType.OTHER:
            # Per the task: don't guess a mapping, surface it instead.
            print(
                f"[UNMAPPED EVENT] {fixture_path} hit TriggerType.OTHER — raw: {trigger.raw!r}"
            )
        assert trigger.raw, f"{fixture_path}: trigger {trigger.type} has an empty raw fragment"


# Expected (type, branches) pairs per fixture, in `on:` block order — locks in
# the exact behaviour verified by hand against each fixture's real `on:` block.
EXPECTED_PUSH_PULL_BRANCHES = {
    "checkout_check_dist.yml": [
        (TriggerType.PUSH, ["main"]),
        (TriggerType.PULL_REQUEST, []),
        (TriggerType.MANUAL, []),
    ],
    "eslint_ci.yml": [
        (TriggerType.PUSH, ["main"]),
        (TriggerType.PULL_REQUEST, ["main"]),
    ],
    "flask_tests.yml": [
        (TriggerType.PULL_REQUEST, []),
        (TriggerType.PUSH, ["main", "stable"]),
    ],
    "pandas_unit_tests.yml": [
        (TriggerType.PUSH, ["main", "3.0.x"]),
        (TriggerType.PULL_REQUEST, ["main", "3.0.x"]),
    ],
    "rust_ci.yml": [
        (TriggerType.PUSH, ["automation/bors/auto", "automation/bors/try", "try-perf"]),
        (TriggerType.PULL_REQUEST, ["**"]),
    ],
    "upload_artifact_test.yml": [
        (TriggerType.PUSH, ["main"]),
        (TriggerType.PULL_REQUEST, []),
    ],
}


@pytest.mark.parametrize("filename,expected", EXPECTED_PUSH_PULL_BRANCHES.items())
def test_fixture_trigger_types_and_branches(filename, expected):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    actual = [(t.type, t.branches) for t in pipeline.triggers]
    assert actual == expected


def test_fastapi_schedule_and_push():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "fastapi_test.yml"))
    types = [t.type for t in pipeline.triggers]
    assert types == [TriggerType.PUSH, TriggerType.PULL_REQUEST, TriggerType.SCHEDULE]
    assert pipeline.triggers[0].branches == ["master"]
    assert pipeline.triggers[2].schedule == "0 0 * * 1"


def test_setup_python_schedule_and_manual():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "setup_python_test.yml"))
    types = [t.type for t in pipeline.triggers]
    assert types == [
        TriggerType.PUSH,
        TriggerType.PULL_REQUEST,
        TriggerType.SCHEDULE,
        TriggerType.MANUAL,
    ]
    assert pipeline.triggers[2].schedule == "30 3 * * *"
    assert pipeline.triggers[3].inputs == []


def test_pytorch_lint_tags_and_branches_ignore():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "pytorch_lint.yml"))
    push = next(t for t in pipeline.triggers if t.type == TriggerType.PUSH)
    assert push.branches == ["main", "release/*", "landchecks/*"]
    assert push.tags == ["ciflow/pull/*", "ciflow/trunk/*"]


def test_node_paths_ignore_and_dropped_types_filter_stays_in_raw():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "node_test_linux.yml"))
    pr = next(t for t in pipeline.triggers if t.type == TriggerType.PULL_REQUEST)
    assert ".mailmap" in pr.paths_ignore
    # `types:` isn't a structured Trigger field (see LIMITATION comment in the
    # parser) — but it must still be present in `raw`, not silently dropped.
    assert "types" in pr.raw


# ---------------------------------------------------------------------------
# `on:` shapes none of the 10 fixtures happen to use, tested directly against
# _parse_triggers via small hand-written snippets.
# ---------------------------------------------------------------------------

def test_bare_string_form():
    triggers = _parse_triggers(_load_on_block("on: push"))
    assert [t.type for t in triggers] == [TriggerType.PUSH]


def test_list_form():
    triggers = _parse_triggers(_load_on_block("on: [push, pull_request]"))
    assert [t.type for t in triggers] == [TriggerType.PUSH, TriggerType.PULL_REQUEST]


def test_release():
    on_block = _load_on_block("on:\n  release:\n    types: [published]\n")
    triggers = _parse_triggers(on_block)
    assert len(triggers) == 1
    assert triggers[0].type == TriggerType.RELEASE
    assert "published" in triggers[0].raw


def test_workflow_call_with_inputs():
    on_block = _load_on_block(
        "on:\n"
        "  workflow_call:\n"
        "    inputs:\n"
        "      release_tag:\n"
        "        required: true\n"
        "        type: string\n"
    )
    triggers = _parse_triggers(on_block)
    assert len(triggers) == 1
    assert triggers[0].type == TriggerType.WORKFLOW_CALL
    assert triggers[0].inputs == [
        {"name": "release_tag", "required": True, "default": None, "type": "string"}
    ]


def test_workflow_run_with_source_workflow():
    on_block = _load_on_block(
        "on:\n"
        "  workflow_run:\n"
        "    workflows: [Build]\n"
        "    types: [completed]\n"
    )
    triggers = _parse_triggers(on_block)
    assert len(triggers) == 1
    assert triggers[0].type == TriggerType.WORKFLOW_RUN
    assert triggers[0].source_workflow == "Build"


def test_workflow_dispatch_with_inputs():
    on_block = _load_on_block(
        "on:\n"
        "  workflow_dispatch:\n"
        "    inputs:\n"
        "      environment:\n"
        "        required: true\n"
        "        default: staging\n"
        "        type: choice\n"
    )
    triggers = _parse_triggers(on_block)
    assert len(triggers) == 1
    assert triggers[0].type == TriggerType.MANUAL
    assert triggers[0].inputs == [
        {"name": "environment", "required": True, "default": "staging", "type": "choice"}
    ]


def test_multiple_schedule_entries_become_separate_triggers():
    on_block = _load_on_block(
        "on:\n"
        "  schedule:\n"
        "    - cron: '0 0 * * *'\n"
        "    - cron: '0 12 * * *'\n"
    )
    triggers = _parse_triggers(on_block)
    assert [t.type for t in triggers] == [TriggerType.SCHEDULE, TriggerType.SCHEDULE]
    assert [t.schedule for t in triggers] == ["0 0 * * *", "0 12 * * *"]


def test_unknown_event_type_maps_to_other_and_preserves_raw():
    on_block = _load_on_block("on:\n  issues:\n    types: [opened]\n")
    triggers = _parse_triggers(on_block)
    assert len(triggers) == 1
    assert triggers[0].type == TriggerType.OTHER
    assert "issues" in triggers[0].raw


def test_empty_on_block_returns_no_triggers():
    assert _parse_triggers(None) == []


# ---------------------------------------------------------------------------
# Contract from parsers/base.py: parse() must return a Pipeline with the
# `on:` gotcha handled correctly (PyYAML's YAML-1.1 bool resolver would
# otherwise turn `on:` into the boolean key True) and jobs deliberately empty
# for now.
# ---------------------------------------------------------------------------

def test_parse_returns_jobs_with_steps_but_no_needs_matrix_yet():
    # jobs: name/runs-on and steps: name/type/value/with_args parsing landed
    # in later passes (see tests/test_github_actions_jobs.py and
    # tests/test_github_actions_steps.py); needs/matrix are still
    # unimplemented, so every Job keeps those dataclass defaults for now.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "eslint_ci.yml"))
    assert len(pipeline.jobs) == 6
    assert all(job.dependencies == [] and job.matrix is None for job in pipeline.jobs)
    assert pipeline.name == "CI"
