"""
parsers/github_actions.py — GitHub Actions YAML -> ir.schema.Pipeline.

Implemented incrementally per BUILD_PLAN.md Phase 3. So far: the `on:`
trigger block (see `_parse_triggers`), `jobs:` name/runs-on (see
`_parse_jobs`), each job's `steps:` name/type/value/with_args (see
`_parse_steps`), each job's `needs:` (see `_parse_dependencies`), job/step
`env:`, `continue-on-error:`, and `if:` conditions (see `_parse_env_vars`/
`_parse_continue_on_error`/`_parse_condition`), and pipeline-wide secret
references (see `_parse_secret_references`). Matrix strategy is
intentionally not implemented yet — `Job.matrix` stays `None`. Later passes
fill that in. See LIMITATIONS.md for what's known-unhandled so far.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import yaml

from ir.schema import (
    Condition,
    EnvironmentVariable,
    Job,
    Pipeline,
    Secret,
    SecretScope,
    SourcePlatform,
    Step,
    StepType,
    Trigger,
    TriggerType,
)
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
# Environment variables and secret references
# ---------------------------------------------------------------------------

def _stringify_env_value(value: Any) -> Optional[str]:
    """
    Coerce a YAML `env:` value to the string GH Actions would actually
    expose to the job/step. `None` (a declared-but-empty entry) stays
    `None`. Bools are lowercased (`true`/`false`) to match GH Actions'
    runtime string coercion, since Python's `str(True)` would otherwise
    render the wrong case (`"True"`) — seen in fastapi_test.yml's
    `UV_NO_SYNC: true`.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _parse_env_vars(
    env_block: Any, scope: SecretScope, scope_ref: Optional[str]
) -> List[EnvironmentVariable]:
    """
    `env:` -> EnvironmentVariable list. Only a dict of name->value pairs is
    valid GH Actions syntax; missing/non-dict -> no entries. Values may
    themselves be unresolved GH Actions expressions (e.g. `${{ github.sha }}`
    or `${{ secrets.X }}`) — stored as-is rather than evaluated or nulled
    out, since most real env values in these fixtures are expressions and
    EnvironmentVariable has no separate raw fallback field the way
    Trigger/Condition do. (This diverges from the schema's inline comment
    suggesting `None` for "secret/dynamic" values — see LIMITATIONS.md for
    why storing the raw expression string is safe: it's always the
    unresolved reference, never the resolved secret.)
    """
    if not isinstance(env_block, dict):
        return []
    return [
        EnvironmentVariable(
            name=name,
            value=_stringify_env_value(value),
            scope=scope,
            scope_ref=scope_ref,
        )
        for name, value in env_block.items()
    ]


_SECRET_REF_RE = re.compile(r"secrets\.([A-Za-z0-9_]+)")


def _extract_secret_names(value: Any) -> List[str]:
    """
    Textual scan for `secrets.NAME` inside a `${{ ... }}` expression.
    LIMITATION: this is a regex scan, not a GH Actions expression parser —
    a secret referenced via unusual indirection (e.g. bracket syntax
    `secrets['X']`, or a name built dynamically from a matrix value) won't
    be caught. Not seen in any of the 10 fixtures.
    """
    if value is None:
        return []
    return _SECRET_REF_RE.findall(str(value))


def _scan_dict_for_secrets(block: Any) -> List[str]:
    """Scan every value of a dict (e.g. an `env:` or `with:` block) for secret names."""
    if not isinstance(block, dict):
        return []
    names: List[str] = []
    for value in block.values():
        names.extend(_extract_secret_names(value))
    return names


