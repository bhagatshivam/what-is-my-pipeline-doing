# CI Pipeline Documentation Tool

## Current status

Tool 1 (single-pipeline documentation) is implemented end-to-end for GitHub Actions: YAML → parser → intermediate representation → structural validation → Markdown + Mermaid generation, with no LLM in the loop yet. Tool 2 (multi-pipeline) and the LLM rewriting layer described later in this document are architecture, not yet built — see "Not yet implemented" below.

### Using Tool 1

    python cli.py tool1 path/to/workflow.yml

Parses the workflow, validates the resulting intermediate representation, and writes `docs/<workflow-name>.md` (Markdown text plus a Mermaid diagram). Add `--check` to compare freshly generated output against the committed doc instead of writing it, without touching the file — useful in CI to catch documentation drift:

    python cli.py tool1 path/to/workflow.yml --check

Exit codes:
- `0` — success, or `--check` found no drift
- `1` — `--check` found the committed doc has drifted from the source YAML
- `2` — parse/input/operational failure (bad path, unparseable or empty YAML, etc.)
- `3` — the YAML parsed, but the resulting IR is structurally invalid (e.g. a job depends on a job that doesn't exist) — nothing is written

### Not yet implemented

- The LLM rewriting layer (Phase 5) — today's output is the deterministic text/Mermaid generators' output directly, not LLM-rewritten prose.
- Tool 2 / multi-pipeline documentation (Phase 6).

See `LIMITATIONS.md` for the full list of known gaps and unmodeled GitHub Actions concepts.

## What is my CI pipeline doing?

This tool automatically generates human-readable documentation — Markdown text plus Mermaid diagrams — directly from CI pipeline configuration files (starting with GitHub Actions YAML). It works in two modes:

- **Tool 1 — single pipeline:** point it at one workflow file, get back a plain-English explanation of what triggers it, what jobs run and in what order, what each step does, and what secrets/variables it needs, alongside a visual flowchart of the job dependency graph.
- **Tool 2 — multi-pipeline:** point it at a whole repository, get back one unified picture of everything the CI setup does — across every workflow file, showing which pipelines fire on which events and how they relate to each other.

This is an MSc dissertation project at the University of Manchester, supervised by Professor Suzanne Embury.

## The problem this tackles

CI/CD pipelines are usually defined as configuration-as-code — YAML files describing triggers, jobs, steps, secrets, and conditional logic. That's great for automation, but it's genuinely hard for a human to read:

- A real project can have several pipeline files, each hundreds of lines long, with cross-file dependencies and conditional branches.
- It's often unclear exactly what quality checks run, and under what circumstances, once every pipeline is considered together.
- New developers joining a codebase have no quick way to understand what conditions their code has to satisfy before it's mergeable.
- Debugging a pipeline, or changing one safely, is risky precisely because the cumulative effect of all the rules together isn't documented anywhere.

Bajpai & Lewis (2022) make the case that this isn't just an inconvenience — undocumented CI/CD pipelines are a genuine security and process risk, because developers can't fully reason about what their own pipelines are doing.

## Why this project exists

Pipeline YAML is machine-optimized, not human-optimized. Nobody sits down and writes prose documentation for their `.github/workflows/` folder, and even if they do, it goes stale the moment the YAML changes. This project investigates whether that documentation can instead be *generated automatically and kept honest*, by extracting facts systematically from the config itself rather than relying on a human to write (and maintain) a separate description by hand.

The architecture is deliberately built so the LLM never sees raw YAML — a Python layer deterministically extracts and structurally validates the facts first (triggers, jobs, dependencies, secrets), and the LLM's only job is turning those already-extracted, validated facts into readable prose and diagrams. This keeps the tool's output grounded in what the pipeline actually specifies, rather than an LLM's best guess at interpreting YAML directly.

## How this differs from what already exists

There are tools that touch parts of this problem, but nothing that combines all of it:

- **Diagram-only visualizers** — some tools will draw a graph of jobs/steps from a workflow file, but they stop at the visual: no natural-language explanation of *why* something runs or what it means for a developer's code.
- **Native platform features** — GitHub Actions (and other CI platforms) show you a live run's job graph and logs in their own UI, but this only describes *one specific run that already happened* — it doesn't explain the pipeline's full logic across all possible triggers and branches, and it's entirely platform-specific.
- **General-purpose AI repo-documentation generators** — tools that point an LLM at a whole codebase and ask for documentation can technically be pointed at YAML files too, but they treat CI config the same as any other code: no structured understanding of CI-specific semantics (triggers, job dependency graphs, secrets, conditional execution), and no way to unify multiple pipeline files into one coherent picture of "what happens when I push."

None of these combine a **platform-agnostic intermediate representation** with **structured fact-extraction**, **natural-language explanation**, and **multi-file unification** specifically for CI pipeline semantics — that gap is what this project sets out to fill.

## Scope of the current prototype

Building and evaluating a complete version of both Tool 1 and Tool 2 for **GitHub Actions only** first. Support for other platforms (GitLab CI, CircleCI, Jenkins) is planned as a later extension once the GitHub Actions prototype is solid — see `BUILD_PLAN.md` for the full phase-by-phase plan.

## Project documents

- `PROJECT_PLAN.md` — architecture reference (layers, IR schema, design rationale)
- `BUILD_PLAN.md` — phase-by-phase build plan (start here for build order)
- `WEEKLY_PLAN.md` — calendar/weekly schedule
- `EVALUATION_PLAN.md` — evaluation methodology
