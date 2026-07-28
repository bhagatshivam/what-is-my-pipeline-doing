"""
evaluation.diagram_diff_direct — Tier 1 Method 3: IR-to-diagram structure
check, built directly from the IR's job dependency graph (no hand-authored
manifest).

Confirms the Mermaid graph's job nodes and dependency edges match
`pipeline.jobs`/`Job.dependencies` exactly. Same scope as
`evaluation/diagram_diff.py`'s existing manifest-driven E3: the job
dependency graph specifically, not trigger-to-job entry edges (mirroring
that module's own documented scope decision).

Deliberately separate from `evaluation/diagram_diff.py` (E3's existing
manifest-driven half, which stays scoped to its Tier 3/4-foundation role
against `evaluation/held_out_workflows/` — see LIMITATIONS.md). This module
is new code alongside it, scoped to the 10 `tests/fixtures/` only, guarded
by `evaluation/_path_guard.py`. Reuses `parse_generated_mermaid()` and
`GraphDiff` from `evaluation.diagram_diff` directly: both are already fully
manifest-agnostic (pure Mermaid-text structural parsing, and a neutral
diff-result shape), so duplicating them here would only be repetition, not
clarity. Function names use a `_direct` suffix throughout so the two paths
are never confused.
"""

from __future__ import annotations

from typing import Set, Tuple

from evaluation._path_guard import assert_not_held_out
from evaluation.diagram_diff import GraphDiff, parse_generated_mermaid
from generators.mermaid_generator import generate_mermaid
from ir.schema import Pipeline
from parsers.github_actions import GitHubActionsParser


def expected_graph_from_ir(pipeline: Pipeline) -> Tuple[Set[str], Set[Tuple[str, str]]]:
    """node set = every Job.name; edge set = (depends_on, job.name) for every
    entry in Job.dependencies -- built directly from the IR, no manifest."""
    nodes = {job.name for job in pipeline.jobs}
    edges = {
        (dep, job.name)
        for job in pipeline.jobs
        for dep in job.dependencies
    }
    return nodes, edges


def diff_graphs_direct(pipeline: Pipeline, mermaid_text: str) -> GraphDiff:
    expected_nodes, expected_edges = expected_graph_from_ir(pipeline)
    actual_nodes, actual_edges = parse_generated_mermaid(mermaid_text)
    return GraphDiff(
        missing_nodes=expected_nodes - actual_nodes,
        extra_nodes=actual_nodes - expected_nodes,
        missing_edges=expected_edges - actual_edges,
        extra_edges=actual_edges - expected_edges,
    )


def score_workflow_diagram_direct(fixture_path: str) -> GraphDiff:
    assert_not_held_out(fixture_path)
    pipeline = GitHubActionsParser().parse(fixture_path)
    mermaid_text = generate_mermaid(pipeline)
    return diff_graphs_direct(pipeline, mermaid_text)
