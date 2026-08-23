# Tier 3 — Correctness Check (this repo's own CI)

Method 7 of `EVALUATION_PLAN.md` ("Correctness check"): compare the tool's
documentation against a real pipeline's actual GitHub Actions execution
history — GitHub's own recorded truth about what ran, when, and in what
order, rather than a manifest or human prose. Framed the same way as the
beautify-rewrite experiment and the Tier 2/3 work before it: a bounded
try-it experiment, reported honestly whether it works cleanly or hits a
wall.

## Subject and why

This repository's own `.github/workflows/ci.yml` — the workflow producing
the `test`/`lint` checks already observed on every PR this session. Using
our own repo avoids triggering CI on someone else's infrastructure for a
comparison they didn't ask for, and gives dozens of already-real,
already-observed executions to compare against for free — no new CI run was
needed for this report.

## The workflow file (baseline, read before generating anything)

`.github/workflows/ci.yml`, in full:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: ruff check ir/ parsers/ tests/ generators/ tool1/ tool2/ llm/ evaluation/ cli.py scripts/

  test:
    runs-on: ubuntu-latest
    needs: [lint]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: pytest tests/ -m "not slow"
```

Two triggers (push to `main`, PR to `main`), two jobs (`lint` independent,
`test` depending on `lint` via `needs: [lint]`), no matrix, no conditions,
no secrets, no environment variables. Deliberately simple — chosen because
it's the pipeline with the most real, already-observed execution history
available to compare against.

## Real execution history pulled via GitHub API

- **75 `push`-event runs** and **70 `pull_request`-event runs** recorded for
  this workflow — both trigger types genuinely fire, matching the YAML's two
  `on:` entries.
- **Job-level detail, 2 runs** (`list_workflow_jobs`):

  | Run (commit) | `lint` job | `test` job | Dependency confirmed? |
  |---|---|---|---|
  | PR #60 merge (`f92cf39`, [run 32608644002](https://github.com/bhagatshivam/what-is-my-pipeline-doing/actions/runs/32608644002)) | 00:44:58 → 00:45:13, success | created 00:45:13, ran 00:45:16 → 00:45:40, success | Yes — `test`'s `created_at` (00:45:13) matches `lint`'s `completed_at` (00:45:13) exactly; GitHub only creates the `test` job once `lint` finishes |
  | PR #58 merge (`0d8fcab`, [run 32550330778](https://github.com/bhagatshivam/what-is-my-pipeline-doing/actions/runs/32550330778)) | 03:56:13 → 03:56:29, success | created 03:56:29, ran 03:57:08 → 03:57:41, success | Same pattern — `test` created at exactly `lint`'s completion timestamp |

- **Step-level detail, both runs**: `Run actions/checkout@v4` → `Run actions/setup-python@v5` → `Run pip install -r requirements.txt` → `Run ruff check ...` (lint) / `Run pytest tests/ -m "not slow"` (test) — matching the YAML's literal commands, in order, as separate recorded steps.
- **Job log content, `lint` job of run 32608644002** (`get_job_logs`, real log lines, not metadata):
  ```
  ##[group]Run actions/setup-python@v5
  with:
    python-version: 3.11
    ...
  ##[group]Installed versions
  Successfully set up CPython (3.11.16)
  ##[endgroup]
  ##[group]Run pip install -r requirements.txt
  ...
    pythonLocation: /opt/hostedtoolcache/Python/3.11.16/x64
  ...
  ##[group]Run ruff check ir/ parsers/ tests/ generators/ tool1/ tool2/ llm/ evaluation/ cli.py scripts/
    ruff check ir/ parsers/ tests/ generators/ tool1/ tool2/ llm/ evaluation/ cli.py scripts/
  ...
  All checks passed!
  ```
  Confirms the resolved Python version (**3.11.16**) that the `python-version: "3.11"` input actually installed, closing the one gap flagged in the investigation phase as possibly unconfirmable from job metadata alone — the log fetch worked cleanly on the first try, no rate-limit or format issues encountered.
- **2 known historical failures** in the 75-run push history: PR #47 and PR #49 merges (2026-08-04) — already documented in `BUILD_PLAN.md`/`LIMITATIONS.md` as accepted red-CI exceptions predating this session. Not new information, but real confirmation that the pipeline does fail sometimes and that failure is visible in this same history — relevant context for judging whether the tool's output overclaims reliability (it doesn't; see below).

## Tool's output

Generated via `parsers.github_actions.GitHubActionsParser` → `ir.validate.validate_pipeline` → `generators.text_generator.generate_text` → `llm.gemini_provider.GeminiProvider.beautify`, exactly as `cli.py tool1` would. **Zero validation issues.**

### Deterministic output (verbatim)

```text
Pipeline: CI
Source: .github/workflows/ci.yml (GitHub Actions)

AT A GLANCE
This workflow runs on pushes to `main` and pull requests.
It contains 2 jobs: 1 with no declared dependencies, 1 depending on other jobs.

WHEN IT RUNS
- Runs on every push to main branch
- Runs on every pull request targeting main branch

EXECUTION SUMMARY
Independent jobs (no dependencies): lint
test runs after lint

