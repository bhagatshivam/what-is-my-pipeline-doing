"""
parsers/github_actions.py — GitHub Actions YAML -> ir.schema.Pipeline.

Implemented incrementally per BUILD_PLAN.md Phase 3. So far: the `on:`
trigger block (see `_parse_triggers`), `jobs:` name/runs-on (see
`_parse_jobs`), and each job's `steps:` name/type/value/with_args (see
`_parse_steps`). `needs`, job/step env vars, `if:` conditions, matrix
strategy, and `continue-on-error:` are intentionally not implemented yet —
every `Step`'s `condition`/`environment`/`continue_on_error` stay at their
dataclass defaults. Later passes fill those in. See LIMITATIONS.md for
what's known-unhandled so far.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import yaml

from ir.schema import Job, Pipeline, SourcePlatform, Step, StepType, Trigger, TriggerType
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
# Step parsing
# ---------------------------------------------------------------------------

_SHA_PIN_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _truncate_at_word_boundary(text: str, limit: int, ceiling: int) -> str:
    """
    Truncate `text` to roughly `limit` chars. Prefers completing the word
    that straddles `limit` (up to `ceiling` chars total) over cutting
    mid-word or dropping that word entirely — a strict "last whitespace
    before `limit`" cut would, e.g., turn `... -e typing` into `... -e...`,
    losing the one word that mattered. Falls back to the last whitespace
    boundary before `limit` if the straddling word itself would blow the
    ceiling, and further to a hard cutoff at `limit` if there's no
    whitespace before `limit` at all (a single very long token).
    """
    if len(text) <= limit:
        return text

    boundary = text.rfind(" ", 0, limit)
    word_start = boundary + 1 if boundary != -1 else 0
    next_space = text.find(" ", word_start)
    word_end = next_space if next_space != -1 else len(text)

    if word_end <= ceiling:
        return text[:word_end] + ("..." if word_end < len(text) else "")
    if boundary > 0:
        return text[:boundary] + "..."
    return text[:limit] + "..."


def _step_name_fallback(step: Dict[str, Any]) -> str:
    """Derive a name for a step with no `name:` field, from `uses:`/`run:`."""
    if "uses" in step:
        uses = str(step["uses"])
        ref_part, _, sha = uses.rpartition("@")
        if ref_part and _SHA_PIN_RE.match(sha):
            # LIMITATION: a SHA-pinned uses: ref (e.g. actions/checkout@<40 hex
            # chars>) is correct but unreadable as a display name — shortened to
            # just the owner/repo(/path) part for the *name* fallback only.
            # Step.value always keeps the exact original SHA-pinned string.
            return ref_part
        return uses

    first_line = ""
    for line in str(step.get("run", "")).splitlines():
        if line.strip():
            first_line = line.strip()
            break
    return _truncate_at_word_boundary(first_line, 60, 75)


def _parse_step(step: Dict[str, Any]) -> Step:
    raw_extras: Dict[str, Any] = {}

    # `id:` has no dedicated Step field — always preserved when present, per
    # the schema's raw_extras escape-hatch convention, regardless of whether
    # the name fallback also happened to use this step.
    if "id" in step:
        raw_extras["step_id"] = step["id"]
    # `shell:`/`working-directory:` likewise have no dedicated Step field
    # (unlike env/if/continue-on-error, which do and are deferred to later
    # passes) — preserved here rather than silently dropped.
    if "shell" in step:
        raw_extras["shell"] = step["shell"]
    if "working-directory" in step:
        raw_extras["working-directory"] = step["working-directory"]

    if "uses" in step:
        step_type = StepType.ACTION
        value = step["uses"]
    elif "run" in step:
        step_type = StepType.COMMAND
        # LIMITATION: GH Actions has no distinct YAML construct for "external
        # script reference" vs. an inline command — `run: ./deploy.sh` is
        # syntactically identical to `run: npm test`. This parser always maps
        # `run:` to StepType.COMMAND, never StepType.SCRIPT; SCRIPT exists in
        # the IR for platforms that do distinguish the two and may go unused
        # by this parser entirely.
        value = step["run"]
    else:
        # LIMITATION: a step with neither `uses:` nor `run:` isn't valid GH
        # Actions syntax as far as we've seen (0 of 299 steps across all 10
        # fixtures) — rather than raise or guess, the whole step body is
        # preserved in raw_extras and StepType.COMMAND is used as a neutral
        # placeholder type. Untested against real-world data.
        step_type = StepType.COMMAND
        value = ""
        raw_extras["unrecognized_step"] = step

    name = step.get("name") or _step_name_fallback(step)
    with_args = step.get("with")

    return Step(
        name=name,
        type=step_type,
        value=value,
        with_args=dict(with_args) if isinstance(with_args, dict) else {},
        raw_extras=raw_extras,
    )


def _parse_steps(steps_block: Any) -> List[Step]:
    """
    Parse a job's `steps:` list into Step objects. This pass covers name
    (with a fallback when absent), type/value (uses vs. run), and with_args.
    condition/environment/continue_on_error are intentionally left at their
    dataclass defaults — later passes fill those in.
    """
    if not isinstance(steps_block, list):
        return []

    steps: List[Step] = []
    for step in steps_block:
        if isinstance(step, dict):
            steps.append(_parse_step(step))
        else:
            # LIMITATION: a non-dict entry in `steps:` isn't valid GH Actions
            # syntax we've seen — preserved minimally rather than raised or
            # dropped. Untested against real-world data.
            steps.append(Step(
                name=str(step)[:60],
                type=StepType.COMMAND,
                value="",
                raw_extras={"unrecognized_step": step},
            ))
    return steps


# ---------------------------------------------------------------------------
# Job parsing
# ---------------------------------------------------------------------------

def _parse_runner(runs_on: Any) -> Optional[str]:
    """
    `runs-on:` -> Job.runner. Only name/runs-on are handled this pass — steps,
    needs, env, conditions, and matrix are intentionally left for later.
    """
    if runs_on is None:
        # Valid for reusable-workflow-call jobs (`uses: ./.github/workflows/x.yml`),
        # which don't declare their own runner. Don't fabricate one.
        return None

    if isinstance(runs_on, str):
        # LIMITATION: matrix-templated runners (e.g. `${{ matrix.os }}`, or
        # `${{ matrix.os || 'ubuntu-latest' }}` as seen in tests/fixtures/flask_tests.yml)
        # are stored as the raw expression string, unresolved — matrix parsing isn't
        # implemented yet (a later pass), which will need to reconcile Job.runner
        # against the job's matrix once it lands.
        return runs_on

    if isinstance(runs_on, list):
        # LIMITATION: self-hosted runner labels (e.g. `runs-on: [self-hosted, linux,
        # x64]`) are a set of labels a runner must match, not a single named runner.
        # Job.runner is typed as a single Optional[str], so the labels are joined into
        # one comma-separated string; the original list structure isn't preserved
        # separately. Not seen in any current fixture — untested against real data.
        return ", ".join(str(label) for label in runs_on)

    # Unexpected shape (e.g. a dict) — stringify rather than raise or drop.
    return str(runs_on)


def _parse_jobs(jobs_block: Any) -> List[Job]:
    """
    Parse a workflow's `jobs:` map into Job objects. This pass handles the
    job key (-> Job.name), `runs-on` (-> Job.runner), and each job's `steps:`
    (see _parse_steps); `needs`/env/conditions/matrix are left at their
    dataclass defaults.
    """
    if not isinstance(jobs_block, dict):
        return []

    jobs: List[Job] = []
    for job_key, job_body in jobs_block.items():
        job_body = job_body if isinstance(job_body, dict) else {}

        raw_extras: Dict[str, Any] = {}
        display_name = job_body.get("name")
        if display_name and display_name != job_key:
            # Job.name must stay the job key — it's what `needs:`/`dependencies`
            # will reference once that's implemented. The human-facing display
            # name is common (not rare — e.g. eslint_ci.yml's `verify_files` job
            # is named "Verify Files") and isn't dropped, just not structured.
            raw_extras["display_name"] = display_name

        jobs.append(Job(
            name=job_key,
            runner=_parse_runner(job_body.get("runs-on")),
            steps=_parse_steps(job_body.get("steps")),
            raw_extras=raw_extras,
        ))
    return jobs


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class GitHubActionsParser(BaseParser):
    """
    Layer 1 parser for GitHub Actions workflow YAML.

    Currently implemented: `on:` triggers, `jobs:` name/runs-on, and each
    job's `steps:` name/type/value/with_args (see module docstring).
    `parse()` returns a Pipeline with accurate `triggers` and `jobs` (incl.
    steps), though `needs`/env/conditions/matrix are still unimplemented.
    """

    def parse(self, file_path: str) -> Pipeline:
        data = _load_workflow_yaml(file_path)

        name = data.get("name") or os.path.basename(file_path)
        triggers = _parse_triggers(data.get("on"))
        jobs = _parse_jobs(data.get("jobs"))

        return Pipeline(
            name=name,
            source_platform=SourcePlatform.GITHUB_ACTIONS,
            source_file=file_path,
            triggers=triggers,
            jobs=jobs,
        )
