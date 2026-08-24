# Tier 4 — Pre-Registered Fact-Checklist Findings (Method 9)

**Status note:** this report is newly created, not an update to a prior
version — no earlier `evaluation/tier4_findings/REPORT.md` existed in this
repository before this PR. It covers only the fact-checklist half of Tier 4
(`EVALUATION_PLAN.md` Method 9's three-condition comparison). The
answerability audit (Tool 2, Method 9's second half) has not been run and is
not covered here; see `BUILD_PLAN.md`'s open Tier 4 item.

## Method, in brief

Ten held-out pipelines (`evaluation/held_out_workflows/`) were each
pre-registered as a fact checklist — every objectively checkable fact in the
source YAML (triggers, jobs, steps, dependencies, secrets, conditions,
environment variables) — and committed to the repo *before* any of the three
conditions' outputs were generated, so scoring couldn't be influenced by
already having seen what each condition got right or wrong. Three conditions
were then generated and scored fact-by-fact, blind, against each checklist:

- **Condition 1 (deterministic):** this tool's non-LLM structured text layer.
- **Condition 2 (LLM-polished):** this tool's full pipeline, deterministic
  facts rewritten into prose by `llm/gemini_provider.py`.
- **Condition 3 (naive baseline):** the raw pipeline YAML sent directly to
  the same LLM with a generic, unengineered "explain this pipeline" prompt
  (`evaluation/naive_baseline.py`) — no parser, no IR, no anti-hallucination
  framing.

Each fact was scored **Present** (stated, and correct), **Missing** (never
stated, correct or otherwise), or **False** (stated, and incorrect) —
scored against each pipeline's `evaluation/tier4_scoring/*.scoring.md`,
which used blinded Condition A/B/C labels resolved back to the real
conditions via each pipeline's own `.answer_key.md` (the mapping differs per
pipeline; each was checked individually, not assumed constant). 201 facts
total across the 10 checklists. Full per-fact detail, including the sourced
reason for every non-Present outcome, lives in the checklist files
themselves (`evaluation/tier4_checklists/*.checklist.yml`); this report
summarizes and interprets the aggregate.

Totals were computed programmatically, not by hand, via
`evaluation/tier4_scoring/compute_totals.py` — run fresh against the
committed checklists as the authoritative source for every number below.

## Headline result

| Condition | Present | Missing | False | % Present | % Missing | % False |
|---|---:|---:|---:|---:|---:|---:|
| 1 — Deterministic | 192 | 9 | 0 | 95.5% | 4.5% | 0.0% |
| 2 — LLM-polished | 192 | 9 | 0 | 95.5% | 4.5% | 0.0% |
| 3 — Naive baseline | 107 | 93 | 1 | 53.2% | 46.3% | 0.5% |

Conditions 1 and 2 are identical fact-for-fact across all 201 facts — the
LLM-polishing layer neither adds nor loses any fact relative to the
deterministic layer it rewrites, on this held-out set.

## Correction to this project's previous working figure

An earlier internal working figure for this comparison stated the naive
baseline's False rate as **15.4% (31/201)**. That figure was superseded by
the 0.5% (1/201) figure above, for a single 30-fact block:
`nextjs_build_and_test.dependency.115-144` (the "tests-pass" job's
dependency list).

This is not a case of an error being found and fixed in the usual sense —
both scorings were accurate against the text they were scored from. The
naive baseline for `nextjs_build_and_test` was generated twice, on two
different dates, as two independent, non-deterministic LLM calls of the
same condition: once on 2026-08-20 (commit `f20c036`), and again on
2026-08-22 (commit `5053d08`) as part of an unrelated regeneration to add
environment-variable facts to conditions 1/2 for three pipelines. The
2026-08-20 generation stated the `tests-pass` job's dependencies as "lists
*all* other jobs in the pipeline" — a specific, checkable claim, and a
wrong one: `tests-pass` depends on roughly 29 of the pipeline's other 39
jobs, not all of them. That generation was correctly scored False. The
2026-08-22 regeneration produced different wording for the same fact —
"this job explicitly lists all critical build, lint, and test jobs as
dependencies" — a vaguer, unenumerated characterization that no longer
makes a checkably wrong claim, just an incomplete one. Under the
individually-named-edge convention this project applies consistently
elsewhere (e.g. `scipy_linux`'s dependency facts, `vscode_pr`'s job facts)
— a fact scores Missing when a plausible-sounding but non-specific summary
is offered instead of individually naming the fact itself, and reserves
False for a claim that is concretely, checkably wrong — the currently
committed text (`5053d08`, unchanged since) is correctly scored Missing.
The 2026-08-20 scoring wasn't wrong at the time; the source text underneath
it changed.

**A second, independently observed instance of the same phenomenon:**
`urllib3_ci.matrix.1` (the job `test`'s multi-axis matrix fact) shows the
identical pattern on a single fact rather than thirty. The 2026-08-20
naive-baseline generation enumerated the `python-version` matrix axis as
10 explicit values ("3.10, 3.11, 3.12, 3.13, 3.14, 3.14t, 3.15, `pypy-3.11`,
`3.x`, and a specific `3.12.2`") — conflating the axis's actual 7 base
values with 3 values that only exist via `include:` entries, a specific
and checkably wrong count. The eventual regeneration (`8c63b3b`, after an
intervening `5053d08` attempt failed with a `503` and fell back to an
unprocessed error banner — see `BUILD_PLAN.md`'s PR #57/#58 entries)
instead gives illustrative examples without committing to a count ("a wide
range of Python versions... including specific patch versions, pre-releases,
and PyPy") and correctly separates the `include` entries into their own
section. `matrix.1`'s currently committed verdict is Present in all three
conditions — the vaguer phrasing doesn't misstate anything, it just stops
short of the wrong specific claim the earlier generation made.

Two confirmed instances, both drawn from this project's own primary sources
(`evaluation/tier4_scoring/*.scoring.md` and their git history) rather than
from any external documentation: **naive-baseline verdicts on borderline or
vague fan-in/fan-out claims are not fully stable across independent
regenerations of the same condition** — sensitive to phrasing rather than
reflecting a change in the underlying method's structural strength or
weakness. Both corrections were made before transcription into the
checklists, against each fact's currently committed source text, not after
the fact.

The one remaining genuine False is `cpython_reusable_macos.job.1`: the
naive baseline states the checkout step is pinned to the tag
`actions/checkout@v7.0.0`. The real YAML pins `actions/checkout` to a full
commit SHA, with `# v7.0.0` only as a trailing human-readable comment — a
materially different (and materially more security-relevant) statement
about how the dependency is pinned. This is a concrete, checkable
misstatement, not an omission, and is the only fact across all 603
condition-fact pairs (201 facts × 3 conditions) scored False in this round.

## Revised framing

**The naive baseline's primary demonstrated weakness, measured this way, is
completeness — not confident fabrication.** Given a pipeline's raw YAML and
an unconstrained "explain this" prompt, the model reliably avoids inventing
facts it wasn't given (0.5% False), but just as reliably fails to mention
roughly half of what's actually there (46.3% Missing) — it summarizes and
narrates a plausible-sounding subset rather than working through the file
systematically. This tool's deterministic/IR-mediated approach doesn't win
by suppressing hallucination the naive baseline was otherwise prone to (it
mostly wasn't, on this sample); it wins by exhaustively enumerating facts a
free-form narrative summary naturally skips.

This reframing matters for how the comparison should be read going forward:
"prevents hallucination" overstates the naive baseline's actual failure
mode on this evidence, and risks setting up a stronger claim than the data
supports. "Achieves much higher completeness, at equivalent (near-zero)
factual error rates" is the framing this evidence actually supports.

## Per-pipeline breakdown

| Pipeline | Facts | Tool (P/M/F) | Naive baseline (P/M/F) |
|---|---:|---:|---:|
| celery_python_package | 20 | 20/0/0 | 19/1/0 |
| cpython_reusable_macos | 6 | 2/4/0 | 5/0/1 |
| httpie_code_style | 2 | 2/0/0 | 2/0/0 |
| httpx_test_suite | 6 | 6/0/0 | 6/0/0 |
| nextjs_build_and_test | 82 | 81/1/0 | 22/60/0 |
| pre_commit_main | 5 | 5/0/0 | 5/0/0 |
| requests_lint | 6 | 6/0/0 | 6/0/0 |
| scipy_linux | 35 | 35/0/0 | 23/12/0 |
| urllib3_ci | 11 | 11/0/0 | 11/0/0 |
| vscode_pr | 28 | 24/4/0 | 8/20/0 |

`nextjs_build_and_test` (82 facts, the largest checklist by a wide margin —
41% of all 201 facts) and `vscode_pr` (28 facts) dominate the naive
baseline's Missing count: both are large, many-job pipelines where a
free-form narrative summary structurally cannot enumerate every job,
dependency, and secret the way a systematic per-fact walk can. Pipelines
with few jobs and little structure (`httpie_code_style`, `httpx_test_suite`,
`urllib3_ci`, `requests_lint`, `pre_commit_main`) score near-identically
across all three conditions — there's little for a narrative summary to
miss when there isn't much to summarize.

## The tool's 9 Missing facts

Every one of the tool's 9 Missing facts is a previously-known, independently
corroborated gap, not a new finding from this scoring round:

- **`workflow_call` input metadata** (`cpython_reusable_macos.trigger.1`):
  input names are surfaced, but type, required/optional status, and default
  value are not.
- **Dynamic job-level metadata** (`cpython_reusable_macos.job.1`): a
  job-level `name:` expression and `timeout-minutes:` are never rendered.
- **Step-level `if:` conditions** (`cpython_reusable_macos.step.2`,
  `.condition.1`; `vscode_pr`'s two step-condition facts): `generators/text_generator.py`'s
  `_step_lines` has no code path that surfaces a step-level condition in
  either the deterministic or LLM-polished output. This is the single most
  frequently reconfirmed gap in this project's evaluation work — found here,
  and independently re-found via Tier 2 error injection (PR #59) and Tier 3's
  natural-pairs comparison against `black`'s real documentation (PR #60).
- **`vscode_pr.job.17` / `.step.1`**: a job/step pair beyond
  `generators/text_generator.py`'s `_STEP_LIST_CAP` (10) truncation point —
  a deliberate, signal-don't-silently-drop truncation (`"... and N more
  steps"`), not a silent loss, but still scores Missing for the specific
  late-step fact it doesn't individually name.
- **`nextjs_build_and_test.trigger.2`**: one trigger-level fact not
  individually surfaced in the output.

None of these 9 facts are new; all are already documented in
`LIMITATIONS.md`. This scoring round is their first appearance as part of a
pre-registered, quantitative protocol rather than an ad hoc finding.

## Threats to validity

See `EVALUATION_PLAN.md`'s "Threats to validity — single-author evaluation"
section, which applies in full here: scoring was performed by this
project's sole author, not blind reviewers, against a fact checklist this
same author also wrote. The pre-registration protocol (checklist committed
before any condition's output was generated) mitigates outcome-contingent
checklist authorship specifically, but does not substitute for independent
scoring. The 0.5% False figure in particular rests on the correctness of a
single scoring judgment (the `nextjs_build_and_test.dependency.115-144`
reclassification above) — the reasoning is recorded in detail in
`evaluation/tier4_checklists/nextjs_build_and_test.checklist.yml`'s own
fact-level detail fields for independent verification.