def _iter_scoped_blocks(data: Dict[str, Any]):
    """
    Single shared traversal of a workflow's pipeline/job/step levels,
    yielding `(scope, scope_ref, env_block, with_block, run_value,
    if_value)` for each. Reused by `_parse_pipeline_env_vars` (only needs
    `env_block`) and `_parse_secret_references` (needs `env_block`/
    `with_block`/`run_value`/`if_value`) so the tree only gets walked once
    and the two can't drift apart.

    `if_value` is always `None` at PIPELINE scope — the top-level workflow
    YAML has no `if:` concept, only jobs/steps do.

    STEP scope_ref is `f"{job_key}.{step_index}"` (0-based index, not step
    name) — steps often lack a stable, unique `name:`. This is safe by
    spec, not just by luck: GH Actions' job-id grammar only permits
    `[A-Za-z_][A-Za-z0-9_-]*`, so a job key can never itself contain a `.`
    that would confuse `scope_ref.split(".")[0]` (what
    ir.validate._check_secret_and_env_scopes uses).
    """
    yield SecretScope.PIPELINE, None, data.get("env"), None, None, None

    jobs_block = data.get("jobs")
    if not isinstance(jobs_block, dict):
        return
    for job_key, job_body in jobs_block.items():
        job_body = job_body if isinstance(job_body, dict) else {}
        yield (
            SecretScope.JOB,
            job_key,
            job_body.get("env"),
            job_body.get("with"),
            None,
            job_body.get("if"),
        )

        steps_block = job_body.get("steps")
        if not isinstance(steps_block, list):
            continue
        for i, step in enumerate(steps_block):
            if not isinstance(step, dict):
                continue
            yield (
                SecretScope.STEP,
                f"{job_key}.{i}",
                step.get("env"),
                step.get("with"),
                step.get("run"),
                step.get("if"),
            )


def _parse_pipeline_env_vars(data: Dict[str, Any]) -> List[EnvironmentVariable]:
    """Build the pipeline-wide `Pipeline.environment_variables` list from every scope."""
    entries: List[EnvironmentVariable] = []
    for scope, scope_ref, env_block, _with_block, _run_value, _if_value in _iter_scoped_blocks(data):
        entries.extend(_parse_env_vars(env_block, scope, scope_ref))
    return entries


def _parse_secret_references(data: Dict[str, Any]) -> List[Secret]:
    """
    Scan the whole workflow for `${{ secrets.NAME }}` references — GH
    Actions has no declarative secrets block, so secrets only show up
    wherever they're used (`env:`/`with:`/`run:`/`if:` at any scope).
    Deduped by (name, scope, scope_ref): a secret referenced twice in the
    exact same location collapses to one entry (no new information), but
    the same secret referenced from two different jobs/steps stays as
    separate entries, since those are genuinely different usage sites.
    `ir.validate._check_secret_and_env_scopes` itself tolerates duplicates
    freely, so this dedup is a parser-side cleanliness choice, not a
    correctness requirement.

    LIMITATION: job-level `secrets:` (the reusable-workflow-call mechanism
    for passing secrets to a called workflow, e.g. `secrets: inherit`) is a
    distinct GH Actions construct from `env:`/`with:` and isn't scanned
    here — deferred to the future reusable-workflows pass. Not seen in any
    fixture (eslint_ci.yml's `test_package_manager`, the only `uses:`-based
    job across all 10 fixtures, has no `secrets:` key).
    """
    seen: set = set()
    secrets: List[Secret] = []
    for scope, scope_ref, env_block, with_block, run_value, if_value in _iter_scoped_blocks(data):
        names = (
            _scan_dict_for_secrets(env_block)
            + _scan_dict_for_secrets(with_block)
            + _extract_secret_names(run_value)
            + _extract_secret_names(if_value)
        )
        for name in names:
            key = (name, scope, scope_ref)
            if key in seen:
                continue
            seen.add(key)
            secrets.append(Secret(name=name, scope=scope, scope_ref=scope_ref))
    return secrets


def _parse_continue_on_error(value: Any) -> bool:
    """
    `continue-on-error:` (step level) -> Step.continue_on_error. A literal
    bool is used as-is. LIMITATION: GH Actions also allows this to be a
    `${{ }}` expression (seen only at job level in these fixtures, e.g.
    rust_ci.yml — never at step level); Step.continue_on_error is strictly
    bool-typed with no raw-expression fallback, so a non-bool value can't
    be faithfully represented and defaults to False rather than guessing.
    Untested against real step-level data.
    """
    return value if isinstance(value, bool) else False


def _parse_job_continue_on_error(value: Any) -> Tuple[bool, Optional[str]]:
    """
    `continue-on-error:` (job level) -> (Job.allow_failure, raw expression
    or None). A literal bool maps directly to allow_failure. GH Actions
    also allows an expression here (rust_ci.yml's `job` job:
    `${{ matrix.continue_on_error || false }}`) — coercing that to a bool
    would be guessing, so allow_failure stays at its safe default False and
    the raw expression is returned for the caller to preserve in
    raw_extras instead of silently dropping it.
    """
    if isinstance(value, bool):
        return value, None
    if value is None:
        return False, None
    return False, str(value)


