"""
Tests for tool2/multi_pipeline.py — Phase 6. Covers the merge layer
(non-mutation, job/trigger/secret/env-var rewriting, linked_workflows
dedup, the deliberate collision -> IRValidationError path), the
origin-scoped Mermaid trigger-wiring regression (the core Phase 6
architectural fix), discovery (including the degenerate one-file/zero-file
cases), marker-based injection, and cli.py's tool2 subcommand.

generators/text_generator.py and generators/mermaid_generator.py are
treated as a fixed, already-tested contract here, same as
tests/test_single_pipeline.py — nothing in this file exercises their
internals beyond calling them.
"""

import copy
import os
import subprocess
import sys
from pathlib import Path

import pytest

from generators.mermaid_generator import generate_mermaid
from ir.schema import (
    EnvironmentVariable,
    Job,
    LinkedWorkflow,
    Pipeline,
    Secret,
    SecretScope,
    SourcePlatform,
    Trigger,
    TriggerType,
)
from ir.validate import IRValidationError, validate_or_raise
from tool2.multi_pipeline import (
    _extract_injected,
    _inject_markers,
    _merge_pipelines,
    _slugify,
    check_repository,
    discover_workflow_files,
    document_repository,
)

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
CLI_PATH = os.path.join(REPO_ROOT, "cli.py")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _write(tmp_path, relative_path, content):
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


_CI_YML = """\
name: ci
on:
  push:
    branches: [main]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: echo lint
"""

_RELEASE_YML = """\
name: release
on:
  schedule:
    - cron: "0 0 * * *"
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - run: echo publish
"""


def _two_workflow_repo(tmp_path):
    _write(tmp_path, ".github/workflows/ci.yml", _CI_YML)
    _write(tmp_path, ".github/workflows/release.yml", _RELEASE_YML)
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Discovery, including the degenerate one-file/zero-file cases.
# ---------------------------------------------------------------------------

