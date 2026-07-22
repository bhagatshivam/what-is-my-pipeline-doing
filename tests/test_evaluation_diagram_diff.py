"""
Tests for evaluation/diagram_diff.py (E3): scores self-test manifests'
job/dependency facts against the actual generated Mermaid output, plus a
structural-parsing regression test proving a job literally named
`trigger_0` is not misclassified as a trigger node (a name-pattern-based
classifier would get this wrong -- caught during design review).
"""

import os

from evaluation.diagram_diff import (
    diff_graphs,
    expected_graph_from_manifest,
    parse_generated_mermaid,
    score_workflow_diagram,
)

_SELF_TEST_MANIFESTS_DIR = os.path.join(os.path.dirname(__file__), "..", "evaluation", "scorer_self_test_manifests")


def test_rust_ci_diagram_exact_match():
    manifest_path = os.path.join(_SELF_TEST_MANIFESTS_DIR, "rust_ci.manifest.yml")
    diff = score_workflow_diagram(manifest_path)
    assert diff.exact_match, diff


def test_pandas_diagram_exact_match():
    manifest_path = os.path.join(_SELF_TEST_MANIFESTS_DIR, "pandas_unit_tests.manifest.yml")
    diff = score_workflow_diagram(manifest_path)
    assert diff.exact_match, diff


def test_expected_graph_from_manifest():
    manifest = {
        "facts": [
            {"category": "job", "expected": {"name": "build"}},
            {"category": "job", "expected": {"name": "test"}},
            {"category": "dependency", "expected": {"job": "test", "depends_on": "build"}},
        ]
    }
    nodes, edges = expected_graph_from_manifest(manifest)
    assert nodes == {"build", "test"}
    assert edges == {("build", "test")}


def test_diff_detects_missing_node_and_edge():
    manifest = {
        "facts": [
            {"category": "job", "expected": {"name": "build"}},
            {"category": "job", "expected": {"name": "test"}},
            {"category": "dependency", "expected": {"job": "test", "depends_on": "build"}},
        ]
    }
    # Mermaid output missing the "test" node and the edge entirely.
    mermaid = 'flowchart LR\n    build["build"]\n'
    diff = diff_graphs(manifest, mermaid)
    assert diff.missing_nodes == {"test"}
    assert diff.missing_edges == {("build", "test")}
    assert not diff.exact_match


def test_job_literally_named_trigger_0_is_classified_as_a_job_node():
    # mermaid_generator.py assigns trigger node IDs as trigger_{i}
    # (positional) independently of job names, so a real job literally
    # named "trigger_0" produces a genuine ID collision in the underlying
    # Mermaid text itself -- both a stadium-shaped trigger line and a
    # square-shaped job line share the exact ID "trigger_0". A name-pattern
    # classifier (exclude any ID matching "trigger_N") would wrongly drop
    # this job from the node set entirely; structural (bracket-shape)
    # classification correctly still counts it as a job node.
    mermaid = (
        'flowchart LR\n'
        '    trigger_0(["Push"])\n'
        '    trigger_0["trigger_0"]\n'
        '    build["build"]\n'
        '    trigger_0 --> build\n'
    )
    nodes, edges = parse_generated_mermaid(mermaid)
    assert "trigger_0" in nodes
    # Documented, narrow residual limitation (see module docstring): since
    # both lines share the literal ID "trigger_0", an edge whose source is
    # that ID is excluded (same as a real trigger edge would be) -- a
    # job-to-job edge FROM a job named trigger_N can be missed. This is a
    # property of the underlying Mermaid ID collision, not something this
    # parser can resolve from the text alone; asserted here explicitly so
    # it's a known, tested behavior rather than a silent surprise.
    assert ("trigger_0", "build") not in edges


def test_extra_node_and_edge_detected():
    manifest = {"facts": [{"category": "job", "expected": {"name": "build"}}]}
    mermaid = 'flowchart LR\n    build["build"]\n    extra["extra"]\n    build --> extra\n'
    diff = diff_graphs(manifest, mermaid)
    assert diff.extra_nodes == {"extra"}
    assert diff.extra_edges == {("build", "extra")}
