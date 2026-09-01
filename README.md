# What Is My CI Pipeline Doing?

Automatically generate human-readable documentation for GitHub Actions workflows — a deterministic Markdown fact sheet and a Mermaid job-dependency diagram, with an optional LLM-written overview layered on top for readability.

This is an MSc Computer Science dissertation project at the University of Manchester, created by Shivam Balasaheb Bhagat and supervised by Professor Suzanne Embury. It targets a specific, real gap: CI pipeline configuration and its documentation drift apart because keeping them in sync depends on a human noticing a change, remembering to update a doc, and describing it correctly — three independent steps that this project's own survey of real open-source repositories found don't reliably all happen together, even in actively maintained projects (see [`evaluation/documentation_practices_survey/REPORT.md`](evaluation/documentation_practices_survey/REPORT.md)).

The core architecture is a strict pipeline: a parser extracts facts from the workflow YAML into a typed intermediate representation, deterministic generators turn that IR into text and a diagram, and an optional Gemini polishing layer rewrites the deterministic facts into prose — the LLM never sees the raw YAML, only the already-extracted, already-validated fact sheet.

> **Prototype scope:** GitHub Actions is the only supported CI platform at present. See [LIMITATIONS.md](LIMITATIONS.md) for supported concepts and known gaps.

## What it does

| Command | Input | Output |
| --- | --- | --- |
| `tool1` | One `.yml` or `.yaml` workflow | One Markdown document and Mermaid diagram |
| `tool2` | A repository root or `.github/workflows` directory | One combined Markdown document, Mermaid diagram, and a cross-workflow relationship analysis for all discovered workflows |

Both tools share the same pipeline:

```text
GitHub Actions YAML → parser → typed intermediate representation → validation → deterministic text + Mermaid diagram → optional LLM overview
```

The parser extracts CI-specific facts such as triggers, jobs, dependencies, steps, matrices, conditions, secrets, permissions, and environment variables. Validation happens before any documentation is written: if the extracted structure is invalid — for example, a job depends on a job that does not exist, or dependencies form a cycle — the command stops rather than producing misleading documentation.

Tool 2 additionally discovers every workflow file in a repository, merges their facts into one combined document (keeping each job's originating file distinguishable so a shared job name across files can't be confused), and analyses relationships *between* workflows — which ones trigger each other via `workflow_run`, which share triggers with no guaranteed ordering, and which are entirely independent — rendering a `## Workflow Relationships` table and, when a cross-file edge exists, a separate workflow-to-workflow Mermaid diagram.

## Evaluation results

The project's evaluation (`EVALUATION_PLAN.md`) is entirely self-conducted — recruiting developer evaluators was ruled out by supervisor guidance — and spans four tiers of automated, stress-testing, comparative, and pre-registered self-scored methods. As of this README, **Tiers 1–4 are complete.**

The headline result, from Tier 4's pre-registered fact-checklist protocol (201 facts, hand-enumerated from 10 held-out real-world workflows before any output was generated, then scored present/missing/false):

| Condition | Present | Missing | False |
| --- | ---: | ---: | ---: |
| Deterministic output (no LLM) | 192 (95.5%) | 9 (4.5%) | 0 (0.0%) |
| LLM-polished output | 192 (95.5%) | 9 (4.5%) | 0 (0.0%) |
| Naive baseline (raw YAML → generic "explain this" LLM prompt) | 107 (53.2%) | 93 (46.3%) | 1 (0.5%) |

The honest framing, straight from `LIMITATIONS.md`'s dated evaluation entry: **the tool's demonstrated advantage over a naive raw-YAML-to-LLM baseline is completeness, not hallucination-prevention.** The naive baseline turned out to reliably avoid inventing facts it wasn't given (0.5% false) — it just as reliably failed to mention roughly half of what was actually there (46.3% missing), narrating a plausible-sounding subset rather than working through the file systematically. A companion answerability audit (five ground-truth questions checked against both outputs across the same 10 pipelines) found the naive baseline's sharpest weak spot is specifically secrets and external-action attribution, not a uniform failure across the board.

This is a short summary, not the full picture — see [`EVALUATION_PLAN.md`](EVALUATION_PLAN.md) for the complete methodology across all four tiers, and [`evaluation/tier4_findings/REPORT.md`](evaluation/tier4_findings/REPORT.md) / [`evaluation/tier4_answerability/REPORT.md`](evaluation/tier4_answerability/REPORT.md) for the full per-pipeline results, corrections, and threats-to-validity discussion.

## How to run it

### 1. Clone and install locally

You need Git and Python 3.10 or later.

```bash
git clone https://github.com/bhagatshivam/what-is-my-pipeline-doing.git
cd what-is-my-pipeline-doing
python -m venv .venv
```

Activate the virtual environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. Document one workflow with Tool 1

From the tool's repository root, run:

```bash
python cli.py tool1 .github/workflows/<workflow-file>.yml --no-llm
```

For example:

```bash
python cli.py tool1 .github/workflows/ci.yml --no-llm
```

The deterministic document is written to `docs/ci.md`.

### 3. Document a repository with Tool 2

Give Tool 2 either a repository root or its `.github/workflows` folder:

```bash
python cli.py tool2 /path/to/a/repository --no-llm
```

It discovers all `*.yml` and `*.yaml` files in that repository's `.github/workflows` folder, validates every workflow, merges their facts safely, analyses cross-workflow relationships, and writes `docs/<repository-folder-name>.md`.

