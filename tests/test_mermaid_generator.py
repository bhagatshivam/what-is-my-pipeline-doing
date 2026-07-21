"""
Tests for the second slice of Phase 4: generators/mermaid_generator.py's
generate_mermaid(pipeline: Pipeline) -> str.

Covers all 10 real fixtures (no-raise, since none of the 3 hand-written
ground-truth pipelines exercise every real-world shape) plus the 3
hand-written Phase 2 ground-truth IR fixtures (simple/medium/complex),
where exact substring assertions are made against the known IR shapes
documented in tests/fixtures/build_ir_fixtures.py.
"""

import json
import os

import pytest

from generators.mermaid_generator import _entry_jobs, _escape_label, generate_mermaid
from ir.schema import Job, Pipeline
from parsers.github_actions import GitHubActionsParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

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

GROUND_TRUTH_FIXTURE_FILES = [
    "simple_pipeline_ir.json",
    "medium_pipeline_ir.json",
    "complex_pipeline_ir.json",
]


def _load_ground_truth(filename):
    with open(os.path.join(FIXTURES_DIR, filename)) as f:
        return Pipeline.from_dict(json.load(f))


# ---------------------------------------------------------------------------
# No-raise coverage: all 10 real fixtures + all 3 ground-truth fixtures.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", REAL_FIXTURE_FILES)
def test_generate_mermaid_does_not_raise_on_real_fixture(filename):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    output = generate_mermaid(pipeline)
    assert isinstance(output, str)
    assert output.startswith("flowchart LR")


@pytest.mark.parametrize("filename", GROUND_TRUTH_FIXTURE_FILES)
def test_generate_mermaid_does_not_raise_on_ground_truth_fixture(filename):
    pipeline = _load_ground_truth(filename)
    output = generate_mermaid(pipeline)
    assert isinstance(output, str)
    assert output.startswith("flowchart LR")


# ---------------------------------------------------------------------------
# Exact-shape assertions against the 3 ground-truth fixtures.
# ---------------------------------------------------------------------------

def test_simple_fixture_mermaid_shape():
    output = generate_mermaid(_load_ground_truth("simple_pipeline_ir.json"))
    assert output == (
        "flowchart LR\n"
        '    trigger_0(["Push"])\n'
        '    lint["lint"]\n'
        "    trigger_0 --> lint\n"
    )


def test_medium_fixture_mermaid_shape():
    output = generate_mermaid(_load_ground_truth("medium_pipeline_ir.json"))
    assert '    trigger_0(["Push"])' in output
    assert '    trigger_1(["Pull request"])' in output
    assert '    build["build"]' in output
    assert '    test["test [matrix: 3 combinations (python-version)]"]' in output
    assert '    deploy["deploy [if: branch == \'main\']"]' in output
    assert "    trigger_0 --> build" in output
    assert "    trigger_1 --> build" in output
    assert "    build --> test" in output
    assert "    test --> deploy" in output
    # deploy has no dependents and isn't an entry job — no trigger edge to it.
    assert "trigger_0 --> deploy" not in output
    assert "trigger_1 --> deploy" not in output


def test_complex_fixture_mermaid_shape():
    output = generate_mermaid(_load_ground_truth("complex_pipeline_ir.json"))
    assert '    trigger_0(["Push"])' in output
    assert '    trigger_1(["Workflow call"])' in output
    assert '    build["build [matrix: 3 combinations (os)]"]' in output
    assert '    test["test"]' in output
    assert '    release["release"]' in output
    assert "    trigger_0 --> build" in output
    assert "    trigger_1 --> build" in output
    assert "    build --> test" in output
    assert "    test --> release" in output
    # linked_workflows/secrets are out of scope for this diagram.
    assert "build.yml" not in output
    assert "PYPI_TOKEN" not in output


# ---------------------------------------------------------------------------
# Trigger node ID scheme: index-based, not TriggerType-derived.
# ---------------------------------------------------------------------------

def test_multiple_triggers_of_same_type_get_distinct_ids():
    # Two SCHEDULE triggers (e.g. two separate cron entries) must not
    # collide on a type-derived node ID.
    from ir.schema import SourcePlatform, Trigger, TriggerType

    pipeline = Pipeline(
        name="Cron",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file=".github/workflows/cron.yml",
        triggers=[
            Trigger(type=TriggerType.SCHEDULE, schedule="0 0 * * *"),
            Trigger(type=TriggerType.SCHEDULE, schedule="0 12 * * *"),
        ],
        jobs=[Job(name="run")],
    )
    output = generate_mermaid(pipeline)
    assert 'trigger_0(["Schedule"])' in output
    assert 'trigger_1(["Schedule"])' in output
    assert "trigger_0 --> run" in output
    assert "trigger_1 --> run" in output


