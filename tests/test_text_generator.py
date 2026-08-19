"""
Tests for the first slice of Phase 4: generators/text_generator.py's
generate_text(pipeline: Pipeline) -> str.

Covers all 10 real fixtures (no-raise, since none of the 3 hand-written
ground-truth pipelines exercise every real-world shape) plus the 3
hand-written Phase 2 ground-truth IR fixtures (simple/medium/complex),
where exact substring assertions are made against the known IR shapes
documented in tests/fixtures/build_ir_fixtures.py.
"""

import json
import os

import pytest

from generators.text_generator import (
    _concurrency_phrase,
    _permissions_phrase,
    _topological_job_order,
    _with_phrase,
    generate_text,
)
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
    with open(os.path.join(FIXTURES_DIR, filename), encoding="utf-8") as f:
        return Pipeline.from_dict(json.load(f))


# ---------------------------------------------------------------------------
# No-raise coverage: all 10 real fixtures + all 3 ground-truth fixtures.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", REAL_FIXTURE_FILES)
def test_generate_text_does_not_raise_on_real_fixture(filename):
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, filename))
    output = generate_text(pipeline)
    assert isinstance(output, str)
    assert output.startswith(f"Pipeline: {pipeline.name}")


@pytest.mark.parametrize("filename", GROUND_TRUTH_FIXTURE_FILES)
def test_generate_text_does_not_raise_on_ground_truth_fixture(filename):
    pipeline = _load_ground_truth(filename)
    output = generate_text(pipeline)
    assert isinstance(output, str)
    assert output.startswith(f"Pipeline: {pipeline.name}")


# ---------------------------------------------------------------------------
# Substring assertions against the 3 ground-truth fixtures.
# ---------------------------------------------------------------------------

def test_simple_fixture_text_shape():
    output = generate_text(_load_ground_truth("simple_pipeline_ir.json"))
    assert "Pipeline: Lint" in output
    assert "Source: .github/workflows/lint.yml (GitHub Actions)" in output
    assert "AT A GLANCE" in output
    assert "This workflow runs on pushes to `main`." in output
    assert "It contains 1 job, with no job dependencies, so GitHub may run them in parallel." in output
    assert "WHEN IT RUNS" in output
    assert "- Runs on every push to main branch" in output
    assert "EXECUTION SUMMARY" in output
    assert "Independent jobs (no dependencies): lint" in output
    assert "IMPLEMENTATION DETAILS" in output
    assert "1. lint — runs on ubuntu-latest; 2 steps" in output
    assert "SECRETS REQUIRED" not in output
    assert "LINKED WORKFLOWS" not in output


def test_medium_fixture_text_shape():
    output = generate_text(_load_ground_truth("medium_pipeline_ir.json"))
    assert "Pipeline: CI Pipeline" in output
    assert "AT A GLANCE" in output
    assert "It contains 3 jobs: 1 with no declared dependencies, 2 depending on other jobs." in output
    assert "- Runs on every push to main branch" in output
    assert "- Runs on every pull request targeting main branch" in output
    assert "EXECUTION SUMMARY" in output
    assert "Independent jobs (no dependencies): build" in output
    assert "test runs after build" in output
    assert "deploy runs after test" in output
    assert "1. build — runs on ubuntu-latest; 2 steps" in output
    assert (
        "2. test — runs on ubuntu-latest; 2 steps; "
        "matrix: 3 combinations (python-version); after build"
    ) in output
    assert (
        "3. deploy — runs on ubuntu-latest; 1 step; after test; "
        "condition: branch == 'main'"
    ) in output
    assert "SECRETS REQUIRED" in output
    assert "- DEPLOY_API_KEY" in output
    assert "LINKED WORKFLOWS" not in output


def test_complex_fixture_text_shape():
    output = generate_text(_load_ground_truth("complex_pipeline_ir.json"))
    assert "Pipeline: Build, Test & Release" in output
    assert "- Runs on every push with tag matching v*" in output
    assert (
        "- Can be called by other workflows as a reusable workflow "
        "— inputs: release_tag"
    ) in output
    assert (
        "1. build — runs on ubuntu-latest; 3 steps; "
        "matrix: 3 combinations (os); produces dist/"
    ) in output
    assert (
        "2. test — runs on ubuntu-latest; 2 steps; after build; "
        "uses artifacts from build"
    ) in output
    assert (
        "3. release — runs on ubuntu-latest; 2 steps; after test; "
        "uses artifacts from build"
    ) in output
    assert "LINKED WORKFLOWS" in output
    assert "- calls ./.github/workflows/build.yml" in output
    assert "SECRETS REQUIRED" in output
    assert "- PYPI_TOKEN (used in job: release)" in output