# ---------------------------------------------------------------------------
# Condition (if:) parsing
# ---------------------------------------------------------------------------

_STATUS_CHECK_RE = re.compile(
    r"^(?P<negated>!)?\s*(?P<function>always|success|failure|cancelled)\(\)$"
)
_GITHUB_EQUALS_RE = re.compile(
    r"^github\.(?P<field>ref|event_name)\s*==\s*(['\"])(?P<value>[^'\"]*)\2$"
)


def _strip_expression_wrapper(expr: str) -> str:
    """
    Strip a leading `${{`/trailing `}}` (plus surrounding whitespace) for
    pattern-matching purposes only — GH Actions allows `if:` both wrapped
    (`${{ github.ref == 'main' }}`) and bare (`github.ref == 'main'`); 12 of
    44 real conditions across the fixtures are wrapped, 32 bare. Never used
    to modify the stored `Condition.expression`, which always preserves the
    original text (wrapped or not) verbatim.
    """
    stripped = expr.strip()
    if stripped.startswith("${{") and stripped.endswith("}}"):
        return stripped[3:-2].strip()
    return stripped


def _classify_condition(inner: str) -> Dict[str, Any]:
    """
    Best-effort classification of a `${{ }}`-stripped condition into one of
    a small, explicitly-named set of recognized shapes — not a general
    expression parser. Two shapes recognized:
      - a bare (optionally negated) status-check function call
      - a bare `github.ref == 'X'` / `github.event_name == 'X'` equality

    Anything else -> {"type": "unparsed"}, per the schema's documented
    "don't guess" convention, rather than partially parsing a compound
    expression.

    LIMITATION: `needs.<job>.outputs.*` / `needs.<job>.result` references
    are a meaningfully common real shape (7 occurrences across 3 fixtures:
    fastapi_test.yml, pytorch_lint.yml, rust_ci.yml) that isn't
    structured-parsed this pass — a reasonable future enhancement, not an
    oversight.
    """
    status_match = _STATUS_CHECK_RE.match(inner)
    if status_match:
        return {
            "type": "status_check",
            "function": status_match.group("function"),
            "negated": status_match.group("negated") is not None,
        }

    equals_match = _GITHUB_EQUALS_RE.match(inner)
    if equals_match:
        field = equals_match.group("field")
        condition_type = "ref_equals" if field == "ref" else "event_equals"
        return {"type": condition_type, "value": equals_match.group("value")}

    return {"type": "unparsed"}


def _parse_condition(if_value: Any) -> Optional[Condition]:
    """
    `if:` -> Condition. Missing/`None`/empty-or-whitespace-only string ->
    no condition at all (`None`) — `_check_conditions` in ir/validate.py
    requires `expression` be non-empty whenever a Condition exists, so an
    empty `if:` must map to `None`, never an empty-expression Condition.

    A string's `expression` is stored exactly as written, `${{ }}` wrapper
    included verbatim if present — never normalized, since `expression` is
    the ground truth per the schema's docstring.
    """
    if if_value is None:
        return None

    if isinstance(if_value, str):
        if not if_value.strip():
            return None
        expression = if_value
    elif isinstance(if_value, bool):
        # `if: true`/`if: false` (a literal YAML boolean, not a `${{ }}`
        # expression string) is real syntax — seen in
        # tests/fixtures/pandas_unit_tests.yml's `python-dev` job.
        # Lowercased to match GH Actions' own true/false string convention
        # (mirrors _stringify_env_value's precedent from the env/secrets
        # pass), not Python's str(False) == "False".
        expression = "true" if if_value else "false"
    else:
        # LIMITATION: an `if:` value that's neither a string nor a bool
        # isn't valid GH Actions syntax we've seen — stringify defensively
        # rather than raise. Untested against real data.
        expression = str(if_value)

    structured = _classify_condition(_strip_expression_wrapper(expression))
    return Condition(expression=expression, structured=structured)


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
    # `shell:`/`working-directory:` have no dedicated Step field (unlike
    # env/continue-on-error/if, which all do) — preserved here rather than
    # silently dropped.
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
    env_entries = _parse_env_vars(step.get("env"), SecretScope.STEP, None)

    return Step(
        name=name,
        type=step_type,
        value=value,
        with_args=dict(with_args) if isinstance(with_args, dict) else {},
        condition=_parse_condition(step.get("if")),
        environment={e.name: e.value if e.value is not None else "" for e in env_entries},
        continue_on_error=_parse_continue_on_error(step.get("continue-on-error")),
        raw_extras=raw_extras,
    )