The `docs/` directory is created relative to the directory from which you run the command. If you want the generated document inside the target repository, run the tool from there:

```bash
cd /path/to/a/repository
python /path/to/what-is-my-pipeline-doing/cli.py tool2 . --no-llm
```

### Run the test suite and static checks

```bash
pytest -q -m "not slow"
ruff check .
```

Golden-document tests cover real single-workflow and multi-workflow fixtures. Evaluation scripts and results are under `evaluation/`.

## Optional LLM layer

The deterministic output is the reliable core of the tool and works fully offline after installation — it includes every extracted fact and the Mermaid diagram(s). The LLM is optional: it only adds a `## Overview` section of clearer prose above the deterministic fact block. Everything below the Overview — the fact block and diagram(s) — is never rewritten or replaced.

The current working provider is **Google Gemini** (`llm/gemini_provider.py`). It never receives the raw YAML file — it receives only the deterministic fact sheet after parsing and structural validation, with an explicit system prompt instructing it not to add, infer, or omit any fact.

### Use deterministic output only

Use `--no-llm` whenever you do not want to use an external LLM, do not have an API key, or want fully reproducible output:

```bash
python cli.py tool1 .github/workflows/ci.yml --no-llm
python cli.py tool2 /path/to/a/repository --no-llm
```

If you omit `--no-llm` but have not configured an API key, the command also completes with deterministic output only.

### Enable Gemini prose

1. Create a Gemini API key through [Google AI Studio](https://aistudio.google.com/).
2. Set it in your terminal before running the command.

```bash
# macOS / Linux
export GEMINI_API_KEY="your-api-key"

# Windows PowerShell
$env:GEMINI_API_KEY = "your-api-key"
```

Then run Tool 1 or Tool 2 without `--no-llm`:

```bash
python cli.py tool1 .github/workflows/ci.yml
python cli.py tool2 /path/to/a/repository
```

By default, the tool uses `gemini-2.5-flash` with a fixed low temperature of `0.2`, because this layer is for factual rewriting rather than creative generation.

### Select a Gemini model

Set `GEMINI_MODEL` before running the command. Use the exact identifier of a Gemini model available to your API key and account.

```bash
# macOS / Linux
export GEMINI_MODEL="gemini-2.5-flash"

# Windows PowerShell
$env:GEMINI_MODEL = "gemini-2.5-flash"

python cli.py tool1 .github/workflows/ci.yml
```

To use another available Gemini model, replace the value, for example:

```bash
export GEMINI_MODEL="<your-available-gemini-model>"
```

Only Gemini is a working provider in this prototype. The Ollama module (`llm/ollama_provider.py`) is an interface stub for future local-model support; it is not a runnable option yet.

If Gemini is unavailable, times out, or returns an unusable response (including its own explicit "I'm not confident rewriting this safely" escape hatch), the tool falls back safely to byte-identical deterministic documentation instead of failing or substituting unverified prose.

## Keeping documentation in sync

Use `--check` in local checks or CI to see whether generated documentation has drifted from its source workflow. It does not change files.

```bash
python cli.py tool1 .github/workflows/ci.yml --check
python cli.py tool2 /path/to/a/repository --check
```

`--check` always compares only the deterministic sections. LLM prose is intentionally excluded because it is not byte-for-byte reproducible and does not need an API key in CI.

Exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | Success, or no documentation drift found |
| `1` | `--check` found drift or no committed generated document exists |
| `2` | Input, parsing, path or operational error |
| `3` | Parsed workflow produced an invalid intermediate representation; no documentation was written |

## Insert Tool 2 output into a README

Tool 2 can replace a marked section in an existing README rather than create a standalone document. First add these markers to the target file:

```html
<!-- ci-docs:start -->
<!-- ci-docs:end -->
```

Then run:

```bash
python cli.py tool2 /path/to/a/repository --no-llm --inject /path/to/a/repository/README.md
```

To check the injected content without changing the README:

```bash
python cli.py tool2 /path/to/a/repository --check --inject /path/to/a/repository/README.md
```

The command fails clearly if the target file or markers do not exist; it never guesses where to insert generated text. (`--inject` is a Tool 2-only flag — Tool 1 does not support it.)

## Examples

Real generated output — not mocked, not hand-edited — lives in two places:

- [`samples/`](samples/README.md) — deterministic/LLM-polished pairs for four fixtures, chosen to illustrate specific behaviours: a real dependency diagram, the "all jobs independent" fallback note, workflows that trigger each other across files, and workflows that don't. Start with `samples/README.md` for what to look at in each pair.
- [`docs/`](docs/) — the committed golden documentation for every development fixture workflow used by the test suite, generated by the exact same code paths as the CLI.

## Project documents

- [PROJECT_PLAN.md](PROJECT_PLAN.md) — architecture and design rationale
- [BUILD_PLAN.md](BUILD_PLAN.md) — implementation history and phase plan
- [EVALUATION_PLAN.md](EVALUATION_PLAN.md) — evaluation methodology and results
- [LIMITATIONS.md](LIMITATIONS.md) — known gaps and intentionally unmodelled GitHub Actions concepts

## Licence and academic use

This repository is released under the [MIT License](LICENSE). It remains an academic prototype: please check `LIMITATIONS.md` before relying on generated documentation for production-critical decisions.