# ---------------------------------------------------------------------------
# Fan-out / fan-in edges: hand-written, since no real fixture proves this
# in isolation from other job facts.
# ---------------------------------------------------------------------------

def _job(name, deps=()):
    return Job(name=name, dependencies=list(deps))


def test_fan_out_and_fan_in_edges():
    # A -> B, A -> C, B -> D, C -> D (diamond dependency graph).
    jobs = [
        _job("A"),
        _job("B", deps=["A"]),
        _job("C", deps=["A"]),
        _job("D", deps=["B", "C"]),
    ]
    from ir.schema import SourcePlatform

    pipeline = Pipeline(
        name="Diamond",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file="diamond.yml",
        jobs=jobs,
    )
    output = generate_mermaid(pipeline)
    assert "    A --> B" in output
    assert "    A --> C" in output
    assert "    B --> D" in output
    assert "    C --> D" in output


def test_dangling_dependency_still_gets_an_entry_edge():
    from ir.schema import SourcePlatform, Trigger, TriggerType

    pipeline = Pipeline(
        name="Dangling",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file="dangling.yml",
        triggers=[Trigger(type=TriggerType.PUSH)],
        jobs=[_job("A", deps=["does-not-exist"])],
    )
    output = generate_mermaid(pipeline)
    assert "trigger_0 --> A" in output
    # No edge is drawn from a nonexistent job.
    assert "does-not-exist" not in output


def test_entry_jobs_helper():
    jobs = [_job("A"), _job("B", deps=["A"]), _job("C", deps=["does-not-exist"])]
    entries = [j.name for j in _entry_jobs(jobs)]
    assert entries == ["A", "C"]


def test_cycle_falls_back_without_raising():
    # Proves the shared _topological_job_order reuse still carries its
    # cycle-safety guarantee through to the Mermaid generator.
    from ir.schema import SourcePlatform

    jobs = [_job("A", deps=["B"]), _job("B", deps=["A"])]
    pipeline = Pipeline(
        name="Cycle",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file="cycle.yml",
        jobs=jobs,
    )
    output = generate_mermaid(pipeline)
    assert '    A["A"]' in output
    assert '    B["B"]' in output
    assert "    A --> B" in output
    assert "    B --> A" in output


# ---------------------------------------------------------------------------
# Label escaping.
# ---------------------------------------------------------------------------

def test_escape_label_quotes():
    assert _escape_label('say "hi"') == "say #quot;hi#quot;"


def test_escape_label_newlines():
    assert _escape_label("line one\nline two") == "line one<br/>line two"
    assert _escape_label("line one\r\nline two") == "line one<br/>line two"


def test_escape_label_leaves_ordinary_text_untouched():
    assert _escape_label("github.ref == 'main'") == "github.ref == 'main'"


# ---------------------------------------------------------------------------
# Gap 2 — long/multiline job conditions are truncated in the diagram only.
# ---------------------------------------------------------------------------

def test_multiline_condition_truncated_to_first_line_plus_ellipsis():
    # pytorch_lint.yml's lintrunner-clang/lintrunner-pyrefly jobs have a
    # ~12-line block-scalar `if:` (786/236 chars once rendered) -- the full
    # multiline text must not appear verbatim as a wall of <br/>-joined text.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "pytorch_lint.yml"))
    output = generate_mermaid(pipeline)
    clang = next(j for j in pipeline.jobs if j.name == "lintrunner-clang")
    pyrefly = next(j for j in pipeline.jobs if j.name == "lintrunner-pyrefly")
    assert len(clang.condition.expression) > 100
    assert len(pyrefly.condition.expression) > 100
    assert "<br/>" not in output
    assert (
        '    lintrunner-clang["lintrunner-clang '
        "[if: github.repository_owner == 'pytorch' && (...]\"]"
    ) in output
    assert (
        '    lintrunner-pyrefly["lintrunner-pyrefly '
        "[if: github.repository_owner == 'pytorch' && (...]\"]"
    ) in output


def test_long_single_line_condition_truncated_at_max_len():
    # pr-sanity-checks' condition is a single line (no embedded newline) but
    # 161 chars -- too long for a readable node on its own.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "pytorch_lint.yml"))
    output = generate_mermaid(pipeline)
    job = next(j for j in pipeline.jobs if j.name == "pr-sanity-checks")
    assert len(job.condition.expression) > 80
    assert job.condition.expression not in output
    assert (
        "if: ${{ github.event_name == 'pull_request' && "
        "!contains(github.event.pull_request.l...]"
    ) in output


def test_short_condition_left_untruncated():
    # medium_pipeline_ir.json's deploy condition (branch == 'main', well
    # under the threshold) must render exactly as before this change.
    output = generate_mermaid(_load_ground_truth("medium_pipeline_ir.json"))
    assert '    deploy["deploy [if: branch == \'main\']"]' in output