# ---------------------------------------------------------------------------
# Topological sort: hand-written cases, proving correctness beyond
# fixture-coincidence (all 10 real fixtures already declare jobs in
# dependency order, so passing those alone wouldn't prove anything).
# ---------------------------------------------------------------------------

def _job(name, deps=()):
    return Job(name=name, dependencies=list(deps))


def test_topological_order_breaks_ties_by_declaration_order():
    # Declared C, B, A; C depends on A. Expected: B, A, C -- neither
    # declaration order (C, B, A) nor alphabetical.
    jobs = [_job("C", deps=["A"]), _job("B"), _job("A")]
    ordered = [j.name for j in _topological_job_order(jobs)]
    assert ordered == ["B", "A", "C"]


def test_topological_order_falls_back_to_declaration_order_on_cycle():
    jobs = [_job("A", deps=["B"]), _job("B", deps=["A"])]
    ordered = [j.name for j in _topological_job_order(jobs)]
    assert ordered == ["A", "B"]


def test_topological_order_ignores_dangling_dependency():
    jobs = [_job("A", deps=["does-not-exist"])]
    ordered = [j.name for j in _topological_job_order(jobs)]
    assert ordered == ["A"]


# ---------------------------------------------------------------------------
# Phase 7.5 Revision 1 — a dangling `needs:` reference is a real, if
# unresolvable, declared dependency. It must never be rendered as
# "independent"/"no dependencies" in AT A GLANCE or EXECUTION SUMMARY, even
# though the (separate, diagram-only) entry-point notion tolerates it.
# ---------------------------------------------------------------------------

def test_dangling_dependency_not_reported_as_independent():
    from ir.schema import SourcePlatform

    pipeline = Pipeline(
        name="Dangling",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file="dangling.yml",
        jobs=[_job("A"), _job("B", deps=["does-not-exist"])],
    )
    output = generate_text(pipeline)

    # AT A GLANCE: only A has no declared dependencies -- B has one
    # (dangling, but declared), so this must be the mixed-case sentence,
    # not the "no job dependencies" all-independent one.
    assert "It contains 2 jobs: 1 with no declared dependencies, 1 depending on other jobs." in output
    assert "with no job dependencies, so GitHub may run them in parallel" not in output

    # EXECUTION SUMMARY: B belongs under "runs after", not the independent list.
    assert "Independent jobs (no dependencies): A" in output
    assert "B runs after does-not-exist" in output
    independent_line = next(line for line in output.splitlines() if line.startswith("Independent jobs"))
    assert "B" not in independent_line


# ---------------------------------------------------------------------------
# Phase 7.5 post-merge fix — AT A GLANCE's trigger sentence dedupes
# string-identical trigger phrases (first-seen order preserved). Real case:
# Tool 2's combined Pipeline can have two origins each contributing an
# unqualified "pushes"/"pull requests" trigger (tests/fixtures/multi/black's
# lint.yml alongside diff_shades.yml/diff_shades_comment.yml), which without
# this fix repeated the same phrase verbatim in the sentence. Two phrases
# that are semantically similar but NOT string-identical (e.g. "pushes to
# `main`" vs. unqualified "pushes") are deliberately NOT deduped -- that's a
# real difference in branch scoping, not a duplicate.
# ---------------------------------------------------------------------------

def test_at_a_glance_dedupes_string_identical_trigger_phrases():
    from ir.schema import SourcePlatform, Trigger, TriggerType

    pipeline = Pipeline(
        name="TwoOriginsSameTrigger",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file="combined.yml",
        triggers=[
            Trigger(type=TriggerType.PUSH, raw="push:"),          # origin A: unqualified push
            Trigger(type=TriggerType.PULL_REQUEST, raw="pull_request:"),
            Trigger(type=TriggerType.PUSH, raw="push:"),          # origin B: identical unqualified push
            Trigger(type=TriggerType.PULL_REQUEST, raw="pull_request:"),
        ],
        jobs=[_job("build")],
    )
    output = generate_text(pipeline)

    assert "This workflow runs on pushes and pull requests." in output
    # Each phrase appears exactly once in the sentence itself, not twice.
    glance_line = next(line for line in output.splitlines() if line.startswith("This workflow runs on"))
    assert glance_line.count("pushes") == 1
    assert glance_line.count("pull requests") == 1


