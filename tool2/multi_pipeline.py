"""
tool2.multi_pipeline — orchestrates parser -> IR -> generators -> LLM
across a whole repository's `.github/workflows/` folder, producing one
unified Markdown document + one unified Mermaid diagram. Phase 6 of
BUILD_PLAN.md.

Contract:
- Every real workflow file is parsed via the same, unmodified
  `parsers.github_actions.GitHubActionsParser` Tool 1 uses, and each
  resulting `Pipeline` is individually validated via
  `ir.validate.validate_or_raise` before anything is merged — an error in
  one file aborts the whole run (fail-closed, same philosophy as
  `tool1.single_pipeline._build_documentation`), attributed to that file's
  path, rather than producing a partial or misleading combined doc.
- `_merge_pipelines` never mutates its inputs: every rewritten `Job`/
  `Trigger`/`Secret`/`EnvironmentVariable` is a new object built via
  `dataclasses.replace`, so the original per-file `Pipeline` objects
  (and everything reachable from them) are unchanged after a merge — a
  later evaluation script may legitimately want both the per-file and the
  combined view from one parse pass.
- Every job is renamed `f"{origin}__{job.name}"` and tagged
  `Job.origin = origin` (and every trigger from the same file tagged
  `Trigger.origin = origin`), where `origin` is a Mermaid/GH-Actions-job-
  key-safe slug of that file's own filename. This is what lets
  `generators.mermaid_generator.generate_mermaid`'s origin-scoped
  trigger-wiring (Phase 6's approved exception, see that module's
  docstring) keep one workflow's triggers from wiring to another,
  unrelated workflow's jobs once they share one combined `Pipeline`
  object. `Job.dependencies` are rewritten with the same prefix, safe
  because GH Actions has no cross-file `needs:` — a job's dependencies
  only ever name jobs from its own file. The prefixing is visible in the
  generated text output (`generate_text()` renders `Job.name` directly)
  — a deliberate, documented trade-off; see `LIMITATIONS.md`'s "Tool 2"
  section.
- After merging, the combined `Pipeline` is *also* run through
  `validate_or_raise` — this second pass, not the per-file one, is what
  actually catches a cross-file job-name collision introduced by the
  merge layer's own prefixing (no single file's `Pipeline` could ever
  exhibit that on its own).
- `Pipeline.linked_workflows` are unioned across files and deduped by
  `(target, relationship)` (the same key the parser already dedupes on
  per-file) — deliberately not resolved against sibling `Pipeline`
  objects discovered in this same run. That resolution would be new
  interpretive logic; the combined `LINKED WORKFLOWS` section already
  shows every relationship from every file, and a reader can match a
  `uses:`/`workflow_run` target string against another job's `Source:`
  line by eye.
- `generate_text()`, `generate_mermaid()`, and
  `tool1.single_pipeline.generate_documentation()` are reused completely
  unmodified against the combined `Pipeline` — this module's only job is
  building that combined `Pipeline`, never reimplementing generator or
  document-assembly logic.
"""

from __future__ import annotations

import dataclasses
import difflib
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from generators.text_generator import generate_text
from ir.schema import EnvironmentVariable, Job, Pipeline, Secret, SecretScope, SourcePlatform, Trigger
from ir.validate import IRValidationError, validate_or_raise
from llm import get_default_provider
from llm.base import LLMProvider, LLMResult
from parsers.github_actions import GitHubActionsParser
from tool1.single_pipeline import _log_llm_call, _strip_llm_overview, generate_documentation
from tool2.relationships import (
    analyze_relationships,
    render_follows_diagram,
    render_relationship_table,
    render_shared_triggers_note,
)

_WORKFLOW_GLOBS = ("*.yml", "*.yaml")

