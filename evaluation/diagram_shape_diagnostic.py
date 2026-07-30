"""
evaluation.diagram_shape_diagnostic — read-only diagnostic: how many
distinct weakly-connected components does each real pipeline's
job-dependency graph have?

Built 2026-07-30 as a direct follow-up to the no-dependency-diagram-note
fix (`tool1/single_pipeline.py::_pipeline_diagram_section`,
`generators.common._has_dependency_edges`): that fix handles the
all-independent case (every job disconnected). This script answers the
next question — are there real pipelines with a *genuine mix* of a real
dependency chain plus separate standalone jobs, where the diagram might
also need special handling? — with actual numbers instead of a guess.

Findings and the resulting decision (grouping components into Mermaid
`subgraph` blocks was considered and deliberately not built) are recorded
in `LIMITATIONS.md`'s "Tool 1" section. This script is what makes those
numbers independently reproducible rather than only living in chat
history — run it yourself to check them.

Scope: `tests/fixtures/*.yml` (Tool 1, single-file) and
`tests/fixtures/multi/*` (Tool 2, combined) only. Deliberately does NOT
read `evaluation/held_out_workflows/` — this is a development-time design
diagnostic, not a Tier 4 evaluation method, and has no reason to touch the
held-out set. Component resolution mirrors `generators.common
._has_dependency_edges` and `generate_mermaid()`'s own edge-drawing
condition exactly: a `Job.dependencies` entry counts as an edge only if it
resolves to another job's `name` in the same pipeline (a dangling
reference never connects two components).

Read-only: makes no network calls, writes no file, modifies no generator
or fixture. Prints a report to stdout.

Usage:
    python evaluation/diagram_shape_diagnostic.py
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, REPO_ROOT)

from ir.schema import Job  # noqa: E402
from parsers.github_actions import GitHubActionsParser  # noqa: E402
from tool2.multi_pipeline import _merge_pipelines, _repo_label, discover_workflow_files  # noqa: E402

FIXTURES_DIR = os.path.join(REPO_ROOT, "tests", "fixtures")
MULTI_FIXTURES_DIR = os.path.join(FIXTURES_DIR, "multi")

REAL_FIXTURE_FILES = [
    "checkout_check_dist.yml",
    "eslint_ci.yml",
    "fastapi_test.yml",
    "flask_tests.yml",
    "node_test_linux.yml",
    "pandas_unit_tests.yml",
    "pytorch_lint.yml",
    "rust_ci.yml",
    "setup_python_test.yml",
    "upload_artifact_test.yml",
]

REAL_MULTI_FIXTURE_REPOS = ["black", "starlette", "tox"]


def weakly_connected_components(jobs: List[Job]) -> Tuple[List[List[str]], int]:
    """Groups job names into weakly-connected components via
    `Job.dependencies` edges (undirected, only counting a dependency that
    resolves to a real job in the same list — dangling references never
    connect two components, matching `generators.common
    ._has_dependency_edges`'s own resolution rule exactly). Returns
    (components, edge_count); each component is a list of job names."""
    names = [j.name for j in jobs]
    name_set = set(names)
    parent: Dict[str, str] = {n: n for n in names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    edge_count = 0
    for job in jobs:
        for dep in job.dependencies:
            if dep in name_set:
                union(job.name, dep)
                edge_count += 1

    groups: Dict[str, List[str]] = {}
    for name in names:
        groups.setdefault(find(name), []).append(name)
    return list(groups.values()), edge_count


def _shape(component_count: int, edge_count: int) -> str:
    if component_count <= 1:
        return "trivial/fully chained"
    if edge_count == 0:
        return "all-independent"
    return "MIXED"


def main() -> None:
    print("=== tests/fixtures/*.yml (single-file, Tool 1) ===")
    for filename in REAL_FIXTURE_FILES:
        pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
        components, edges = weakly_connected_components(pipeline.jobs)
        sizes = sorted((len(c) for c in components), reverse=True)
        shape = _shape(len(components), edges)
        flag = "  <-- MIXED" if shape == "MIXED" else ""
        print(
            f"{filename}: jobs={len(pipeline.jobs)} edges={edges} "
            f"components={len(components)} sizes={sizes} ({shape}){flag}"
        )

    print()
    print("=== tests/fixtures/multi/* (combined, Tool 2) ===")
    for repo in REAL_MULTI_FIXTURE_REPOS:
        repo_path = os.path.join(MULTI_FIXTURES_DIR, repo)
        files = discover_workflow_files(repo_path)
        pipelines = [GitHubActionsParser().parse(str(f)) for f in files]
        combined = _merge_pipelines(files, pipelines, _repo_label(repo_path), files[0].parent)
        components, edges = weakly_connected_components(combined.jobs)
        sizes = sorted((len(c) for c in components), reverse=True)
        shape = _shape(len(components), edges)
        flag = "  <-- MIXED" if shape == "MIXED" else ""
        print(
            f"{repo}: origins={len(files)} jobs={len(combined.jobs)} edges={edges} "
            f"components={len(components)} sizes={sizes} ({shape}){flag}"
        )
        for component in sorted(components, key=len, reverse=True):
            print(f"    component ({len(component)}): {sorted(component)}")


if __name__ == "__main__":
    main()