def test_discover_workflow_files_repo_root_finds_github_workflows(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    files = discover_workflow_files(str(repo))
    assert [f.name for f in files] == ["ci.yml", "release.yml"]  # sorted by name


def test_discover_workflow_files_given_workflows_folder_directly(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    files = discover_workflow_files(str(repo / ".github" / "workflows"))
    assert [f.name for f in files] == ["ci.yml", "release.yml"]


def test_discover_workflow_files_nonexistent_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        discover_workflow_files(str(tmp_path / "does-not-exist"))


def test_discover_workflow_files_degenerate_single_file(tmp_path):
    _write(tmp_path, ".github/workflows/ci.yml", _CI_YML)
    files = discover_workflow_files(str(tmp_path))
    assert [f.name for f in files] == ["ci.yml"]


def test_discover_workflow_files_degenerate_zero_files_raises(tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        discover_workflow_files(str(tmp_path))


# ---------------------------------------------------------------------------
# 2. Merge layer: non-mutation, rewriting, dedup.
# ---------------------------------------------------------------------------

def _hand_built_pipeline(source_file, job_name="build", dependency=None, secret_scope=None,
                          secret_scope_ref=None):
    job = Job(name=job_name, dependencies=[dependency] if dependency else [])
    secrets = []
    if secret_scope is not None:
        secrets.append(Secret(name="TOKEN", scope=secret_scope, scope_ref=secret_scope_ref))
    return Pipeline(
        name=source_file,
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file=source_file,
        triggers=[Trigger(type=TriggerType.PUSH, raw="on: push")],
        jobs=[job],
        secrets=secrets,
    )


def test_merge_pipelines_does_not_mutate_inputs(tmp_path):
    p1 = _hand_built_pipeline("a.yml")
    p2 = _hand_built_pipeline("b.yml")
    p1_before = copy.deepcopy(p1)
    p2_before = copy.deepcopy(p2)

    _merge_pipelines([Path("a.yml"), Path("b.yml")], [p1, p2], "repo", Path("."))

    assert p1 == p1_before
    assert p2 == p2_before
    assert p1.jobs[0].name == "build"
    assert p1.jobs[0].origin is None
    assert p1.triggers[0].origin is None


def test_merge_pipelines_prefixes_job_names_and_dependencies():
    p1 = _hand_built_pipeline("ci.yml", job_name="build")
    p2 = _hand_built_pipeline("release.yml", job_name="publish", dependency="build")
    # publish's "after build" dependency is nonsensical cross-file (GH Actions
    # has no cross-file needs:), but this only tests that the merge layer
    # rewrites whatever dependency string is present, consistently, with the
    # *same file's* origin — real parser output never produces this shape.

    combined = _merge_pipelines(
        [Path("ci.yml"), Path("release.yml")], [p1, p2], "repo", Path(".")
    )

    names = [j.name for j in combined.jobs]
    assert names == ["ci_yml__build", "release_yml__publish"]
    assert combined.jobs[1].dependencies == ["release_yml__build"]
    assert combined.jobs[0].origin == "ci_yml"
    assert combined.jobs[1].origin == "release_yml"
    assert combined.triggers[0].origin == "ci_yml"
    assert combined.triggers[1].origin == "release_yml"


@pytest.mark.parametrize(
    "scope,scope_ref,expected",
    [
        (SecretScope.PIPELINE, None, None),
        (SecretScope.JOB, "build", "ci_yml__build"),
        (SecretScope.STEP, "build.2", "ci_yml__build.2"),
    ],
)
def test_merge_pipelines_rewrites_secret_scope_ref(scope, scope_ref, expected):
    p1 = _hand_built_pipeline("ci.yml", secret_scope=scope, secret_scope_ref=scope_ref)
    combined = _merge_pipelines([Path("ci.yml")], [p1], "repo", Path("."))
    assert combined.secrets[0].scope_ref == expected


def test_merge_pipelines_rewrites_environment_variable_scope_ref():
    p1 = Pipeline(
        name="ci.yml",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file="ci.yml",
        jobs=[Job(name="build")],
        environment_variables=[
            EnvironmentVariable(name="FOO", value="bar", scope=SecretScope.JOB, scope_ref="build"),
        ],
    )
    combined = _merge_pipelines([Path("ci.yml")], [p1], "repo", Path("."))
    assert combined.environment_variables[0].scope_ref == "ci_yml__build"


def test_merge_pipelines_dedups_linked_workflows_by_target_and_relationship():
    lw = LinkedWorkflow(target="./.github/workflows/reusable.yml", relationship="calls")
    p1 = Pipeline(
        name="a.yml", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="a.yml",
        jobs=[Job(name="build")], linked_workflows=[lw],
    )
    p2 = Pipeline(
        name="b.yml", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="b.yml",
        jobs=[Job(name="build")],
        linked_workflows=[LinkedWorkflow(target="./.github/workflows/reusable.yml", relationship="calls")],
    )
    combined = _merge_pipelines([Path("a.yml"), Path("b.yml")], [p1, p2], "repo", Path("."))
    assert len(combined.linked_workflows) == 1


def test_merge_pipelines_collision_raises_on_defensive_revalidation():
    """A pathological case where two distinct (origin, job_name) pairs
    concatenate to the same combined job name: origin 'a' + job '_b', and
    origin 'a_' + job 'b', both yield 'a___b'. This is the residual risk
    documented for the `__` separator (LIMITATIONS.md's Tool 2 section) —
    it must surface as a loud IRValidationError from the merged-pipeline
    validate_or_raise() pass, never as a silently corrupted diagram."""
    p1 = Pipeline(
        name="a", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="a",
        jobs=[Job(name="_b")],
    )
    p2 = Pipeline(
        name="a_", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="a_",
        jobs=[Job(name="b")],
    )
    combined = _merge_pipelines([Path("a"), Path("a_")], [p1, p2], "repo", Path("."))
    assert combined.jobs[0].name == combined.jobs[1].name == "a___b"

    with pytest.raises(IRValidationError):
        validate_or_raise(combined)


def test_slugify_distinguishes_same_stem_different_extension():
    assert _slugify("ci.yml") != _slugify("ci.yaml")


# ---------------------------------------------------------------------------
# 3. Origin-scoped Mermaid trigger wiring — the core Phase 6 regression proof.
# ---------------------------------------------------------------------------

def test_generate_mermaid_scopes_triggers_to_their_own_origin():
    p1 = Pipeline(
        name="ci.yml", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="ci.yml",
        triggers=[Trigger(type=TriggerType.PUSH, raw="on: push")],
        jobs=[Job(name="build")],
    )
    p2 = Pipeline(
        name="release.yml", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="release.yml",
        triggers=[Trigger(type=TriggerType.SCHEDULE, schedule="0 0 * * *", raw="on: schedule")],
        jobs=[Job(name="publish")],
    )
    combined = _merge_pipelines([Path("ci.yml"), Path("release.yml")], [p1, p2], "repo", Path("."))

    mermaid = generate_mermaid(combined)

    assert "trigger_0 --> ci_yml__build" in mermaid
    assert "trigger_1 --> release_yml__publish" in mermaid
    # The bug this fix prevents: neither trigger should wire to the other
    # workflow's job.
    assert "trigger_0 --> release_yml__publish" not in mermaid
    assert "trigger_1 --> ci_yml__build" not in mermaid


def test_generate_mermaid_single_pipeline_unaffected_by_origin_field():
    """origin is always None for a real single-file Tool 1 parse — confirms
    the fix is a no-op there (every trigger still wires to every entry job),
    on top of the existing golden-file suite already proving this for real
    fixtures."""
    pipeline = Pipeline(
        name="ci.yml", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="ci.yml",
        triggers=[
            Trigger(type=TriggerType.PUSH, raw="on: push"),
            Trigger(type=TriggerType.PULL_REQUEST, raw="on: pull_request"),
        ],
        jobs=[Job(name="build")],
    )
    mermaid = generate_mermaid(pipeline)
    assert "trigger_0 --> build" in mermaid
    assert "trigger_1 --> build" in mermaid


# ---------------------------------------------------------------------------
# 4. Marker-based injection.
# ---------------------------------------------------------------------------

def test_inject_markers_missing_target_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        _inject_markers(tmp_path / "README.md", "doc\n")


def test_inject_markers_absent_in_existing_file_raises(tmp_path):
    readme = _write(tmp_path, "README.md", "# Repo\n\nNo markers here.\n")
    with pytest.raises(ValueError, match="ci-docs"):
        _inject_markers(readme, "doc\n")


def test_inject_markers_replaces_content_and_preserves_rest_of_file(tmp_path):
    readme = _write(
        tmp_path, "README.md",
        "# Repo\n\nIntro.\n\n<!-- ci-docs:start -->\nstale\n<!-- ci-docs:end -->\n\nFooter.\n",
    )
    _inject_markers(readme, "fresh doc\n")
    content = readme.read_text(encoding="utf-8")
    assert "fresh doc" in content
    assert "stale" not in content
    assert content.startswith("# Repo\n\nIntro.\n\n")
    assert content.endswith("\n\nFooter.\n")


def test_inject_markers_idempotent_on_repeated_identical_content(tmp_path):
    readme = _write(
        tmp_path, "README.md",
        "<!-- ci-docs:start -->\nold\n<!-- ci-docs:end -->\n",
    )
    _inject_markers(readme, "doc\n")
    first = readme.read_text(encoding="utf-8")
    _inject_markers(readme, "doc\n")
    second = readme.read_text(encoding="utf-8")
    assert first == second


def test_extract_injected_round_trips_with_inject_markers(tmp_path):
    readme = _write(
        tmp_path, "README.md",
        "<!-- ci-docs:start -->\nold\n<!-- ci-docs:end -->\n",
    )
    _inject_markers(readme, "doc body\n")
    extracted = _extract_injected(readme.read_text(encoding="utf-8"))
    assert extracted == "doc body\n"


def test_extract_injected_returns_none_when_absent():
    assert _extract_injected("# Repo\n\nno markers\n") is None


# ---------------------------------------------------------------------------
# 5. document_repository()/check_repository() integration.
# ---------------------------------------------------------------------------

def test_document_repository_writes_standalone_file(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    out_dir = tmp_path / "docs"
    written = document_repository(str(repo), output_dir=str(out_dir), use_llm=False)
    assert written.exists()
    assert written.parent == out_dir


def test_check_repository_standalone_missing_doc_returns_false(tmp_path, capsys):
    repo = _two_workflow_repo(tmp_path)
    assert check_repository(str(repo), output_dir=str(tmp_path / "docs")) is False
    assert "no committed doc found" in capsys.readouterr().out


def test_check_repository_standalone_clean_after_generation(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    out_dir = tmp_path / "docs"
    document_repository(str(repo), output_dir=str(out_dir), use_llm=False)
    assert check_repository(str(repo), output_dir=str(out_dir)) is True


def test_check_repository_standalone_detects_drift(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    out_dir = tmp_path / "docs"
    written = document_repository(str(repo), output_dir=str(out_dir), use_llm=False)
    with open(written, "a", encoding="utf-8") as f:
        f.write("mutated\n")
    assert check_repository(str(repo), output_dir=str(out_dir)) is False


def test_check_repository_inject_missing_target_raises(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    with pytest.raises(FileNotFoundError):
        check_repository(str(repo), inject_into=str(tmp_path / "README.md"))


def test_check_repository_inject_markers_absent_raises(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    readme = _write(tmp_path, "README.md", "# Repo\n\nno markers\n")
    with pytest.raises(ValueError, match="ci-docs"):
        check_repository(str(repo), inject_into=str(readme))


def test_check_repository_inject_clean_after_generation(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    readme = _write(tmp_path, "README.md", "<!-- ci-docs:start -->\nold\n<!-- ci-docs:end -->\n")
    document_repository(str(repo), use_llm=False, inject_into=str(readme))
    assert check_repository(str(repo), inject_into=str(readme)) is True


def test_check_repository_inject_detects_drift(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    readme = _write(tmp_path, "README.md", "<!-- ci-docs:start -->\nold\n<!-- ci-docs:end -->\n")
    document_repository(str(repo), use_llm=False, inject_into=str(readme))
    with open(readme, "a", encoding="utf-8") as f:
        f.write("\n<!-- appended after end marker, not between markers -->\n")
    # Sanity: drift must come from content *between* the markers, not
    # trailing file content, so mutate between the markers explicitly.
    content = readme.read_text(encoding="utf-8")
    content = content.replace("<!-- ci-docs:end -->", "mutated\n<!-- ci-docs:end -->")
    readme.write_text(content, encoding="utf-8")
    assert check_repository(str(repo), inject_into=str(readme)) is False


# ---------------------------------------------------------------------------
# 6. CLI-level tests via subprocess, mirroring tests/test_single_pipeline.py.
# ---------------------------------------------------------------------------

def _run_cli(args, cwd):
    return subprocess.run(
        [sys.executable, CLI_PATH, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_cli_tool2_normal_run(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    result = _run_cli(["tool2", str(repo), "--no-llm"], cwd=str(tmp_path))
    assert result.returncode == 0
    assert (tmp_path / "docs").exists()


def test_cli_tool2_check_clean(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    _run_cli(["tool2", str(repo), "--no-llm"], cwd=str(tmp_path))
    result = _run_cli(["tool2", str(repo), "--check"], cwd=str(tmp_path))
    assert result.returncode == 0


def test_cli_tool2_check_drift(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    _run_cli(["tool2", str(repo), "--no-llm"], cwd=str(tmp_path))
    written = next((tmp_path / "docs").glob("*.md"))
    with open(written, "a", encoding="utf-8") as f:
        f.write("mutated\n")
    result = _run_cli(["tool2", str(repo), "--check"], cwd=str(tmp_path))
    assert result.returncode == 1


def test_cli_tool2_nonexistent_path_exit_code_2(tmp_path):
    result = _run_cli(["tool2", str(tmp_path / "nope")], cwd=str(tmp_path))
    assert result.returncode == 2
    assert result.stderr.strip() != ""


def test_cli_tool2_zero_workflow_files_exit_code_2(tmp_path):
    (tmp_path / "repo" / ".github" / "workflows").mkdir(parents=True)
    result = _run_cli(["tool2", str(tmp_path / "repo")], cwd=str(tmp_path))
    assert result.returncode == 2


def test_cli_tool2_invalid_ir_in_one_file_exit_code_3(tmp_path):
    _write(tmp_path, ".github/workflows/ci.yml", _CI_YML)
    _write(
        tmp_path, ".github/workflows/broken.yml",
        "name: broken\non: push\njobs:\n  test:\n    needs: missing\n    runs-on: ubuntu-latest\n",
    )
    result = _run_cli(["tool2", str(tmp_path)], cwd=str(tmp_path))
    assert result.returncode == 3
    assert "IR validation failed:" in result.stderr
    assert not (tmp_path / "docs").exists()


def test_cli_tool2_inject_writes_between_markers(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    readme = _write(tmp_path, "README.md", "<!-- ci-docs:start -->\nold\n<!-- ci-docs:end -->\n")
    result = _run_cli(["tool2", str(repo), "--no-llm", "--inject", str(readme)], cwd=str(tmp_path))
    assert result.returncode == 0
    assert "old" not in readme.read_text(encoding="utf-8")


def test_cli_tool2_inject_missing_markers_exit_code_2(tmp_path):
    repo = _two_workflow_repo(tmp_path)
    readme = _write(tmp_path, "README.md", "# Repo\n\nno markers\n")
    result = _run_cli(["tool2", str(repo), "--no-llm", "--inject", str(readme)], cwd=str(tmp_path))
    assert result.returncode == 2
