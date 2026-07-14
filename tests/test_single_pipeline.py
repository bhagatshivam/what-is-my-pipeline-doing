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
from parsers.github_actions import GitHubActionsParser
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


def _fixture_path(filename):
    return os.path.join(FIXTURES_DIR, filename)


def _load_ground_truth(filename):
    with open(_fixture_path(filename)) as f:
        return Pipeline.from_dict(json.load(f))


# ---------------------------------------------------------------------------
# 1. generate_documentation() unit test against a ground-truth Pipeline.
# ---------------------------------------------------------------------------

def test_generate_documentation_simple_fixture_shape():
    pipeline = _load_ground_truth("simple_pipeline_ir.json")
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
@pytest.mark.parametrize("filename", REAL_FIXTURE_FILES)
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
