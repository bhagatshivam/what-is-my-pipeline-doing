"""
Tests for evaluation/diagram_diff_direct.py: IR-to-diagram structure check,
built directly from the IR's job dependency graph (no manifest). Regression
tests against all 10 real tests/fixtures/ -- these are real, working
fixtures, so an exact match is expected; a mismatch here means the Mermaid
generator's job/dependency rendering has drifted from the IR.
"""

import os

import pytest

from evaluation._path_guard import HELD_OUT_ROOT
from evaluation.diagram_diff_direct import (
    diff_graphs_direct,
    expected_graph_from_ir,
    score_workflow_diagram_direct,
)
from ir.schema import Job, Pipeline, SourcePlatform

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

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.mark.parametrize("filename", REAL_FIXTURE_FILES)
def test_score_workflow_diagram_direct_exact_match(filename):
    diff = score_workflow_diagram_direct(os.path.join(_FIXTURES_DIR, filename))
    assert diff.exact_match, f"{filename}: {diff}"


def test_score_workflow_diagram_direct_refuses_held_out_path():
    held_out_file = os.path.join(str(HELD_OUT_ROOT), "requests_lint.yml")
    with pytest.raises(ValueError):
        score_workflow_diagram_direct(held_out_file)


def _pipeline(jobs):
    return Pipeline(name="Example", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="example.yml", jobs=jobs)


def test_expected_graph_from_ir():
    pipeline = _pipeline([Job(name="build"), Job(name="test", dependencies=["build"])])
    nodes, edges = expected_graph_from_ir(pipeline)
    assert nodes == {"build", "test"}
    assert edges == {("build", "test")}


def test_diff_graphs_direct_detects_missing_node_and_edge():
    pipeline = _pipeline([Job(name="build"), Job(name="test", dependencies=["build"])])
    mermaid = 'flowchart LR\n    build["build"]\n'
    diff = diff_graphs_direct(pipeline, mermaid)
    assert diff.missing_nodes == {"test"}
    assert diff.missing_edges == {("build", "test")}
    assert not diff.exact_match


def test_diff_graphs_direct_detects_extra_node_and_edge():
    pipeline = _pipeline([Job(name="build")])
    mermaid = 'flowchart LR\n    build["build"]\n    extra["extra"]\n    build --> extra\n'
    diff = diff_graphs_direct(pipeline, mermaid)
    assert diff.extra_nodes == {"extra"}
    assert diff.extra_edges == {("build", "extra")}