_CI_DOCS_START = "<!-- ci-docs:start -->"
_CI_DOCS_END = "<!-- ci-docs:end -->"
_CI_DOCS_BLOCK_RE = re.compile(
    re.escape(_CI_DOCS_START) + r".*?" + re.escape(_CI_DOCS_END),
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_workflow_files(path: str) -> List[Path]:
    """
    Resolve `path` to a `.github/workflows`-style folder and return every
    `*.yml`/`*.yaml` file in it, sorted by filename for deterministic,
    reproducible ordering (matching the project's existing determinism
    ethic — declaration-order tie-breaking in `generators.common`, etc.).

    `path` may be a repository root (its `.github/workflows` subfolder is
    used if present) or the workflows folder itself. Raises
    `FileNotFoundError` — a clear operational error, not an IR-validation
    failure — if neither resolves to a directory, or if the resolved
    directory contains no workflow files at all (an empty combined doc
    would otherwise silently look like a valid, if boring, result).
    """
    base = Path(path)
    candidate = base / ".github" / "workflows"
    workflows_dir = candidate if candidate.is_dir() else base

    if not workflows_dir.is_dir():
        raise FileNotFoundError(
            f"'{path}' is not a directory and has no .github/workflows subfolder."
        )

    files = sorted(
        (f for pattern in _WORKFLOW_GLOBS for f in workflows_dir.glob(pattern)),
        key=lambda f: f.name,
    )
    if not files:
        raise FileNotFoundError(
            f"No workflow files (*.yml/*.yaml) found under '{workflows_dir}'."
        )
    return files


# ---------------------------------------------------------------------------
# Merge layer
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Sanitize a workflow filename (with extension, so same-stem/different-
    extension files like ci.yml and ci.yaml can never collide) into a bare
    Mermaid/GH-Actions-job-key-safe identifier: `[A-Za-z_][A-Za-z0-9_]*`."""
    slug = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not slug or not (slug[0].isalpha() or slug[0] == "_"):
        slug = f"_{slug}"
    return slug


def _prefixed(origin: str, name: str) -> str:
    return f"{origin}__{name}"


def _rewrite_job(job: Job, origin: str) -> Job:
    return dataclasses.replace(
        job,
        name=_prefixed(origin, job.name),
        origin=origin,
        dependencies=[_prefixed(origin, dep) for dep in job.dependencies],
    )


def _rewrite_trigger(trigger: Trigger, origin: str) -> Trigger:
    return dataclasses.replace(trigger, origin=origin)


def _rewrite_scope_ref(scope_ref: Optional[str], scope: SecretScope, origin: str) -> Optional[str]:
    """JOB scope's scope_ref is exactly the job name; STEP scope's is
    `"{job_key}.{step_index}"`. PIPELINE scope has no scope_ref at all.
    Only the job-key part ever needs the origin prefix."""
    if scope == SecretScope.PIPELINE or not scope_ref:
        return scope_ref
    job_part, sep, rest = scope_ref.partition(".")
    prefixed = _prefixed(origin, job_part)
    return f"{prefixed}{sep}{rest}" if sep else prefixed


def _rewrite_secret(secret: Secret, origin: str) -> Secret:
    return dataclasses.replace(secret, scope_ref=_rewrite_scope_ref(secret.scope_ref, secret.scope, origin))


def _rewrite_env_var(env_var: EnvironmentVariable, origin: str) -> EnvironmentVariable:
    return dataclasses.replace(env_var, scope_ref=_rewrite_scope_ref(env_var.scope_ref, env_var.scope, origin))


def _merge_pipelines(files: List[Path], pipelines: List[Pipeline], repo_label: str,
                      workflows_dir: Path) -> Pipeline:
    """Build one combined Pipeline from N real, already-parsed-and-validated
    per-file Pipelines. Never mutates any input Pipeline/Job/Trigger/Secret/
    EnvironmentVariable — every rewritten object is newly constructed via
    dataclasses.replace(). See module docstring for the full contract."""
    triggers: List[Trigger] = []
    jobs: List[Job] = []
    secrets: List[Secret] = []
    env_vars: List[EnvironmentVariable] = []
    linked = []
    seen_linked = set()

    for file, pipeline in zip(files, pipelines):
        origin = _slugify(file.name)
        triggers.extend(_rewrite_trigger(t, origin) for t in pipeline.triggers)
        jobs.extend(_rewrite_job(j, origin) for j in pipeline.jobs)
        secrets.extend(_rewrite_secret(s, origin) for s in pipeline.secrets)
        env_vars.extend(_rewrite_env_var(e, origin) for e in pipeline.environment_variables)
        for lw in pipeline.linked_workflows:
            key = (lw.target, lw.relationship)
            if key in seen_linked:
                continue
            seen_linked.add(key)
            linked.append(lw)

    return Pipeline(
        name=f"{repo_label} (unified CI documentation)",
        source_platform=SourcePlatform.GITHUB_ACTIONS,
        source_file=str(workflows_dir),
        triggers=triggers,
        jobs=jobs,
        secrets=secrets,
        environment_variables=env_vars,
        linked_workflows=linked,
    )


def _origin_display_names(files: List[Path], pipelines: List[Pipeline]) -> Dict[str, str]:
    """Origin slug -> that file's own (pre-merge) `Pipeline.name`. Additive,
    read-only helper for `tool2/relationships.py` — NOT part of
    `_merge_pipelines` and does not change what that function returns;
    `_merge_pipelines` discards each per-file `Pipeline.name` (only one
    combined name survives the merge), so this is the one place that
    mapping still exists, built the same way `_merge_pipelines` derives
    `origin` (`_slugify(file.name)`) so the two stay in lockstep by
    construction. See `tool2/relationships.py`'s module docstring for why
    this mapping (not the origin slug itself) is what `workflow_run`/
    `LinkedWorkflow` targets actually reference."""
    return {_slugify(file.name): pipeline.name for file, pipeline in zip(files, pipelines)}


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

def _repo_label(path: str) -> str:
    resolved = Path(path).resolve()
    return resolved.name or str(resolved)


def _output_filename(path: str) -> str:
    return f"{_repo_label(path)}.md"


def _render_relationships_section(combined: Pipeline, origin_display_names: Dict[str, str]) -> str:
    """New Phase 7.5 section, appended after the existing (unmodified)
    generate_documentation() output — never inserted into or replacing any
    of that function's own text/Mermaid contract. Always includes the
    relationship table (informative even when every row is "independent");
    the shared-triggers note and workflow-to-workflow diagram are each
    omitted when there's nothing to say, same idiom as the existing
    generators' conditionally-emitted sections."""
    report = analyze_relationships(combined, origin_display_names)

    parts = ["## Workflow Relationships\n\n", render_relationship_table(report), "\n"]

    shared_note = render_shared_triggers_note(report)
    if shared_note:
        parts.append(shared_note)
        parts.append("\n")

    if report.follows:
        parts.append("### Workflow-to-Workflow Diagram\n\n")
        parts.append(f"```mermaid\n{render_follows_diagram(report)}```\n")

    return "".join(parts)


def _build_documentation(path: str, use_llm: bool = True,
                          provider: Optional[LLMProvider] = None) -> str:
    """
    Parse every workflow file discovered under `path`, validate each
    individually (aborting the whole run, attributed to that file, on any
    error — the same fail-closed boundary Tool 1 uses), merge into one
    combined Pipeline, validate the combined Pipeline too (this second
    pass is what catches a cross-file job-name collision from the merge
    layer's own prefixing), then hand off to the unmodified
    `generate_text`/`beautify`/`generate_documentation`.

    `use_llm` defaults to True, matching `tool1.document_pipeline`'s
    default; `check_repository` below always calls this with
    `use_llm=False`, matching `tool1.check_pipeline`'s existing rationale
    (no committed, bit-reproducible "golden" LLM output to diff against —
    LLM drift stays a Tier 1/4 evaluation concern, not a --check concern).
    """
    files = discover_workflow_files(path)
    pipelines: List[Pipeline] = []
    for file in files:
        pipeline = GitHubActionsParser().parse(str(file))
        try:
            warnings = validate_or_raise(pipeline)
        except IRValidationError as exc:
            print(f"{file}: {exc}", file=sys.stderr)
            raise
        for warning in warnings:
            print(f"{file}: {warning}", file=sys.stderr)
        pipelines.append(pipeline)

    combined = _merge_pipelines(files, pipelines, _repo_label(path), files[0].parent)
    validate_or_raise(combined)  # defensive: catches merge-layer bugs, e.g. a name collision
    origin_display_names = _origin_display_names(files, pipelines)

    llm_result: Optional[LLMResult] = None
    if use_llm:
        active_provider = provider or get_default_provider()
        if active_provider is not None:
            text_output = generate_text(combined)
            llm_result = active_provider.beautify(text_output, combined)
            _log_llm_call(str(path), combined.name, llm_result)

    doc = generate_documentation(combined, llm_result)
    return doc + "\n" + _render_relationships_section(combined, origin_display_names)


# ---------------------------------------------------------------------------
# Marker-based injection
# ---------------------------------------------------------------------------

def _inject_markers(target: Path, doc: str) -> None:
    """Replace the content between `_CI_DOCS_START`/`_CI_DOCS_END` markers
    in `target` with `doc`, preserving the rest of the file. Fails loudly
    rather than guessing an insertion point: `target` must already exist
    and already contain both markers (terraform-docs' convention)."""
    if not target.exists():
        raise FileNotFoundError(
            f"Cannot inject into '{target}': file does not exist. Create it first "
            f"(with {_CI_DOCS_START}/{_CI_DOCS_END} markers already in place)."
        )
    content = target.read_text(encoding="utf-8")
    if not _CI_DOCS_BLOCK_RE.search(content):
        raise ValueError(
            f"'{target}' has no {_CI_DOCS_START}/{_CI_DOCS_END} markers — add them first, "
            f"then re-run to inject the unified documentation there."
        )
    replacement = f"{_CI_DOCS_START}\n{doc}{_CI_DOCS_END}"
    new_content = _CI_DOCS_BLOCK_RE.sub(replacement, content, count=1)
    target.write_text(new_content, encoding="utf-8")


def _extract_injected(content: str) -> Optional[str]:
    """Return the content between an existing marker pair (with exactly the
    one leading newline `_inject_markers` itself inserts stripped back off,
    so it compares cleanly against a fresh `_build_documentation()` string),
    or None if no marker pair is present."""
    match = _CI_DOCS_BLOCK_RE.search(content)
    if match is None:
        return None
    inner = match.group(0)[len(_CI_DOCS_START):-len(_CI_DOCS_END)]
    if inner.startswith("\n"):
        inner = inner[1:]
    return inner


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def document_repository(path: str, output_dir: str = "docs", use_llm: bool = True,
                         provider: Optional[LLMProvider] = None,
                         inject_into: Optional[str] = None) -> Path:
    """Generate the unified documentation for the repository at `path` and
    either write it to `<output_dir>/<repo>.md` (default) or inject it
    between markers in `inject_into` if given. Returns the written/injected
    path."""
    doc = _build_documentation(path, use_llm=use_llm, provider=provider)

    if inject_into is not None:
        target = Path(inject_into)
        _inject_markers(target, doc)
        return target

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / _output_filename(path)
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def check_repository(path: str, output_dir: str = "docs", inject_into: Optional[str] = None) -> bool:
    """
    Compare freshly generated documentation for the repository at `path`
    against either the committed `<output_dir>/<repo>.md` or the current
    contents between markers in `inject_into`, without writing anything.
    Always regenerates with use_llm=False and strips any committed LLM
    overview block before comparing (see `_build_documentation`'s
    docstring for the rationale — reuses
    `tool1.single_pipeline._strip_llm_overview` rather than duplicating
    that regex).

    Missing-target handling, one rule applied consistently: where a Tool 1
    precedent already exists, inherit it verbatim; where a failure mode is
    new (everything --inject-specific has no Tool 1 equivalent), it's a
    distinct operational error instead of being folded into the drift
    exit code.
    - Standalone (no inject_into): a missing `<repo>.md` mirrors
      `tool1.check_pipeline` exactly — prints a message and returns False
      (CLI exit code 1), the same as Tool 1's identical case.
    - inject_into: a missing target file, or a target file with no
      markers, both raise distinct errors (CLI exit code 2 via cli.py's
      generic handler) — only "markers present but content differs"
      returns False (exit code 1), same as the standalone drift case.
    """
    fresh = _build_documentation(path, use_llm=False)

    if inject_into is not None:
        target = Path(inject_into)
        if not target.exists():
            raise FileNotFoundError(f"Cannot check '{target}': file does not exist.")
        content = target.read_text(encoding="utf-8")
        inner = _extract_injected(content)
        if inner is None:
            raise ValueError(
                f"'{target}' has no {_CI_DOCS_START}/{_CI_DOCS_END} markers — add them first, "
                f"then run without --check to inject for the first time."
            )
        committed = _strip_llm_overview(inner)
        label = str(target)
    else:
        out_path = Path(output_dir) / _output_filename(path)
        if not out_path.exists():
            print(f"no committed doc found for {out_path.name} — run without --check to generate it")
            return False
        committed = _strip_llm_overview(out_path.read_text(encoding="utf-8"))
        label = str(out_path)

    if committed == fresh:
        print(f"{label} is up to date")
        return True

    diff = difflib.unified_diff(
        committed.splitlines(keepends=True),
        fresh.splitlines(keepends=True),
        fromfile=f"{label} (committed, deterministic sections)",
        tofile=f"{label} (generated, deterministic sections)",
    )
    print("".join(diff), end="")
    return False
