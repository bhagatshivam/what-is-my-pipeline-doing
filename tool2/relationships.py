"""
tool2.relationships — read-only analysis of an already-combined (Tool 2)
Pipeline, distinguishing genuinely independent workflow files from ones
chained via `workflow_run`. Phase 7.5 of BUILD_PLAN.md.

Motivation: Tool 2's combined document could show that two workflow files
share the exact same trigger, but had no way to say honestly whether that
means "these run independently, GitHub gives no ordering between them" or
"one genuinely follows the other" — and risked implying an ordering that
doesn't exist. This module adds that distinction as a new, additive layer
on top of the existing merge output.

Contract:
- Read-only consumer of the already-combined `Pipeline` produced by
  `tool2.multi_pipeline._merge_pipelines`. Does NOT import from or modify
  `_merge_pipelines`, `_rewrite_job`, `_rewrite_trigger`, `_rewrite_secret`,
  `_rewrite_env_var`, or any of the existing origin-prefixing/collision-
  guard logic there — that logic is already tested and load-bearing.
- Groups `Trigger`/`Job` by `.origin` (already set by the merge layer for
  every Tool 2 call; this module is meaningless against a single-file Tool
  1 parse, where `.origin` is always `None`).
- "Shared trigger" detection uses STRICT equality only: two triggers count
  as the same shared trigger only if every structured IR field matches
  exactly (type, branches/branches_ignore/paths/paths_ignore/tags/
  tags_ignore as sets, schedule cron string, workflow_dispatch inputs) AND
  their `Trigger.raw` text matches too (whitespace-normalized). The raw
  check exists because `types:` activity filters and other fields aren't
  structurally modelled yet (see LIMITATIONS.md) — they only live in
  `.raw`, so two structurally-identical-looking triggers could still
  differ in a way only the raw text shows. If structured fields match but
  raw text doesn't, the two are NOT shared — two separate independent
  rows, never merged into one. A shared trigger is reported as shared,
  never as an implied ordering — GitHub Actions gives none between
  separately-triggered workflow runs.
- "Follows" relationships are resolved ONLY from `workflow_run` Triggers,
  which carry both `.origin` (who's listening) and `.source_workflow`
  (the upstream workflow's display *name*, not filename — see
  `origin_display_names` below) after merging. `Pipeline.linked_workflows`
  is deliberately NOT used to build a "follows" edge: `LinkedWorkflow` has
  no per-origin attribution at all after merging (it's unioned and deduped
  by `(target, relationship)` alone, across every file — see
  `tool2/multi_pipeline.py`'s docstring and LIMITATIONS.md's "Tool 2"
  section), so for a job-level `uses:` reusable-workflow call
  (`relationship="calls"`) there is no structured, origin-tagged way to
  know which origin *made* the call from the combined Pipeline alone.
  Guessing the source origin from a "calls"/"includes" LinkedWorkflow
  entry would be exactly the kind of inference this phase exists to avoid
  — that fact is still visible in the document's existing (unchanged)
  LINKED WORKFLOWS section, just not attributed to a specific origin row
  here. `workflow_run` is the one relationship type this module can
  resolve honestly, because it alone carries real per-origin structured
  data.
- `origin_display_names: Dict[str, str]` (origin slug -> that file's own
  `Pipeline.name`, i.e. its `name:` field or filename fallback) is
  required input, separate from the combined `Pipeline` itself, because
  that per-file display name is discarded by `_merge_pipelines` (only one
  combined `Pipeline.name` survives). `workflow_run: workflows: [...]`
  and `LinkedWorkflow.target` reference the target's *display name*, not
  its filename-derived origin slug — confirmed divergent on the one real
  fixture with an actual relationship (`tests/fixtures/multi/black`):
  `diff_shades.yml` has `name: diff-shades`; its origin slug is
  `diff_shades_yml`. Built by `tool2.multi_pipeline._origin_display_names`
  from the pre-merge per-file Pipelines, alongside (not inside)
  `_merge_pipelines` — see that function's docstring.
- Never fabricates an edge: a `source_workflow` that doesn't resolve to a
  sibling origin present in this run is left out, not guessed at (matches
  the existing documented `linked_workflows` behaviour, just now resolving
  the workflow_run cases that *can* be resolved).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from generators.common import (
    _and_join,
    _glance_other,
    _has_dependency_edges,
    _jobs_with_no_declared_dependencies,
    _plural,
    _TRIGGER_GLANCE_BUILDERS,
)
from generators.mermaid_generator import generate_mermaid
from ir.schema import Job, Pipeline, SourcePlatform, Trigger, TriggerType


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class SharedTrigger:
    trigger: Trigger          # one representative instance (structured content + raw)
    origins: List[str]        # >=2 origins that share this exact trigger, sorted


@dataclass
class FollowsRelationship:
    origin: str            # the workflow that follows (the workflow_run listener)
    target_origin: str     # the sibling origin it resolves to (the upstream workflow)
    target: str             # the raw source_workflow display name, kept for traceability
    relationship: str       # "triggered_by" — see module docstring for why "calls" isn't resolved here


@dataclass
class WorkflowRow:
    origin: str
    triggers: List[Trigger] = field(default_factory=list)
    job_count: int = 0
    independent_job_count: int = 0     # via generators.common._jobs_with_no_declared_dependencies
    # (the narrow, truthful check — a job with a dangling `needs:` reference
    # must never be counted as "independent" here just because it has no
    # *resolvable* dependency; see LIMITATIONS.md / BUILD_PLAN.md Phase 7.5
    # Revision 1)
    relationship: str = "independent"   # "independent" or "follows {target_origin}[, {target_origin2}, ...]"


@dataclass
class RelationshipReport:
    origins: List[str] = field(default_factory=list)                # distinct origins, first-seen order
    rows: List[WorkflowRow] = field(default_factory=list)            # one per origin, for the relationship table
    shared_triggers: List[SharedTrigger] = field(default_factory=list)  # cross-origin strictly-equal triggers
    follows: List[FollowsRelationship] = field(default_factory=list)    # resolved workflow_run edges


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _ordered_origins(pipeline: Pipeline) -> List[str]:
    """Distinct origins in first-seen order. Jobs are the primary source
    (every real workflow file has at least one), with trigger-only origins
    appended defensively after, in case a hand-built Pipeline ever has
    triggers without jobs."""
    seen: Dict[str, None] = {}
    for job in pipeline.jobs:
        if job.origin is not None:
            seen.setdefault(job.origin, None)
    for trigger in pipeline.triggers:
        if trigger.origin is not None:
            seen.setdefault(trigger.origin, None)
    return list(seen.keys())


def _group_triggers_by_origin(pipeline: Pipeline) -> Dict[str, List[Trigger]]:
    grouped: Dict[str, List[Trigger]] = {}
    for trigger in pipeline.triggers:
        if trigger.origin is None:
            continue
        grouped.setdefault(trigger.origin, []).append(trigger)
    return grouped


def _group_jobs_by_origin(pipeline: Pipeline) -> Dict[str, List[Job]]:
    grouped: Dict[str, List[Job]] = {}
    for job in pipeline.jobs:
        if job.origin is None:
            continue
        grouped.setdefault(job.origin, []).append(job)
    return grouped


# ---------------------------------------------------------------------------
# Strict-equality shared-trigger detection
# ---------------------------------------------------------------------------

def _normalize_raw(raw: str) -> str:
    return " ".join(raw.split())


def _canonical_inputs(inputs: List[Dict[str, object]]) -> tuple:
    """A hashable, deterministic canonical form of `Trigger.inputs`, for
    equality comparison only (not a meaningful sort order). Values are
    converted via `repr()` before comparison/sorting so heterogeneous
    value types (str/bool/None) never raise a TypeError from Python 3's
    refusal to order-compare mixed types — dict keys are guaranteed unique
    within one input dict, so this never loses information needed for
    equality, only for a "natural" ordering nobody needs here."""
    return tuple(
        sorted(
            tuple(sorted((k, repr(v)) for k, v in d.items()))
            for d in inputs
        )
    )


def _trigger_key(trigger: Trigger) -> tuple:
    """Hashable structural key for STRICT shared-trigger equality: every
    structured IR field must match exactly (list-valued fields compared as
    sets, since their order carries no meaning), AND whitespace-normalized
    `raw` must match too — see module docstring for why the raw check is
    required. `origin` is deliberately excluded (that's the whole point:
    two triggers with different origins but an equal key are "shared")."""
    return (
        trigger.type,
        frozenset(trigger.branches),
        frozenset(trigger.branches_ignore),
        frozenset(trigger.paths),
        frozenset(trigger.paths_ignore),
        frozenset(trigger.tags),
        frozenset(trigger.tags_ignore),
        trigger.schedule,
        _canonical_inputs(trigger.inputs),
        _normalize_raw(trigger.raw),
    )


def _find_shared_triggers(triggers_by_origin: Dict[str, List[Trigger]]) -> List[SharedTrigger]:
    """Groups triggers across origins by `_trigger_key`; only keys
    appearing in >=2 distinct origins become a `SharedTrigger`. A trigger
    appearing more than once within a single origin doesn't inflate that
    origin's contribution — it's still exactly one origin sharing with
    others, not two."""
    groups: Dict[tuple, List[Tuple[str, Trigger]]] = {}
    for origin, triggers in triggers_by_origin.items():
        keys_seen_this_origin = set()
        for trigger in triggers:
            key = _trigger_key(trigger)
            if key in keys_seen_this_origin:
                continue
            keys_seen_this_origin.add(key)
            groups.setdefault(key, []).append((origin, trigger))

    shared: List[SharedTrigger] = []
    for entries in groups.values():
        origins = sorted({origin for origin, _ in entries})
        if len(origins) < 2:
            continue
        shared.append(SharedTrigger(trigger=entries[0][1], origins=origins))

    shared.sort(key=lambda s: (s.origins, s.trigger.type.value))
    return shared


# ---------------------------------------------------------------------------
# Follows resolution (workflow_run only — see module docstring)
# ---------------------------------------------------------------------------

def _resolve_follows(pipeline: Pipeline, origin_display_names: Dict[str, str]) -> List[FollowsRelationship]:
    name_to_origin = {name: origin for origin, name in origin_display_names.items()}
    follows: List[FollowsRelationship] = []
    seen: set = set()

    for trigger in pipeline.triggers:
        if trigger.type != TriggerType.WORKFLOW_RUN or trigger.origin is None:
            continue
        if not trigger.source_workflow:
            continue
        target_origin = name_to_origin.get(trigger.source_workflow)
        if target_origin is None or target_origin == trigger.origin:
            continue  # unresolved (points outside this run), or self-reference
        key = (trigger.origin, target_origin)
        if key in seen:
            continue
        seen.add(key)
        follows.append(FollowsRelationship(
            origin=trigger.origin,
            target_origin=target_origin,
            target=trigger.source_workflow,
            relationship="triggered_by",
        ))

    follows.sort(key=lambda f: (f.origin, f.target_origin))
    return follows


# ---------------------------------------------------------------------------
# Relationship table rows
# ---------------------------------------------------------------------------

def _build_rows(
    origins: List[str],
    triggers_by_origin: Dict[str, List[Trigger]],
    jobs_by_origin: Dict[str, List[Job]],
    follows: List[FollowsRelationship],
) -> List[WorkflowRow]:
    follows_by_origin: Dict[str, List[str]] = {}
    for f in follows:
        follows_by_origin.setdefault(f.origin, []).append(f.target_origin)

    rows: List[WorkflowRow] = []
    for origin in origins:
        jobs = jobs_by_origin.get(origin, [])
        independent = _jobs_with_no_declared_dependencies(jobs)
        targets = follows_by_origin.get(origin)
        relationship = "independent" if not targets else "follows " + ", ".join(sorted(set(targets)))
        rows.append(WorkflowRow(
            origin=origin,
            triggers=triggers_by_origin.get(origin, []),
            job_count=len(jobs),
            independent_job_count=len(independent),
            relationship=relationship,
        ))
    return rows


# ---------------------------------------------------------------------------
# Top-level analysis
# ---------------------------------------------------------------------------

def analyze_relationships(pipeline: Pipeline, origin_display_names: Dict[str, str]) -> RelationshipReport:
    """Read-only analysis of an already-combined (Tool 2) Pipeline. See
    module docstring for the full contract."""
    triggers_by_origin = _group_triggers_by_origin(pipeline)
    jobs_by_origin = _group_jobs_by_origin(pipeline)
    origins = _ordered_origins(pipeline)

    shared_triggers = _find_shared_triggers(triggers_by_origin)
    follows = _resolve_follows(pipeline, origin_display_names)
    rows = _build_rows(origins, triggers_by_origin, jobs_by_origin, follows)

    return RelationshipReport(origins=origins, rows=rows, shared_triggers=shared_triggers, follows=follows)


# ---------------------------------------------------------------------------
# Rendering — new, separate from generators/text_generator.py and
# generators/mermaid_generator.py's existing fixed contracts.
# ---------------------------------------------------------------------------

def render_relationship_table(report: RelationshipReport) -> str:
    lines = [
        "| Workflow file | Runs when | Job behaviour | Relationship |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.rows:
        if row.triggers:
            phrases = [_TRIGGER_GLANCE_BUILDERS.get(t.type, _glance_other)(t) for t in row.triggers]
            runs_when = _and_join(phrases)
        else:
            runs_when = "(no triggers)"
        behaviour = f"{row.job_count} {_plural(row.job_count, 'job')}, {row.independent_job_count} independent"
        lines.append(f"| {row.origin} | {runs_when} | {behaviour} | {row.relationship} |")
    return "\n".join(lines) + "\n"


def render_shared_triggers_note(report: RelationshipReport) -> str:
    """Only emitted when there's something to say. States explicitly that
    a shared trigger implies no ordering — GitHub Actions gives none
    between separately-triggered workflow runs — rather than letting the
    table's rows read as if they might be sequenced."""
    if not report.shared_triggers:
        return ""
    lines = [
        "Some workflow files share the exact same trigger. GitHub Actions "
        "gives no ordering between separately-triggered workflow runs — "
        "these run independently of each other, not in sequence, even "
        "though they fire on the same event:",
        "",
    ]
    for shared in report.shared_triggers:
        phrase = _TRIGGER_GLANCE_BUILDERS.get(shared.trigger.type, _glance_other)(shared.trigger)
        lines.append(f"- {phrase}: {', '.join(shared.origins)}")
    return "\n".join(lines) + "\n"


