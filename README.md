# What Is My CI Pipeline Doing?

Automatically generate human-readable documentation for GitHub Actions workflows. The tool produces a deterministic Markdown fact sheet and a Mermaid job-dependency diagram; it can also add an optional Gemini-written overview to make the facts easier to read.

This is an MSc Computer Science dissertation project at the University of Manchester, created by Shivam Balasaheb Bhagat and supervised by Professor Suzanne Embury.

> **Prototype scope:** GitHub Actions is the only supported CI platform at present. See [LIMITATIONS.md](LIMITATIONS.md) for supported concepts and known gaps.

## What it does

| Command | Input | Output |
| --- | --- | --- |
| `tool1` | One `.yml` or `.yaml` workflow | One Markdown document and Mermaid diagram |
| `tool2` | A repository root or `.github/workflows` directory | One combined Markdown document and Mermaid diagram for all discovered workflows |

Both tools use the same safe pipeline:

```text
GitHub Actions YAML â†’ parser â†’ typed intermediate representation â†’ validation â†’ deterministic text + Mermaid diagram â†’ optional LLM overview
```

The parser extracts CI-specific facts such as triggers, jobs, dependencies, steps, matrices, conditions, secrets, permissions, concurrency and deployment environments. Validation happens before any documentation is written. If the extracted structure is invalidâ€”for example, a job depends on a job that does not exist, or dependencies form a cycleâ€”the command stops rather than producing misleading documentation.

## Quick start

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

It discovers all `*.yml` and `*.yaml` files in that repository's `.github/workflows` folder, validates every workflow, merges their facts safely, and writes `docs/<repository-folder-name>.md`.

The `docs/` directory is created relative to the directory from which you run the command. If you want the generated document inside the target repository, run the tool from there:

```bash
cd /path/to/a/repository
python /path/to/what-is-my-pipeline-doing/cli.py tool2 . --no-llm
```

## Optional LLM beautification

The deterministic output is the reliable core of the tool and works offline after installation. It includes all extracted facts and the Mermaid diagram. The LLM is optional: it only adds an `## Overview` section of clearer prose.

The current working provider is **Google Gemini**. It never receives the raw YAML file. It receives only the deterministic fact sheet after parsing and structural validation. The diagram and deterministic facts are never rewritten or replaced.

### Use deterministic output only

Use `--no-llm` whenever you do not want to use an external LLM, do not have an API key, or want the fully reproducible output:

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

Only Gemini is a working provider in this prototype. The Ollama module is an interface stub for future local-model support; it is not a runnable `--model` option yet.

If Gemini is unavailable, times out, or returns an unusable response, the tool falls back safely to deterministic documentation instead of failing or substituting unverified prose.

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

The command fails clearly if the target file or markers do not exist; it never guesses where to insert generated text.

## Why Tool 2 needs a merge layer

Repositories can reuse the same job name in different workflow files. Tool 2 preserves each workflow's origin and prefixes jobs and their dependencies internally before combining them. This prevents a trigger in one workflow from being shown as starting an unrelated job in another workflow, while retaining a single, readable combined document and diagram.

## Development and verification

Run the test suite and static checks from the repository root:

```bash
pytest -q -m "not slow"
ruff check .
```

Golden-document tests cover real single-workflow and multi-workflow fixtures. Evaluation scripts and results are under `evaluation/`.

## Project documents

- [PROJECT_PLAN.md](PROJECT_PLAN.md) â€” architecture and design rationale
- [BUILD_PLAN.md](BUILD_PLAN.md) â€” implementation history and phase plan
- [EVALUATION_PLAN.md](EVALUATION_PLAN.md) â€” evaluation methodology
- [LIMITATIONS.md](LIMITATIONS.md) â€” known gaps and intentionally unmodelled GitHub Actions concepts

## Licence and academic use

This repository is an academic prototype. Please check the repository licence and the limitations before relying on generated documentation for production-critical decisions.