def test_at_a_glance_keeps_differently_qualified_trigger_phrases_distinct():
    # Same TriggerType, different branch scoping -> different phrases,
    # both kept -- this is real information, not a duplicate to collapse.
    from ir.schema import SourcePlatform, Trigger, TriggerType

    pipeline = Pipeline(
        name="TwoOriginsDifferentScope",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file="combined.yml",
        triggers=[
            Trigger(type=TriggerType.PUSH, branches=["main"], raw="push:\n  branches: [main]"),
            Trigger(type=TriggerType.PUSH, raw="push:"),  # unqualified -- a genuinely different phrase
        ],
        jobs=[_job("build")],
    )
    output = generate_text(pipeline)
    assert "This workflow runs on pushes to `main` and pushes." in output


# ---------------------------------------------------------------------------
# Gap 1 — per-job step-name listing (PROJECT_PLAN.md's Tool 1 deliverable
# "what each step in each job does"), against real fixtures.
# ---------------------------------------------------------------------------

def test_step_names_listed_for_real_fixture():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "checkout_check_dist.yml"))
    output = generate_text(pipeline)
    assert "   - actions/checkout@v7" in output
    assert "   - Set Node.js 24.x" in output
    assert "   - Install dependencies" in output
    assert "   - Rebuild the index.js file" in output
    assert "   - Compare the expected and actual dist/ directories" in output
    assert "   - actions/upload-artifact@v7" in output
    # All 6 real steps fit under the cap -- no overflow line.
    assert "more step" not in output


def test_step_list_capped_with_overflow_on_long_job():
    # rust_ci.yml's `job` has 33 steps -- first 10 shown, then one overflow line.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "rust_ci.yml"))
    output = generate_text(pipeline)
    job = next(j for j in pipeline.jobs if j.name == "job")
    assert len(job.steps) == 33
    for step in job.steps[:10]:
        assert f"   - {step.name}" in output
    assert "   - ... and 23 more steps" in output
    # The 11th step onward isn't listed on its own line.
    assert f"   - {job.steps[10].name}" not in output
    # The aggregate count in the job line itself is unaffected by the cap.
    assert "33 steps" in output


def test_step_list_capped_with_overflow_on_second_long_job():
    # upload_artifact_test.yml's `build` has 28 steps -- a second real,
    # independent case for the cap (not just rust_ci.yml coincidence).
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "upload_artifact_test.yml"))
    output = generate_text(pipeline)
    build = next(j for j in pipeline.jobs if j.name == "build")
    assert len(build.steps) == 28
    assert "   - ... and 18 more steps" in output


# ---------------------------------------------------------------------------
# Gap 3 — secret scope_ref decoded into a human-readable job/step reference.
# ---------------------------------------------------------------------------

def test_step_scoped_secret_decoded_to_job_and_step_name():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "rust_ci.yml"))
    output = generate_text(pipeline)
    # Raw "job.26" internal convention must not leak into output...
    assert "job.26" not in output
    assert "job.30" not in output
    assert "job.32" not in output
    # ...decoded into the real step name instead.
    assert "- CACHES_AWS_ACCESS_KEY_ID (used in job: job, step: run the build)" in output
    assert "- CACHES_AWS_SECRET_ACCESS_KEY (used in job: job, step: run the build)" in output


def test_job_scoped_secret_unchanged_by_scope_ref_decoding():
    # JOB-scope secrets have no step index to decode -- output is exactly
    # as before this change.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "rust_ci.yml"))
    output = generate_text(pipeline)
    assert "- GITHUB_TOKEN (used in job: job)" in output


def test_pipeline_scoped_secret_has_no_job_reference():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "rust_ci.yml"))
    output = generate_text(pipeline)
    assert "- TOOLSTATE_REPO_ACCESS_TOKEN" in output
    assert "TOOLSTATE_REPO_ACCESS_TOKEN (used in job" not in output


# ---------------------------------------------------------------------------
# Gap 4 — reusable-workflow-calling jobs state their delegation, not "0 steps".
# ---------------------------------------------------------------------------

def test_reusable_workflow_calling_job_states_delegation():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "eslint_ci.yml"))
    output = generate_text(pipeline)
    assert (
        "test_package_manager — delegates to reusable workflow "
        "eslint/workflows/.github/workflows/ci-package-manager.yml@main"
    ) in output
    assert "test_package_manager — 0 steps" not in output


def test_reusable_workflow_calling_job_without_with_block_has_no_with_clause():
    # eslint_ci.yml's test_package_manager has uses: but no job-level with:
    # (only its steps use with:) — the whole line must stay unchanged by
    # the with: clause added below, not just the delegation prefix.
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "eslint_ci.yml"))
    output = generate_text(pipeline)
    line = next(ln for ln in output.splitlines() if "test_package_manager —" in ln)
    assert "with:" not in line
    assert line.endswith(
        "test_package_manager — delegates to reusable workflow "
        "eslint/workflows/.github/workflows/ci-package-manager.yml@main"
    )


