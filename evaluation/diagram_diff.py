"""
evaluation.diagram_diff — E3: builds the expected job-node/dependency-edge
set directly from the manifest's `job`/`dependency` facts (never from the
IR or parser), parses the ACTUAL generated Mermaid flowchart string, and
diffs node/edge sets.

Trigger vs. job nodes are classified STRUCTURALLY (stadium `(["..."])` vs
square `["..."]` bracket shape), never by ID name pattern -- a real job can
legally be named `trigger_0` (GH Actions' job-id grammar allows it, and
mermaid_generator.py's own node IDs are `Job.name` verbatim), so excluding
"trigger_N"-looking IDs by string pattern would silently misclassify such a
job as a trigger and produce a false "missing node" result. Structural
classification fixes this for NODE identity (a job named `trigger_0` is
correctly counted as a job node).

Residual, narrower limitation, documented rather than silently present:
mermaid_generator.py itself assigns trigger node IDs as `trigger_{i}`
independently of job names, so if a real job is ALSO literally named
`trigger_0` (etc.), the underlying Mermaid text has two different-shaped
nodes sharing one ID string -- a genuine ID collision in the diagram
itself, not something this scorer introduces. Edges are matched by source
ID string, so an edge whose source is that collided ID is excluded (same
as a real trigger edge would be), meaning a job-to-job dependency edge
FROM a job named `trigger_N` can be missed. This is vanishingly unlikely in
practice and not fixable from the text-parsing side alone -- flagged here
so a future reader isn't surprised by it, not left to rediscover it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Set, Tuple

_JOB_NODE_RE = re.compile(r'^ {4}(\S+)\["(.*)"\]$')
_TRIGGER_NODE_RE = re.compile(r'^ {4}(\S+)\(\["(.*)"\]\)$')
_EDGE_RE = re.compile(r'^ {4}(\S+) --> (\S+)$')


@dataclass
class GraphDiff:
    missing_nodes: Set[str] = field(default_factory=set)
    extra_nodes: Set[str] = field(default_factory=set)
    missing_edges: Set[Tuple[str, str]] = field(default_factory=set)
    extra_edges: Set[Tuple[str, str]] = field(default_factory=set)

    @property
    def exact_match(self) -> bool:
        return not (self.missing_nodes or self.extra_nodes or self.missing_edges or self.extra_edges)


def expected_graph_from_manifest(manifest: Dict[str, Any]) -> Tuple[Set[str], Set[Tuple[str, str]]]:
    """node set = every `job` fact's job name; edge set = (depends_on, job)
    for every `dependency` fact. Trigger->job entry edges are NOT checked
    here -- the manifest's `trigger` facts don't currently encode which
    jobs are entry points, matching this scorer's scope (the job-dependency
    graph specifically, per BUILD_PLAN.md line 184's "job-node and
    dependency-edge comparison" wording, not the full diagram including
    triggers)."""
    nodes = {f["expected"]["name"] for f in manifest["facts"] if f["category"] == "job"}
    edges = {
        (f["expected"]["depends_on"], f["expected"]["job"])
        for f in manifest["facts"] if f["category"] == "dependency"
    }
    return nodes, edges


def parse_generated_mermaid(mermaid_text: str) -> Tuple[Set[str], Set[Tuple[str, str]]]:
    """Structural (bracket-shape) parse -- trigger node IDs are identified
    first by their stadium-shape line, then excluded from both the
    job-node set and any edge whose source is a trigger node."""
    lines = mermaid_text.splitlines()
    trigger_ids = {m.group(1) for line in lines if (m := _TRIGGER_NODE_RE.match(line))}
    job_ids = {m.group(1) for line in lines if (m := _JOB_NODE_RE.match(line))}
    edges = set()
    for line in lines:
        m = _EDGE_RE.match(line)
        if m and m.group(1) not in trigger_ids:
            edges.add((m.group(1), m.group(2)))
    return job_ids, edges


def diff_graphs(manifest: Dict[str, Any], mermaid_text: str) -> GraphDiff:
    expected_nodes, expected_edges = expected_graph_from_manifest(manifest)
    actual_nodes, actual_edges = parse_generated_mermaid(mermaid_text)
    return GraphDiff(
        missing_nodes=expected_nodes - actual_nodes,
        extra_nodes=actual_nodes - expected_nodes,
        missing_edges=expected_edges - actual_edges,
        extra_edges=actual_edges - expected_edges,
    )


def score_workflow_diagram(manifest_path: str) -> GraphDiff:
    from evaluation.fact_scoring import load_manifest
    from generators.mermaid_generator import generate_mermaid
    from parsers.github_actions import GitHubActionsParser

    manifest = load_manifest(manifest_path)
    manifest_dir = os.path.dirname(manifest_path)
    local_file = os.path.join(manifest_dir, manifest["local_file"])
    pipeline = GitHubActionsParser().parse(local_file)
    mermaid_text = generate_mermaid(pipeline)
    return diff_graphs(manifest, mermaid_text)
