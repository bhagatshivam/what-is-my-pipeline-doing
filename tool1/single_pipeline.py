"""
tool1.single_pipeline — orchestrates parser -> IR -> generators for one
workflow file (Phase 4: no LLM yet — that's Phase 5).

Contract:
- `generate_documentation` is a pure function: it only combines the output
  of `generators.text_generator.generate_text` and
  `generators.mermaid_generator.generate_mermaid`, never reformats or
  reinterprets either. Both generator contracts are treated as fixed here.
- Only `parsers.github_actions.GitHubActionsParser` is wired in — other
  platforms are out of scope until Phase 9.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from generators.mermaid_generator import generate_mermaid
from generators.text_generator import generate_text
from ir.schema import Pipeline
from parsers.github_actions import GitHubActionsParser


def generate_documentation(pipeline: Pipeline) -> str:
    """Combine generate_text()'s and generate_mermaid()'s output, verbatim, into one Markdown document."""
    # Defensive normalization: both generators currently guarantee exactly
    # one trailing "\n" by construction, but this protects the fence
    # structure below if that ever drifts, without touching either
    # generator module.
    text_output = generate_text(pipeline).rstrip("\n") + "\n"
    mermaid_output = generate_mermaid(pipeline).rstrip("\n") + "\n"
    return (
        f"# {pipeline.name}\n\n"
        f"```text\n{text_output}```\n\n"
        f"## Pipeline Diagram\n\n"
        f"```mermaid\n{mermaid_output}```\n"
    )


def _build_documentation(source_path: str) -> str:
    return generate_documentation(GitHubActionsParser().parse(source_path))


def document_pipeline(source_path: str, output_dir: str = "docs") -> Path:
    """Parse `source_path`, generate its documentation, and write it to `<output_dir>/<stem>.md`."""
    doc = _build_documentation(source_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{Path(source_path).stem}.md"
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def check_pipeline(source_path: str, output_dir: str = "docs") -> bool:
    """
    Compare freshly generated documentation for `source_path` against the
    committed `<output_dir>/<stem>.md`, without writing anything. Exact
    string equality — no whitespace tolerance, since generator output is
    fully deterministic with no LLM in the loop yet.
    """
    stem = Path(source_path).stem
    committed_path = Path(output_dir) / f"{stem}.md"

    if not committed_path.exists():
        print(f"no committed doc found for {stem}.md — run without --check to generate it")
        return False

    fresh = _build_documentation(source_path)
    committed = committed_path.read_text(encoding="utf-8")

    if committed == fresh:
        print(f"{stem}.md is up to date")
        return True

    diff = difflib.unified_diff(
        committed.splitlines(keepends=True),
        fresh.splitlines(keepends=True),
        fromfile=f"{committed_path} (committed)",
        tofile=f"{committed_path} (generated)",
    )
    print("".join(diff), end="")
    return False