def test_reusable_workflow_calling_job_with_block_is_rendered():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "pytorch_lint.yml"))
    output = generate_text(pipeline)
    assert (
        "get-changed-files — delegates to reusable workflow "
        "./.github/workflows/_get-changed-files.yml; "
        "with: all_files: ${{ contains(github.event.pull_request.labels.*.name, 'lint-all-files') "
        "|| contains(github.event.pull_request.labels.*.name, 'Reverted') || github.event_name == 'push' }}; "
        "condition: github.repository_owner == 'pytorch'"
    ) in output


def test_with_phrase_formats_bool_as_lowercase_yaml_style():
    # YAML `true`/`false` parses to Python bool — render it back in YAML's
    # own spelling, not Python's `True`/`False`.
    assert _with_phrase({"uploadNativeArtifact": True, "skipInstallBuild": "yes"}) == (
        "uploadNativeArtifact: true, skipInstallBuild: yes"
    )


def test_with_phrase_trims_block_scalar_trailing_newline_only():
    # A `|` block scalar (e.g. `script:`) keeps one trailing newline per
    # YAML's clip chomping. Left in, it would push the next "; "-joined
    # clause in _job_line_body onto its own line instead of attaching it
    # to the value's last content line — internal newlines must still be
    # preserved verbatim, only the trailing one(s) trimmed.
    assert _with_phrase({"script": "line one\nline two\n"}) == "script: line one\nline two"


# ---------------------------------------------------------------------------
# Item 4 — permissions/concurrency/deployment_environment: pipeline-level
# header lines, per-job clauses, and the two phrase helpers.
# ---------------------------------------------------------------------------

def test_permissions_phrase_bare_string():
    assert _permissions_phrase("read-all") == "read-all"


def test_permissions_phrase_empty_mapping():
    assert _permissions_phrase({}) == "none (all permissions explicitly disabled)"


def test_permissions_phrase_populated_mapping():
    assert _permissions_phrase({"contents": "read", "packages": "write"}) == "contents: read, packages: write"


def test_concurrency_phrase_with_cancel_in_progress():
    value = {"group": "my-group", "cancel-in-progress": True}
    assert _concurrency_phrase(value) == "group my-group; cancels in-progress runs"


def test_concurrency_phrase_without_cancel_in_progress():
    assert _concurrency_phrase({"group": "my-group"}) == "group my-group"


def test_pipeline_level_permissions_and_concurrency_rendered_after_source_line():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "rust_ci.yml"))
    output = generate_text(pipeline)
    assert "Permissions: contents: read, packages: write" in output
    assert "Concurrency: group ${{ github.workflow }}-" in output
    assert "cancels in-progress runs" in output
    # Right after Source:, before the blank-line+TRIGGERS block.
    lines = output.splitlines()
    source_index = next(i for i, line in enumerate(lines) if line.startswith("Source:"))
    assert lines[source_index + 1].startswith("Permissions:")
    assert lines[source_index + 2].startswith("Concurrency:")


def test_pipeline_level_permissions_empty_mapping_rendered():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "pandas_unit_tests.yml"))
    output = generate_text(pipeline)
    assert "Permissions: none (all permissions explicitly disabled)" in output


def test_pipeline_level_permissions_and_concurrency_omitted_when_absent():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "checkout_check_dist.yml"))
    output = generate_text(pipeline)
    assert "Permissions:" not in output
    assert "Concurrency:" not in output


def test_job_level_permissions_and_concurrency_clauses():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "pandas_unit_tests.yml"))
    output = generate_text(pipeline)
    assert "permissions: contents: read" in output
    assert "concurrency: group ${{ github.event_name == 'push'" in output


def test_job_level_deployment_environment_clause():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "rust_ci.yml"))
    output = generate_text(pipeline)
    assert (
        "deployment environment: ${{ ((github.repository == 'rust-lang/rust' && "
        "(github.ref == 'refs/heads/try-perf' || "
        "github.ref == 'refs/heads/automation/bors/try' || "
        "github.ref == 'refs/heads/automation/bors/auto')) && 'bors') || '' }}"
    ) in output
    assert "deployment environment: ${{ (github.repository == 'rust-lang/rust' && 'bors') || '' }}" in output


def test_job_level_facts_omitted_when_absent():
    pipeline = GitHubActionsParser().parse(os.path.join(FIXTURES_DIR, "checkout_check_dist.yml"))
    output = generate_text(pipeline)
    assert "permissions:" not in output
    assert "concurrency:" not in output
    assert "deployment environment:" not in output