def render_per_workflow_diagram(origin: str, jobs_by_origin: Dict[str, List[Job]]) -> str:
    """One small job-dependency diagram scoped to a single origin, reusing
    the now-job-only `generate_mermaid` unchanged (Phase 7.5 already
    dropped trigger nodes from that contract) against a scratch Pipeline
    holding only that origin's jobs. Returns the full ready-to-insert
    section — a "### {origin}" heading plus either a fenced Mermaid block
    or, when every job in this origin is independent
    (`generators.common._has_dependency_edges` is `False`), a one-line
    note instead of an all-disconnected-boxes diagram — same check and
    rationale as `tool1/single_pipeline.py`'s `_pipeline_diagram_section`,
    applied here for the same reason (see LIMITATIONS.md). Owning the full
    section, not just raw Mermaid text, means a future caller can't wire
    this in while forgetting to also apply that check."""
    jobs = jobs_by_origin.get(origin, [])
    heading = f"### {origin}\n\n"
    if jobs and not _has_dependency_edges(jobs):
        n = len(jobs)
        verb = "is" if n == 1 else "are"
        return heading + (
            f"All {n} {_plural(n, 'job')} {verb} independent — no "
            f"job-dependency diagram is shown.\n"
        )
    scratch = Pipeline(
        name=origin,
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file=origin,
        jobs=jobs,
    )
    mermaid_output = generate_mermaid(scratch).rstrip("\n") + "\n"
    return heading + f"```mermaid\n{mermaid_output}```\n"


def render_follows_diagram(report: RelationshipReport) -> str:
    """Workflow-to-workflow diagram containing ONLY real `follows`
    (workflow_run) edges — never a shared-trigger edge, since shared
    triggers have no real ordering to draw (see module docstring)."""
    lines = ["flowchart LR"]
    for origin in report.origins:
        lines.append(f'    {origin}["{origin}"]')
    for f in report.follows:
        lines.append(f"    {f.target_origin} --> {f.origin}")
    return "\n".join(lines) + "\n"
