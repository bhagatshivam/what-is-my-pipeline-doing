"""
Tests for tool1/single_pipeline.py — wiring generate_text()/generate_mermaid()
into a working Tool 1 prototype (generate_documentation, document_pipeline,
check_pipeline), plus cli.py's tool1 subcommand.

generators/text_generator.py and generators/mermaid_generator.py are treated
as a fixed, already-tested contract here — nothing in this file exercises
their internals beyond calling them, mirroring how this module itself is
written.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

from generators.mermaid_generator import generate_mermaid
from generators.text_generator import generate_text
from ir.schema import Pipeline
from ir.validate import IRValidationError
from llm.base import LLMProvider, LLMResult, ProviderResponse
from parsers.github_actions import GitHubActionsParser
import tool1.single_pipeline as single_pipeline_module
from tool1.single_pipeline import check_pipeline, document_pipeline, generate_documentation

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
CLI_PATH = os.path.join(REPO_ROOT, "cli.py")

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

# Split by whether generate_mermaid() actually draws any job-dependency
# edge for that fixture (generators.common._has_dependency_edges) -- the
# 6 all-independent-jobs fixtures get a no-diagram note instead of a
# Mermaid block (see tool1/single_pipeline.py's _pipeline_diagram_section),
# so a mermaid-cli render doesn't apply to them at all.
REAL_FIXTURE_FILES_WITH_DIAGRAM = [
    "fastapi_test.yml",
    "pytorch_lint.yml",
    "rust_ci.yml",
    "upload_artifact_test.yml",
]
REAL_FIXTURE_FILES_WITHOUT_DIAGRAM = [
    "checkout_check_dist.yml",
    "eslint_ci.yml",
    "flask_tests.yml",
    "node_test_linux.yml",
    "pandas_unit_tests.yml",
    "setup_python_test.yml",
]
assert sorted(REAL_FIXTURE_FILES_WITH_DIAGRAM + REAL_FIXTURE_FILES_WITHOUT_DIAGRAM) == sorted(REAL_FIXTURE_FILES)


def _fixture_path(filename):
    return os.path.join(FIXTURES_DIR, filename)


def _load_ground_truth(filename):
    with open(_fixture_path(filename)) as f:
        return Pipeline.from_dict(json.load(f))


def _write_workflow(tmp_path, content, filename="workflow.yml"):
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 1. generate_documentation() unit test against a ground-truth Pipeline.
# ---------------------------------------------------------------------------

def test_generate_documentation_simple_fixture_shape():
    # medium_pipeline_ir.json (not simple_pipeline_ir.json): this test
    # verifies generate_documentation() combines the text/Mermaid output
    # verbatim into one document, which requires a fixture that actually
    # has a Mermaid diagram section -- simple_pipeline_ir.json's single,
    # dependency-free job is exactly the all-independent case that now
    # gets a no-diagram note instead (see
    # test_generate_documentation_all_independent_jobs_shows_note_not_diagram
    # below for that case, specifically).
    pipeline = _load_ground_truth("medium_pipeline_ir.json")
    doc = generate_documentation(pipeline)

    text_output = generate_text(pipeline)
    mermaid_output = generate_mermaid(pipeline)

    assert doc.startswith(f"# {pipeline.name}\n")

    text_start = doc.index("```text\n") + len("```text\n")
    text_end = doc.index("```\n", text_start)
    assert doc[text_start:text_end] == text_output

    mermaid_start = doc.index("```mermaid\n") + len("```mermaid\n")
    mermaid_end = doc.index("```\n", mermaid_start)
    assert doc[mermaid_start:mermaid_end] == mermaid_output

    heading_pos = doc.index("## Pipeline Diagram")
    assert text_end < heading_pos < mermaid_start


def test_generate_documentation_all_independent_jobs_shows_note_not_diagram():
    # simple_pipeline_ir.json's single job has no dependencies -- the
    # Mermaid diagram would be one disconnected box, conveying nothing
    # EXECUTION SUMMARY doesn't already state, so a one-line note replaces
    # it instead of calling generate_mermaid() at all. See
    # generators.common._has_dependency_edges and LIMITATIONS.md.
    pipeline = _load_ground_truth("simple_pipeline_ir.json")
    doc = generate_documentation(pipeline)

    assert "## Pipeline Diagram" in doc
    assert "```mermaid" not in doc
    assert (
        "All 1 job is independent — no job-dependency diagram is shown; "
        "see EXECUTION SUMMARY above."
    ) in doc


# ---------------------------------------------------------------------------
# 2. document_pipeline() integration test across complexity tiers.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "filename",
    ["checkout_check_dist.yml", "eslint_ci.yml", "pytorch_lint.yml"],
)
def test_document_pipeline_writes_correct_file(tmp_path, filename):
    source = _fixture_path(filename)
    stem = filename.rsplit(".", 1)[0]
    output_dir = tmp_path / "docs"

    written = document_pipeline(source, output_dir=str(output_dir))

    assert written == output_dir / f"{stem}.md"
    assert written.exists()

    expected = generate_documentation(GitHubActionsParser().parse(source))
    assert written.read_text(encoding="utf-8") == expected


def test_document_pipeline_overwrites_cleanly_with_no_duplication(tmp_path):
    source = _fixture_path("checkout_check_dist.yml")
    output_dir = tmp_path / "docs"

    first = document_pipeline(source, output_dir=str(output_dir))
    first_content = first.read_text(encoding="utf-8")

    second = document_pipeline(source, output_dir=str(output_dir))
    second_content = second.read_text(encoding="utf-8")

    assert first == second
    assert first_content == second_content
    assert list(output_dir.glob("*.md")) == [first]


@pytest.mark.parametrize(
    "workflow,expected_message",
    [
        (
            "name: dangling\non: push\njobs:\n  test:\n    needs: missing\n    runs-on: ubuntu-latest\n    steps: []\n",
            "depends on 'missing'",
        ),
        (
            "name: cycle\non: push\njobs:\n  a:\n    needs: b\n    runs-on: ubuntu-latest\n"
            "  b:\n    needs: a\n    runs-on: ubuntu-latest\n",
            "Circular dependency detected",
        ),
        (
            "name: malformed\non: push\njobs:\n  - build\n",
            "Workflow 'jobs' must be a mapping",
        ),
        (
            "name: malformed\non: push\njobs:\n  build: run-this\n",
            "Job 'build' must be a mapping",
        ),
    ],
)
def test_validation_errors_block_generators_and_output(
    tmp_path, monkeypatch, workflow, expected_message
):
    source = _write_workflow(tmp_path, workflow)
    output_dir = tmp_path / "docs"

    def fail_if_called(_pipeline):
        pytest.fail("generator called before IR validation completed")

    monkeypatch.setattr(single_pipeline_module, "generate_text", fail_if_called)
    monkeypatch.setattr(single_pipeline_module, "generate_mermaid", fail_if_called)

    with pytest.raises(IRValidationError, match=expected_message):
        document_pipeline(str(source), output_dir=str(output_dir))

    assert not output_dir.exists()


def test_validation_failure_does_not_modify_existing_output(tmp_path):
    source = _write_workflow(
        tmp_path,
        "name: dangling\non: push\njobs:\n  test:\n    needs: missing\n    runs-on: ubuntu-latest\n",
    )
    output_dir = tmp_path / "docs"
    output_dir.mkdir()
    existing = output_dir / "workflow.md"
    existing.write_text("existing documentation\n", encoding="utf-8")

    with pytest.raises(IRValidationError):
        document_pipeline(str(source), output_dir=str(output_dir))

    assert existing.read_text(encoding="utf-8") == "existing documentation\n"


def test_validation_warnings_are_reported_but_do_not_block_generation(tmp_path, capsys):
    source = _write_workflow(
        tmp_path,
        "name: warning-only\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps: []\n",
    )
    output_dir = tmp_path / "docs"

    written = document_pipeline(str(source), output_dir=str(output_dir))

    assert written.exists()
    assert "[WARNING] triggers: Pipeline has no triggers at all." in capsys.readouterr().err


def test_check_validates_before_missing_document_result(tmp_path):
    source = _write_workflow(
        tmp_path,
        "name: dangling\non: push\njobs:\n  test:\n    needs: missing\n    runs-on: ubuntu-latest\n",
    )

    with pytest.raises(IRValidationError):
        check_pipeline(str(source), output_dir=str(tmp_path / "missing-docs"))


# ---------------------------------------------------------------------------
# 3. All 10 real fixtures: no-raise + real Mermaid render via mermaid-cli.
# ---------------------------------------------------------------------------

def _extract_mermaid_block(doc: str) -> str:
    start = doc.index("```mermaid\n") + len("```mermaid\n")
    end = doc.index("```\n", start)
    return doc[start:end]


_MMDC_AVAILABLE = shutil.which("npx") is not None


@pytest.mark.slow
@pytest.mark.skipif(not _MMDC_AVAILABLE, reason="npx not available for mermaid-cli rendering")
@pytest.mark.parametrize("filename", REAL_FIXTURE_FILES_WITH_DIAGRAM)
def test_document_pipeline_diagram_renders_via_mermaid_cli(tmp_path, filename):
    source = _fixture_path(filename)
    output_dir = tmp_path / "docs"
    written = document_pipeline(source, output_dir=str(output_dir))
    doc = written.read_text(encoding="utf-8")

    mermaid_src = _extract_mermaid_block(doc)
    mmd_path = tmp_path / f"{filename}.mmd"
    svg_path = tmp_path / f"{filename}.svg"
    mmd_path.write_text(mermaid_src, encoding="utf-8")

    puppeteer_config = tmp_path / "puppeteer-config.json"
    puppeteer_config.write_text(json.dumps({"args": ["--no-sandbox"]}), encoding="utf-8")

    result = subprocess.run(
        [
            "npx", "-y", "@mermaid-js/mermaid-cli",
            "-i", str(mmd_path), "-o", str(svg_path),
            "-p", str(puppeteer_config),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert svg_path.exists()
    assert svg_path.stat().st_size > 0
    assert svg_path.read_text(encoding="utf-8").startswith("<svg")


@pytest.mark.parametrize("filename", REAL_FIXTURE_FILES_WITHOUT_DIAGRAM)
def test_document_pipeline_all_independent_fixtures_show_note_not_diagram(tmp_path, filename):
    # The complement of the mermaid-cli test above: these 6 real fixtures
    # have no job that depends on another job in the same pipeline, so
    # document_pipeline() must show the no-diagram note, never a Mermaid
    # block -- no mermaid-cli render applies here, there's nothing to render.
    source = _fixture_path(filename)
    output_dir = tmp_path / "docs"
    written = document_pipeline(source, output_dir=str(output_dir))
    doc = written.read_text(encoding="utf-8")

    assert "## Pipeline Diagram" in doc
    assert "```mermaid" not in doc
    assert "no job-dependency diagram is shown" in doc


# ---------------------------------------------------------------------------
# 4. check_pipeline() state-machine test.
# ---------------------------------------------------------------------------

def test_check_pipeline_state_machine(tmp_path, capsys):
    source = _fixture_path("checkout_check_dist.yml")
    output_dir = tmp_path / "docs"

    # Missing.
    assert check_pipeline(source, output_dir=str(output_dir)) is False
    out = capsys.readouterr().out
    assert "no committed doc found for checkout_check_dist.md" in out

    # Created, matches.
    document_pipeline(source, output_dir=str(output_dir))
    assert check_pipeline(source, output_dir=str(output_dir)) is True
    out = capsys.readouterr().out
    assert "up to date" in out

    # Mutated, drifts.
    committed_path = output_dir / "checkout_check_dist.md"
    original = committed_path.read_text(encoding="utf-8")
    committed_path.write_text(original.replace("check-dist", "check-dist-RENAMED", 1), encoding="utf-8")

    assert check_pipeline(source, output_dir=str(output_dir)) is False
    out = capsys.readouterr().out
    assert "check-dist-RENAMED" in out

    # Regenerated, matches again.
    document_pipeline(source, output_dir=str(output_dir))
    assert check_pipeline(source, output_dir=str(output_dir)) is True


# ---------------------------------------------------------------------------
# 5. CLI-level tests via subprocess.
# ---------------------------------------------------------------------------

def _run_cli(args, cwd):
    return subprocess.run(
        [sys.executable, CLI_PATH, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_cli_tool1_normal_run(tmp_path):
    source = os.path.abspath(_fixture_path("checkout_check_dist.yml"))
    result = _run_cli(["tool1", source], cwd=str(tmp_path))

    assert result.returncode == 0
    written = tmp_path / "docs" / "checkout_check_dist.md"
    assert written.exists()


def test_cli_tool1_check_clean(tmp_path):
    source = os.path.abspath(_fixture_path("checkout_check_dist.yml"))
    _run_cli(["tool1", source], cwd=str(tmp_path))

    result = _run_cli(["tool1", source, "--check"], cwd=str(tmp_path))
    assert result.returncode == 0


def test_cli_tool1_check_drift(tmp_path):
    source = os.path.abspath(_fixture_path("checkout_check_dist.yml"))
    _run_cli(["tool1", source], cwd=str(tmp_path))

    written = tmp_path / "docs" / "checkout_check_dist.md"
    with open(written, "a", encoding="utf-8") as f:
        f.write("mutated\n")

    result = _run_cli(["tool1", source, "--check"], cwd=str(tmp_path))
    assert result.returncode == 1


def test_cli_tool1_parse_failure_exit_code(tmp_path):
    result = _run_cli(["tool1", "/nonexistent/path.yml"], cwd=str(tmp_path))
    assert result.returncode == 2
    assert result.stderr.strip() != ""


@pytest.mark.parametrize(
    "workflow",
    [
        "name: dangling\non: push\njobs:\n  test:\n    needs: missing\n    runs-on: ubuntu-latest\n",
        "name: malformed\non: push\njobs:\n  - build\n",
        "name: malformed\non: push\njobs:\n  build: run-this\n",
    ],
)
def test_cli_tool1_invalid_ir_exit_code_and_no_output(tmp_path, workflow):
    source = _write_workflow(tmp_path, workflow)

    result = _run_cli(["tool1", str(source)], cwd=str(tmp_path))

    assert result.returncode == 3
    assert "IR validation failed:" in result.stderr
    assert "Wrote" not in result.stdout
    assert not (tmp_path / "docs").exists()


def test_cli_tool1_warning_does_not_change_success_exit_code(tmp_path):
    source = _write_workflow(
        tmp_path,
        "name: warning-only\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps: []\n",
    )

    result = _run_cli(["tool1", str(source)], cwd=str(tmp_path))

    assert result.returncode == 0
    assert "[WARNING] triggers:" in result.stderr
    assert (tmp_path / "docs" / "workflow.md").exists()


@pytest.mark.parametrize("workflow", ["- not-a-mapping\n", "jobs: [unterminated\n", ""])
def test_cli_tool1_top_level_or_yaml_parse_failure_stays_exit_code_2(tmp_path, workflow):
    source = _write_workflow(tmp_path, workflow)

    result = _run_cli(["tool1", str(source)], cwd=str(tmp_path))

    assert result.returncode == 2
    assert result.stderr.strip() != ""
    assert not (tmp_path / "docs").exists()


# ---------------------------------------------------------------------------
# 6. Phase 5 — LLM Overview section, fallback byte-identity, check_pipeline()
#    deterministic-only scope, --no-llm.
#
# tests/conftest.py's autouse fixture clears GEMINI_API_KEY/GEMINI_MODEL for
# every test, so document_pipeline()/_build_documentation()'s use_llm=True
# default resolves llm.get_default_provider() to None here unless a test
# explicitly injects a provider or sets the env var itself — this is what
# keeps every test above this section (written before Phase 5 existed)
# passing unmodified.
# ---------------------------------------------------------------------------

def _llm_result(text, used_fallback=False, **overrides):
    defaults = dict(
        text=text,
        used_fallback=used_fallback,
        provider_name="fake",
        model="fake-model",
        temperature=0.0,
        prompt_version="v1",
        latency_ms=1.0,
        retry_count=0,
    )
    defaults.update(overrides)
    return LLMResult(**defaults)


class _FixedProseProvider(LLMProvider):
    """Always returns the same fixed prose — for integration tests that
    need a real (non-fallback) LLMResult flowing through document_pipeline()/
    _build_documentation(), without any network or SDK dependency."""

    def __init__(self, prose="Fixed prose overview."):
        self._prose = prose

    @property
    def provider_name(self):
        return "fixed"

    @property
    def model_name(self):
        return "fixed-model"

    @property
    def temperature(self):
        return 0.0

    def _call_once(self, structured_text, pipeline):
        return ProviderResponse(text=self._prose)


def test_generate_documentation_with_successful_llm_result_inserts_overview():
    pipeline = _load_ground_truth("simple_pipeline_ir.json")
    result = _llm_result("This pipeline builds and tests the project on every push.")

    doc = generate_documentation(pipeline, llm_result=result)

    assert "<!-- llm-overview:start -->" in doc
    assert "<!-- llm-overview:end -->" in doc
    assert "## Overview" in doc
    assert "This pipeline builds and tests the project on every push." in doc
    # Overview sits between the title and the deterministic fact block.
    assert doc.index("# " + pipeline.name) < doc.index("## Overview") < doc.index("```text")

    # Everything from the fact block onward is untouched by the LLM result.
    no_llm_doc = generate_documentation(pipeline)
    assert doc[doc.index("```text\n"):] == no_llm_doc[no_llm_doc.index("```text\n"):]


@pytest.mark.parametrize("llm_result", [None, "fallback"])
def test_generate_documentation_fallback_is_byte_identical_to_no_llm_result(llm_result):
    pipeline = _load_ground_truth("simple_pipeline_ir.json")
    result = None if llm_result is None else _llm_result("irrelevant, discarded on fallback", used_fallback=True)

    assert generate_documentation(pipeline, llm_result=result) == generate_documentation(pipeline)


def test_document_pipeline_with_provider_includes_overview(tmp_path):
    source = _fixture_path("checkout_check_dist.yml")
    output_dir = tmp_path / "docs"

    written = document_pipeline(source, output_dir=str(output_dir), provider=_FixedProseProvider("Prose here."))
    content = written.read_text(encoding="utf-8")

    assert "<!-- llm-overview:start -->" in content
    assert "Prose here." in content


@pytest.mark.parametrize(
    "filename",
    ["checkout_check_dist.yml", "eslint_ci.yml", "flask_tests.yml", "rust_ci.yml", "setup_python_test.yml"],
)
def test_document_pipeline_with_llm_across_complexity_range(tmp_path, filename):
    # Spans: a minimal single-job pipeline, a reusable-workflow-delegating
    # job, matrix-with-no-axes, matrix + deployment environment, and a
    # 14-job/35-combination matrix pipeline — proving Overview insertion
    # and the untouched deterministic sections both hold across the real
    # fixture complexity range, not just the simplest case.
    source = _fixture_path(filename)
    output_dir = tmp_path / "docs"

    written = document_pipeline(
        source, output_dir=str(output_dir), provider=_FixedProseProvider(f"Overview for {filename}."),
    )
    content = written.read_text(encoding="utf-8")

    assert "<!-- llm-overview:start -->" in content
    assert f"Overview for {filename}." in content
    assert "## Pipeline Diagram" in content
    # Most of these fixtures have real job-dependency edges and get a
    # Mermaid block; checkout_check_dist/eslint_ci/flask_tests/
    # setup_python_test don't (see REAL_FIXTURE_FILES_WITHOUT_DIAGRAM) and
    # get the no-diagram note instead -- either way, the section is present.
    if filename in REAL_FIXTURE_FILES_WITH_DIAGRAM:
        assert "```mermaid" in content
    else:
        assert "no job-dependency diagram is shown" in content


def test_document_pipeline_use_llm_false_omits_overview_even_with_provider_passed(tmp_path):
    source = _fixture_path("checkout_check_dist.yml")
    output_dir = tmp_path / "docs"

    written = document_pipeline(
        source, output_dir=str(output_dir), use_llm=False, provider=_FixedProseProvider("Prose here."),
    )
    content = written.read_text(encoding="utf-8")

    assert "<!-- llm-overview:start -->" not in content
    assert content == generate_documentation(GitHubActionsParser().parse(source))


def test_document_pipeline_default_without_configured_provider_matches_deterministic_output(tmp_path):
    # use_llm defaults to True, but GEMINI_API_KEY is unset (conftest.py),
    # so get_default_provider() returns None and this stays deterministic-only.
    source = _fixture_path("checkout_check_dist.yml")
    output_dir = tmp_path / "docs"

    written = document_pipeline(source, output_dir=str(output_dir))
    content = written.read_text(encoding="utf-8")

    assert "<!-- llm-overview:start -->" not in content
    assert content == generate_documentation(GitHubActionsParser().parse(source))


def test_check_pipeline_ignores_llm_overview_prose_drift(tmp_path):
    source = _fixture_path("checkout_check_dist.yml")
    output_dir = tmp_path / "docs"

    document_pipeline(source, output_dir=str(output_dir), provider=_FixedProseProvider("Original prose."))
    assert check_pipeline(source, output_dir=str(output_dir)) is True

    committed_path = output_dir / "checkout_check_dist.md"
    committed = committed_path.read_text(encoding="utf-8")
    mutated = committed.replace(
        "Original prose.",
        "Completely different prose that a fresh deterministic-only build would never produce.",
    )
    committed_path.write_text(mutated, encoding="utf-8")

    # Still passes: check_pipeline() never compares LLM prose.
    assert check_pipeline(source, output_dir=str(output_dir)) is True

    # A deterministic-section change is still caught.
    committed_path.write_text(mutated.replace("check-dist", "check-dist-RENAMED", 1), encoding="utf-8")
    assert check_pipeline(source, output_dir=str(output_dir)) is False


def test_check_pipeline_still_works_when_committed_doc_has_no_overview_block(tmp_path):
    # Backward compatibility: every doc committed before Phase 5 has no
    # Overview block at all — _strip_llm_overview must be a no-op on those.
    source = _fixture_path("checkout_check_dist.yml")
    output_dir = tmp_path / "docs"

    document_pipeline(source, output_dir=str(output_dir), use_llm=False)
    assert check_pipeline(source, output_dir=str(output_dir)) is True


def test_build_documentation_logs_llm_call(tmp_path, monkeypatch):
    log_path = tmp_path / "llm_call_log.jsonl"
    monkeypatch.setattr(single_pipeline_module, "DEFAULT_LLM_LOG_PATH", str(log_path))
    source = _fixture_path("checkout_check_dist.yml")

    single_pipeline_module._build_documentation(source, use_llm=True, provider=_FixedProseProvider("Prose."))

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["provider"] == "fixed"
    assert record["model"] == "fixed-model"
    assert record["used_fallback"] is False
    assert record["pipeline_name"] == "Check dist"
    assert record["source_file"] == source


def test_build_documentation_does_not_log_when_use_llm_false(tmp_path, monkeypatch):
    log_path = tmp_path / "llm_call_log.jsonl"
    monkeypatch.setattr(single_pipeline_module, "DEFAULT_LLM_LOG_PATH", str(log_path))
    source = _fixture_path("checkout_check_dist.yml")

    single_pipeline_module._build_documentation(source, use_llm=False)

    assert not log_path.exists()


def test_log_llm_call_swallows_oserror():
    # Logging must never break doc generation, even if the log path is unwritable.
    source = _fixture_path("checkout_check_dist.yml")
    result = _llm_result("prose", used_fallback=False)

    single_pipeline_module._log_llm_call(
        source, "Check dist", result, log_path="/nonexistent-dir/definitely-not-writable/log.jsonl",
    )  # must not raise


# ---------------------------------------------------------------------------
# 7. CLI --no-llm.
# ---------------------------------------------------------------------------

def test_cli_tool1_no_llm_flag_skips_provider_resolution(tmp_path, monkeypatch):
    # In-process (not via subprocess/_run_cli) so the monkeypatch below is
    # actually visible to the code under test — a subprocess would run in
    # a fresh interpreter that never sees this process's monkeypatching.
    import cli

    def fail_if_called():
        pytest.fail("get_default_provider() must not be called when --no-llm is passed")

    monkeypatch.setattr(single_pipeline_module, "get_default_provider", fail_if_called)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv",
        ["cli.py", "tool1", os.path.abspath(_fixture_path("checkout_check_dist.yml")), "--no-llm"],
    )

    exit_code = cli.main()

    assert exit_code == 0
    written = tmp_path / "docs" / "checkout_check_dist.md"
    assert written.exists()
    assert "<!-- llm-overview:start -->" not in written.read_text(encoding="utf-8")


def test_cli_tool1_no_llm_output_matches_use_llm_false(tmp_path):
    source = os.path.abspath(_fixture_path("checkout_check_dist.yml"))

    result_a_dir = tmp_path / "a"
    result_a_dir.mkdir()
    result_a = _run_cli(["tool1", source, "--no-llm"], cwd=str(result_a_dir))
    result_b_dir = tmp_path / "b"
    result_b_dir.mkdir()
    written_b = document_pipeline(source, output_dir=str(result_b_dir / "docs"), use_llm=False)

    assert result_a.returncode == 0
    written_a = tmp_path / "a" / "docs" / "checkout_check_dist.md"
    assert written_a.read_text(encoding="utf-8") == written_b.read_text(encoding="utf-8")
