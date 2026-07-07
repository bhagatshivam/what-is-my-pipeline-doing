"""
parsers/github_actions.py — GitHub Actions YAML -> ir.schema.Pipeline.

Implemented incrementally per BUILD_PLAN.md Phase 3. This pass only handles
the `on:` trigger block (see `_parse_triggers`). Jobs, steps, `needs`, env
vars, conditions, and matrix strategy are intentionally not implemented yet
— `parse()` currently returns a `Pipeline` with an empty `jobs` list. Later
passes fill those in.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import yaml

from ir.schema import Pipeline, SourcePlatform, Trigger, TriggerType
from parsers.base import BaseParser


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

class _GitHubActionsSafeLoader(yaml.SafeLoader):
    """
    PyYAML's default SafeLoader follows YAML 1.1, whose implicit bool
    resolver treats bare `on`/`off`/`yes`/`no` (any case) as booleans. That
    silently turns a workflow's `on:` trigger key into the boolean `True`
    key instead of the string `"on"`, which breaks every GitHub Actions
    workflow file. This loader narrows the bool resolver to `true`/`false`
    only (YAML 1.2 behaviour, which is what GitHub Actions' own parser
    uses), leaving `on`/`off`/`yes`/`no` as plain strings/keys.
    """


_GitHubActionsSafeLoader.yaml_implicit_resolvers = {
    first_char: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != "tag:yaml.org,2002:bool"
    ]
    for first_char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_GitHubActionsSafeLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def _load_workflow_yaml(file_path: str) -> Dict[str, Any]:
    with open(file_path) as f:
        data = yaml.load(f, Loader=_GitHubActionsSafeLoader)
    return data or {}


# ---------------------------------------------------------------------------
# Trigger parsing
# ---------------------------------------------------------------------------

_SIMPLE_EVENT_TYPES: Dict[str, TriggerType] = {
    "push": TriggerType.PUSH,
    "pull_request": TriggerType.PULL_REQUEST,
}


def _dump_fragment(key: str, value: Any) -> str:
    """Render a single `on:` sub-block back to a YAML string for Trigger.raw."""
    return yaml.dump({key: value}, default_flow_style=False, sort_keys=False).strip()


def _parse_inputs(inputs_map: Any) -> List[Dict[str, Any]]:
    """Shared by workflow_dispatch and workflow_call — both use the same `inputs:` shape."""
    inputs: List[Dict[str, Any]] = []
    for name, spec in (inputs_map or {}).items():
        spec = spec or {}
        inputs.append({
            "name": name,
            "required": spec.get("required", False),
            "default": spec.get("default"),
            "type": spec.get("type"),
        })
    return inputs


def _parse_filtered_event(trigger_type: TriggerType, key: str, value: Any) -> Trigger:
    """push / pull_request — the two event types that carry branch/tag/path filters."""
    raw = _dump_fragment(key, value)
    value = value or {}
    if not isinstance(value, dict):
        # Unexpected shape (e.g. a bare scalar under `push:`) — preserve raw, skip filters.
        return Trigger(type=trigger_type, raw=raw)

    # LIMITATION: GH Actions' `types:` filter (e.g. `pull_request: {types: [opened, ...]}`)
    # narrows which activity types fire the event. The IR's Trigger schema has no field
    # for this — nothing is dropped (it's still in `raw`), but it isn't structured.
    # Seen in tests/fixtures/node_test_linux.yml.

    return Trigger(
        type=trigger_type,
        branches=list(value.get("branches") or []),
        branches_ignore=list(value.get("branches-ignore") or []),
        tags=list(value.get("tags") or []),
        tags_ignore=list(value.get("tags-ignore") or []),
        paths=list(value.get("paths") or []),
        paths_ignore=list(value.get("paths-ignore") or []),
        raw=raw,
    )


def _parse_schedule(key: str, value: Any) -> List[Trigger]:
    """
    `schedule:` is always a list of `{cron: "..."}` entries. GH Actions allows
    more than one cron entry; the IR's Trigger.schedule field is a single
    string, so each cron entry becomes its own Trigger rather than losing all
    but one.
    """
    entries = value or []
    if not isinstance(entries, list):
        # LIMITATION: `schedule:` with a non-list value would be invalid GH Actions
        # syntax we haven't seen in practice — preserve raw, don't guess a cron.
        return [Trigger(type=TriggerType.SCHEDULE, raw=_dump_fragment(key, value))]

    triggers = []
    for entry in entries:
        cron = entry.get("cron") if isinstance(entry, dict) else None
        triggers.append(Trigger(
            type=TriggerType.SCHEDULE,
            schedule=cron,
            raw=_dump_fragment(key, [entry]),
        ))
    return triggers


def _parse_manual(key: str, value: Any) -> Trigger:
    """`workflow_dispatch:` — optionally with `inputs:`."""
    raw = _dump_fragment(key, value)
    value = value or {}
    inputs = _parse_inputs(value.get("inputs")) if isinstance(value, dict) else []
    return Trigger(type=TriggerType.MANUAL, inputs=inputs, raw=raw)


def _parse_workflow_call(key: str, value: Any) -> Trigger:
    """`workflow_call:` — reusable-workflow entry point, optionally with `inputs:`."""
    raw = _dump_fragment(key, value)
    value = value or {}
    inputs = _parse_inputs(value.get("inputs")) if isinstance(value, dict) else []
    # LIMITATION: workflow_call also accepts `secrets:` and `outputs:` blocks.
    # Neither has a home in the IR's Trigger schema yet — preserved only in `raw`.
    return Trigger(type=TriggerType.WORKFLOW_CALL, inputs=inputs, raw=raw)


def _parse_workflow_run(key: str, value: Any) -> Trigger:
    """`workflow_run:` — fires when another workflow (by name) completes."""
    raw = _dump_fragment(key, value)
    value = value or {}
    workflows = value.get("workflows") if isinstance(value, dict) else None
    source_workflow: Optional[str] = None
    if isinstance(workflows, list) and workflows:
        source_workflow = workflows[0]
        if len(workflows) > 1:
            # LIMITATION: workflow_run can list multiple upstream workflow names;
            # Trigger.source_workflow is singular, so only the first is captured
            # structurally — the full list remains in `raw`.
            pass
    return Trigger(type=TriggerType.WORKFLOW_RUN, source_workflow=source_workflow, raw=raw)


def _parse_release(key: str, value: Any) -> Trigger:
    """`release:` — optionally filtered by `types:` (e.g. published, created)."""
    return Trigger(type=TriggerType.RELEASE, raw=_dump_fragment(key, value))


def _parse_other(key: str, value: Any) -> Trigger:
    """Any GH Actions event not explicitly modelled above (issues, label, status, ...)."""
    return Trigger(type=TriggerType.OTHER, raw=_dump_fragment(key, value))


def _parse_event(key: str, value: Any) -> List[Trigger]:
    """Dispatch a single `on:` entry (event name + its config) to the right handler."""
    if key in _SIMPLE_EVENT_TYPES:
        return [_parse_filtered_event(_SIMPLE_EVENT_TYPES[key], key, value)]
    if key == "schedule":
        return _parse_schedule(key, value)
    if key == "workflow_dispatch":
        return [_parse_manual(key, value)]
    if key == "workflow_call":
        return [_parse_workflow_call(key, value)]
    if key == "workflow_run":
        return [_parse_workflow_run(key, value)]
    if key == "release":
        return [_parse_release(key, value)]
    return [_parse_other(key, value)]


def _parse_triggers(on_block: Any) -> List[Trigger]:
    """
    Parse a workflow's `on:` value into Trigger objects. Handles all three
    shapes GH Actions allows: bare string (`on: push`), list
    (`on: [push, pull_request]`), and full map with per-event filters.
    """
    if on_block is None:
        return []

    if isinstance(on_block, str):
        return _parse_event(on_block, None)

    if isinstance(on_block, list):
        triggers: List[Trigger] = []
        for item in on_block:
            if isinstance(item, str):
                triggers.extend(_parse_event(item, None))
            else:
                # LIMITATION: the list form of `on:` is only documented to allow
                # bare event-name strings; a non-string entry here is unexpected
                # syntax we haven't seen in practice — preserve raw, don't guess.
                triggers.append(Trigger(
                    type=TriggerType.OTHER,
                    raw=_dump_fragment("on", item),
                ))
        return triggers

    if isinstance(on_block, dict):
        triggers = []
        for key, value in on_block.items():
            triggers.extend(_parse_event(key, value))
        return triggers

    # LIMITATION: `on:` shape we haven't seen in practice (not str/list/dict) —
    # preserve raw rather than raising, per parsers/base.py's contract.
    return [Trigger(type=TriggerType.OTHER, raw=_dump_fragment("on", on_block))]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class GitHubActionsParser(BaseParser):
    """
    Layer 1 parser for GitHub Actions workflow YAML.

    Currently only `on:` triggers are implemented (see module docstring).
    `parse()` returns a Pipeline with an accurate `triggers` list and an
    empty `jobs` list until later passes add jobs/steps/needs/env/
    conditions/matrix.
    """

    def parse(self, file_path: str) -> Pipeline:
        data = _load_workflow_yaml(file_path)

        name = data.get("name") or os.path.basename(file_path)
        triggers = _parse_triggers(data.get("on"))

        return Pipeline(
            name=name,
            source_platform=SourcePlatform.GITHUB_ACTIONS,
            source_file=file_path,
            triggers=triggers,
            jobs=[],
        )
