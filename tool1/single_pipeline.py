"""
tool1.single_pipeline — orchestrates parser -> IR -> generators -> LLM for
one workflow file.

Contract:
- `generate_documentation` is a pure function: it only combines the output
  of `generators.text_generator.generate_text`, `generators.mermaid_generator.generate_mermaid`,
  and (optionally) an already-computed `llm.base.LLMResult`, never reformats
  or reinterprets any of them. Both generator contracts are treated as
  fixed here. It makes no network calls and never constructs a provider
  itself — that's `_build_documentation`'s job.
- When `llm_result` is None or `llm_result.used_fallback` is True, output
  is byte-identical to the pre-Phase-5 (Phase 4) document — no Overview
  section at all. This is the fallback contract (see `llm/base.py`)
  manifesting at the document level, not just the `LLMResult` level, and
  it's what keeps every existing golden file in `tests/golden/` and every
  existing caller of `generate_documentation(pipeline)` unaffected by this
  module's Phase 5 changes.
- When `llm_result` succeeded, its prose is inserted verbatim as an
  `## Overview` section wrapped in `<!-- llm-overview:start -->` /
  `<!-- llm-overview:end -->` marker comments, between the title and the
  deterministic ```text``` fact block. Everything else in the document —
  title, fact block, Mermaid diagram — stays untouched and verbatim,
  never replaced or altered by the LLM.
- Only `parsers.github_actions.GitHubActionsParser` is wired in — other
  platforms are out of scope until Phase 9.
- Phase 7.5 fix (2026-07-30): when `pipeline.jobs` is non-empty but none of
  them have a dependency that resolves to another job in the pipeline
  (`generators.common._has_dependency_edges` is `False` — real case: a
  pipeline where every job is independent, e.g. `setup_python_test.yml`'s
  14 matrix jobs), the `## Pipeline Diagram` section's `generate_mermaid()`
  output would be N disconnected boxes with no edges at all — technically
  correct (no false edges drawn) but conveys nothing beyond what
  `generate_text()`'s EXECUTION SUMMARY section already states, and reads
  as broken/empty rather than as a deliberate choice. In that case only,
  `generate_documentation` replaces the ```mermaid``` fenced block with a
  one-line note under the same `## Pipeline Diagram` heading, instead of
  calling `generate_mermaid()` at all. This is a document-assembly
  decision made here, not a change to `generate_mermaid()`'s own contract
  — that generator is untouched and still produces the same (edgeless)
  output if called directly. See `LIMITATIONS.md` for the full rationale.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from generators.common import _has_dependency_edges, _plural
from generators.mermaid_generator import generate_mermaid
from generators.text_generator import generate_text
from ir.schema import Pipeline
from ir.validate import IRValidationError, validate_or_raise
from llm import get_default_provider
from llm.base import LLMProvider, LLMResult
from parsers.github_actions import GitHubActionsParser

_OVERVIEW_START = "<!-- llm-overview:start -->"
_OVERVIEW_END = "<!-- llm-overview:end -->"
_OVERVIEW_BLOCK_RE = re.compile(
    re.escape(_OVERVIEW_START) + r".*?" + re.escape(_OVERVIEW_END) + r"\n\n",
    re.DOTALL,
)

DEFAULT_LLM_LOG_PATH = "evaluation/llm_call_log.jsonl"


def _pipeline_diagram_section(pipeline: Pipeline) -> str:
    """The "## Pipeline Diagram" section's content: `generate_mermaid()`'s
    output as a fenced code block, unless every job is independent (no
    dependency resolves to another job in this pipeline) — in that case
    the diagram would be N disconnected boxes with no edges, conveying
    nothing beyond EXECUTION SUMMARY's own "no job dependencies" sentence,
    so a one-line note is shown instead. See module docstring's Phase 7.5
    note and LIMITATIONS.md for the full rationale. `generate_mermaid()`
    itself is untouched — this is a document-assembly decision only."""
    if pipeline.jobs and not _has_dependency_edges(pipeline.jobs):
        n = len(pipeline.jobs)
        verb = "is" if n == 1 else "are"
        return (
            f"## Pipeline Diagram\n\n"
            f"All {n} {_plural(n, 'job')} {verb} independent — no "
            f"job-dependency diagram is shown; see EXECUTION SUMMARY "
            f"above.\n"
        )
    mermaid_output = generate_mermaid(pipeline).rstrip("\n") + "\n"
    return f"## Pipeline Diagram\n\n```mermaid\n{mermaid_output}```\n"


def generate_documentation(pipeline: Pipeline, llm_result: Optional[LLMResult] = None) -> str:
    """Combine generate_text()'s, generate_mermaid()'s, and (optionally)
    llm_result's output, verbatim, into one Markdown document. See module
    docstring for the fallback contract when llm_result is None or
    used_fallback, and for the one documented exception to "verbatim":
    the all-jobs-independent no-diagram note (`_pipeline_diagram_section`)."""
    # Defensive normalization: both generators currently guarantee exactly
    # one trailing "\n" by construction, but this protects the fence
    # structure below if that ever drifts, without touching either
    # generator module.
    text_output = generate_text(pipeline).rstrip("\n") + "\n"

    overview = ""
    if llm_result is not None and not llm_result.used_fallback:
        overview = (
            f"{_OVERVIEW_START}\n"
            f"## Overview\n\n"
            f"{llm_result.text}\n"
            f"{_OVERVIEW_END}\n\n"
        )

    return (
        f"# {pipeline.name}\n\n"
        f"{overview}"
        f"```text\n{text_output}```\n\n"
        f"{_pipeline_diagram_section(pipeline)}"
    )


def _strip_llm_overview(markdown: str) -> str:
    """Remove a `<!-- llm-overview:start -->`...`<!-- llm-overview:end -->`
    block (if present) so a committed doc that includes LLM prose can still
    be compared against a deterministic-only regeneration. A no-op on any
    doc that has no such block."""
    return _OVERVIEW_BLOCK_RE.sub("", markdown)


def _log_llm_call(source_path: str, pipeline_name: str, result: LLMResult,
                   log_path: Optional[str] = None) -> None:
    """Append one JSON record of this LLM call to `log_path` (defaults to
    the current DEFAULT_LLM_LOG_PATH, read at call time rather than bound
    as a default argument, so tests can monkeypatch the module-level
    constant). Logging must never break doc generation, so any OSError
    writing it is swallowed."""
    log_path = log_path or DEFAULT_LLM_LOG_PATH
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_file": source_path,
        "pipeline_name": pipeline_name,
        "provider": result.provider_name,
        "model": result.model,
        "temperature": result.temperature,
        "prompt_version": result.prompt_version,
        "used_fallback": result.used_fallback,
        "error": result.error,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "retry_count": result.retry_count,
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass


def _build_documentation(source_path: str, use_llm: bool = True,
                          provider: Optional[LLMProvider] = None) -> str:
    pipeline = GitHubActionsParser().parse(source_path)
    try:
        warnings = validate_or_raise(pipeline)
    except IRValidationError as exc:
        print(str(exc), file=sys.stderr)
        raise
    for warning in warnings:
        print(warning, file=sys.stderr)

    llm_result: Optional[LLMResult] = None
    if use_llm:
        active_provider = provider or get_default_provider()
        if active_provider is not None:
            text_output = generate_text(pipeline)
            llm_result = active_provider.beautify(text_output, pipeline)
            _log_llm_call(source_path, pipeline.name, llm_result)

    return generate_documentation(pipeline, llm_result)


def document_pipeline(source_path: str, output_dir: str = "docs", use_llm: bool = True,
                       provider: Optional[LLMProvider] = None) -> Path:
    """Parse `source_path`, generate its documentation, and write it to `<output_dir>/<stem>.md`."""
    doc = _build_documentation(source_path, use_llm=use_llm, provider=provider)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{Path(source_path).stem}.md"
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def check_pipeline(source_path: str, output_dir: str = "docs") -> bool:
    """
    Compare freshly generated documentation for `source_path` against the
    committed `<output_dir>/<stem>.md`, without writing anything. Exact
    string equality, but only over the deterministic sections: this always
    regenerates with `use_llm=False` and strips any
    `<!-- llm-overview:start -->`...`<!-- llm-overview:end -->` block from
    the committed doc before comparing — a no-op if the committed doc has
    no such block. LLM prose is intentionally left unchecked here; its
    drift is reviewed via EVALUATION_PLAN.md's Tier 1 Method 4 and Tier 4
    Method 9, not gated on an exact-match CLI check that would need a live
    API key in CI and would be flaky against non-deterministic model
    output.
    """
    stem = Path(source_path).stem
    committed_path = Path(output_dir) / f"{stem}.md"
    fresh = _build_documentation(source_path, use_llm=False)

    if not committed_path.exists():
        print(f"no committed doc found for {stem}.md — run without --check to generate it")
        return False

    committed = _strip_llm_overview(committed_path.read_text(encoding="utf-8"))

    if committed == fresh:
        print(f"{stem}.md is up to date")
        return True

    diff = difflib.unified_diff(
        committed.splitlines(keepends=True),
        fresh.splitlines(keepends=True),
        fromfile=f"{committed_path} (committed, deterministic sections)",
        tofile=f"{committed_path} (generated, deterministic sections)",
    )
    print("".join(diff), end="")
    return False