def _parse_steps(steps_block: Any) -> List[Step]:
    """
    Parse a job's `steps:` list into Step objects. This pass covers name
    (with a fallback when absent), type/value (uses vs. run), with_args,
    condition, environment, and continue_on_error.
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

def _parse_dependencies(needs: Any) -> List[str]:
    """
    `needs:` -> Job.dependencies. GH Actions allows a bare job-key string
    (`needs: build`) or a list of job-key strings (`needs: [build, test]`);
    absent entirely is the common case (no upstream dependency). Job.name
    is the YAML job key (see _parse_jobs), which is exactly what `needs:`
    entries reference, so no key/display-name reconciliation is needed here.
    """
    if needs is None:
        return []
    if isinstance(needs, str):
        return [needs]
    if isinstance(needs, list):
        # LIMITATION: a non-string entry in a `needs:` list isn't valid GH
        # Actions syntax we've seen (0 of 58 jobs across all 10 fixtures) —
        # coerced via str() rather than raised. Untested against real data.
        return [item if isinstance(item, str) else str(item) for item in needs]
    # LIMITATION: `needs:` shape we haven't seen in practice (not str/list,
    # e.g. a dict) — treated as no dependencies rather than guessing
    # structure. Untested against real data.
    return []


def _parse_runner(runs_on: Any) -> Optional[str]:
    """
    `runs-on:` -> Job.runner. Matrix strategy is intentionally left for a
    later pass.
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
    job key (-> Job.name), `runs-on` (-> Job.runner), each job's `steps:`
    (see _parse_steps), each job's `needs:` (-> Job.dependencies, see
    _parse_dependencies), each job's `env:` (-> Job.environment, see
    _parse_env_vars), each job's `continue-on-error:` (-> Job.allow_failure,
    see _parse_job_continue_on_error), and each job's `if:` (-> Job.condition,
    see _parse_condition); `matrix` is left at its dataclass default.
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

        allow_failure, coe_expr = _parse_job_continue_on_error(job_body.get("continue-on-error"))
        if coe_expr is not None:
            # LIMITATION: a job-level continue-on-error: expression (e.g.
            # rust_ci.yml's `job` job: `${{ matrix.continue_on_error || false }}`)
            # can't be faithfully coerced into the bool-typed Job.allow_failure —
            # preserved here instead of guessed at. allow_failure stays False.
            raw_extras["continue_on_error_expression"] = coe_expr

        env_entries = _parse_env_vars(job_body.get("env"), SecretScope.JOB, job_key)

        jobs.append(Job(
            name=job_key,
            runner=_parse_runner(job_body.get("runs-on")),
            dependencies=_parse_dependencies(job_body.get("needs")),
            allow_failure=allow_failure,
            condition=_parse_condition(job_body.get("if")),
            environment={e.name: e.value if e.value is not None else "" for e in env_entries},
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

    Currently implemented: `on:` triggers, `jobs:` name/runs-on/needs/env/
    continue-on-error/if, each job's `steps:` name/type/value/with_args/env/
    continue-on-error/if (see module docstring), and pipeline-wide secret
    references. `parse()` returns a Pipeline with accurate `triggers`,
    `jobs` (incl. steps, dependencies, environment, allow_failure, condition),
    `secrets`, and `environment_variables`, though matrix strategy is still
    unimplemented.
    """

    def parse(self, file_path: str) -> Pipeline:
        data = _load_workflow_yaml(file_path)

        name = data.get("name") or os.path.basename(file_path)
        triggers = _parse_triggers(data.get("on"))
        jobs = _parse_jobs(data.get("jobs"))
        secrets = _parse_secret_references(data)
        environment_variables = _parse_pipeline_env_vars(data)

        return Pipeline(
            name=name,
            source_platform=SourcePlatform.GITHUB_ACTIONS,
            source_file=file_path,
            triggers=triggers,
            jobs=jobs,
            secrets=secrets,
            environment_variables=environment_variables,
        )