IMPLEMENTATION DETAILS
1. lint — runs on ubuntu-latest; 4 steps
   - actions/checkout@v4 (https://github.com/actions/checkout)
   - actions/setup-python@v5 (https://github.com/actions/setup-python)
   - pip install -r requirements.txt
   - ruff check ir/ parsers/ tests/ generators/ tool1/ tool2/ llm/...
2. test — runs on ubuntu-latest; 4 steps; after lint
   - actions/checkout@v4 (https://github.com/actions/checkout)
   - actions/setup-python@v5 (https://github.com/actions/setup-python)
   - pip install -r requirements.txt
   - pytest tests/ -m "not slow"
```

### LLM-polished output (verbatim, live call — `gemini-2.5-flash`, temperature 0.2, 518 input / 249 output tokens, ~4.6s)

> This CI pipeline, defined in `.github/workflows/ci.yml` as a GitHub Actions
> workflow, runs automatically on every push to the `main` branch and on
> every pull request targeting the `main` branch. It consists of two jobs:
> `lint` and `test`.
>
> The `lint` job executes first on an `ubuntu-latest` environment. Its steps
> involve checking out the repository using `actions/checkout@v4`, setting
> up Python with `actions/setup-python@v5`, installing dependencies from
> `requirements.txt` using `pip install`, and finally running `ruff check`
> across specified directories including `ir/`, `parsers/`, `tests/`,
> `generators/`, `tool1/`, `tool2/`, and `llm/...`.
>
> Following the successful completion of the `lint` job, the `test` job
> begins, also running on `ubuntu-latest`. This job similarly checks out the
> repository with `actions/checkout@v4`, sets up Python using
> `actions/setup-python@v5`, and installs dependencies via `pip install -r
> requirements.txt`. Its final step is to execute `pytest tests/` with the
> marker `"not slow"`.

## Fact-by-fact comparison

| # | Tool claim | Real execution data | Match? |
|---|---|---|---|
| 1 | Triggers: push to main, PR to main | 75 push-event + 70 pull_request-event runs recorded | Yes |
| 2 | 2 jobs; `test` depends on `lint` ("`test` runs after `lint`") | `test`'s `created_at` matches `lint`'s `completed_at` exactly, in both runs checked | Yes |
| 3 | Both jobs run on `ubuntu-latest` | `labels: ["ubuntu-latest"]` on every real job examined | Yes |
| 4 | Step order per job: checkout → setup-python → pip install → ruff/pytest | Identical order and step names in both runs' `list_workflow_jobs` output | Yes |
| 5 | Python version 3.11 (from `with: python-version: "3.11"`, shown implicitly via the `actions/setup-python@v5` step) | Job log: `Successfully set up CPython (3.11.16)` | Yes — resolved patch version (3.11.16) is a real refinement of the declared minor version (3.11), not a contradiction |
| 6 | `lint` step 4 name: `ruff check ir/ parsers/ tests/ generators/ tool1/ tool2/ llm/...` (truncated, trailing `...`) | Job log's real executed command: `ruff check ir/ parsers/ tests/ generators/ tool1/ tool2/ llm/ evaluation/ cli.py scripts/` (full, untruncated) | **Partial** — see below |
| 7 | LLM overview's restatement of triggers, job order, and step sequence | Matches the deterministic layer (itself confirmed against real data above) faithfully, no invented facts | Yes |

### Item 6, in detail

The `lint` job's fourth step has no explicit `name:` in the YAML, so
`parsers/github_actions.py`'s `_step_name_fallback` derives one from the
`run:` command's first line, truncated to 60–75 characters via
`_truncate_at_word_boundary` — landing at `...tool1/ tool2/ llm/...`, cutting
off ` evaluation/ cli.py scripts/` from the real, actually-executed command
(confirmed verbatim in the job log). This is **not a contradiction**: the
tool never states the shown text is the complete command, and the trailing
`...` is an explicit truncation marker — the same deliberate,
signal-don't-silently-drop pattern already documented in `LIMITATIONS.md`
for other over-length values (e.g. multiline `with:` blocks capped with a
"`[+N more lines]`" marker). `Step.value` (the parser's internal raw_extras)
does hold the full, untruncated command — it's `_step_lines`'s rendering
choice, not a data-loss bug, that only `Step.name` reaches the output. Still
worth flagging as the one place in this comparison where the real ground
truth (the job log) has more information than what the tool actually
prints, however honestly the omission is signaled.

## Synthesis

**Six of seven comparison points match exactly; the seventh is an honestly-flagged truncation, not a misstatement.** Every structural claim the tool makes about this workflow — both triggers, the job dependency, the runner, the step order, and (via the one log fetch) even the resolved Python patch version — is independently confirmed by GitHub's own execution records rather than by a manifest this project wrote itself. This is a cleaner result than either Tier 2 or Tier 3's natural-pairs comparison produced, which makes sense: `ci.yml` is the simplest pipeline in this project's entire fixture/held-out/dev set (2 jobs, no matrix, no conditions, no secrets), so there was little surface area for anything to go wrong.

That simplicity is itself a limitation of this particular try: this method's real test is whether the tool's claims survive contact with *real, externally-recorded* ground truth, and a 2-job linear pipeline doesn't stress that nearly as hard as, say, a dynamic matrix or a workflow_run chain would. The comparison is honest and clean, but it's a light one — the natural-pairs comparisons on `scipy_linux`/`tox`/`black` (12-job, matrix, and cross-file-trigger pipelines respectively) put more real structure under test than this one did. Framed the same way as the beautify-rewrite experiment: this is a legitimate, bounded try-it result, reported as it actually came out — clean, with one small, correctly-caveated, non-contradictory gap — not a disappointing one just because it didn't surface a dramatic finding.

No live CI run was triggered for this report; all execution data is drawn
from the existing 145-run history plus one job-log fetch, both already
public GitHub Actions records for this repository.
