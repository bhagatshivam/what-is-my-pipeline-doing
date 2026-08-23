# Beautify full-rewrite experiment — comparison report

**Branch:** `experiment/beautify-rewrite-prompts` (never to be merged to `main`).
**Status:** NOT part of the live Tier 4 evaluation. Does not modify
`evaluation/tier4_scoring/`, `evaluation/tier4_checklists/`, or
`llm/gemini_provider.py`'s real `SYSTEM_PROMPT`. Reuses only already-existing,
unmodified plumbing (`generate_text`, `llm.gemini_provider._generate_once`/
`_build_user_prompt`) with a different `system_instruction` substituted in.

Question being tested: can the beautification layer do a **fuller rewrite** of
the deterministic fact sheet — not just a short prose overview prepended above
it — while still passing a fact-coverage check as strict as Tier 4's?

## Candidates

- **Candidate 0 (control)** — `llm/gemini_provider.py`'s real, unmodified
  `SYSTEM_PROMPT`: produces a 2-4 paragraph overview only.
- **Candidate 1 (structured rewrite)** — fixed section headings (Overview /
  When It Runs / What Happens / Dependencies / Secrets & Configuration),
  full replacement of the fact sheet.
- **Candidate 2 (narrative rewrite)** — free-form narrative walkthrough,
  reader's-choice organization, full replacement of the fact sheet.

All three take **only** the deterministic fact sheet (`generate_text()`'s
output) as input — never raw YAML — same architectural constraint as the real
`beautify()`.

## Generation notes

- 6 calls planned, 7 made (`nextjs_build_and_test`/candidate 1 hit a
  `504 DEADLINE_EXCEEDED` on its first attempt at the bumped 60s timeout and
  succeeded on retry — confirms the timeout bump was warranted, not just
  precautionary, for this pipeline's fuller-rewrite candidates).
- All 6 final outputs are genuine LLM generations, no fallback used.
- Raw outputs and both fact sheets are alongside this report in
  `evaluation/rewrite_experiment/outputs/`.

## Scoring method

Each candidate's **raw output text** (not wrapped in a full title+diagram
document) was scored fact-by-fact against that pipeline's existing
pre-registered checklist (`evaluation/tier4_checklists/*.checklist.yml`,
read-only, unmodified) as Present / Missing / False — same rubric Tier 4 uses.
Two scoring conventions, applied uniformly across all three candidates so no
candidate is held to a different bar:

1. **Compound facts** (e.g. "Job X exists; uses: reusable-workflow.yml", or a
   value like "= 20") are scored **Present only if every component is stated**.
   Naming a job without attributing its specific reusable-workflow delegation,
   or naming an env var without its value, scores Missing, not partial credit
   — there's no partial bucket in Present/Missing/False, and giving it wouldn't
   guard against length bias.
2. Dependency facts ("Job X depends on Job Y") require an **explicit,
   individually-named** dependency statement. A vague summary ("runs after
   nearly all other jobs") doesn't confirm any specific edge and scores every
   edge fact Missing.

No length/polish credit: a longer, more confident output was never scored
Present on a fact unless that fact was concretely, individually stated.

**Shared limitation, not a candidate defect:** `nextjs_build_and_test.trigger.2`
("restricted to opened/synchronize event types") is **absent from the fact
sheet itself** — its `WHEN IT RUNS` section says only "Runs on every pull
request." No candidate could include this without violating "don't add a
fact not in the fact sheet below" — so all three score Missing on this one
fact for the same reason, and it's excluded from the comparison between
candidates below.

## Results

### `httpie_code_style` (2 facts) — sanity check

| fact_id | Candidate 0 | Candidate 1 | Candidate 2 |
|---|---|---|---|
| `trigger.1` (PR-only, path-filtered) | Present | Present | Present |
| `job.1` (`code-style` job, ubuntu-latest) | Present | Present | Present |

**2/2 all three candidates.** Confirms the mechanism works at trivial scale;
this pipeline is too small to distinguish the prompts.

### `nextjs_build_and_test` (82 facts) — the real stress test

| Candidate | Present | Missing | False | Coverage |
|---|---|---|---|---|
| 0 (control) | 6 | 76 | 0 | 7.3% |
| 1 (structured) | 81 | 1 (shared limitation) | 0 | 98.8% (100% of facts actually in the input) |
| 2 (narrative) | 81 | 1 (shared limitation) | 0 | 98.8% (100% of facts actually in the input) |

By category:

| Category (count) | C0 Present | C1 Present | C2 Present |
|---|---|---|---|
| trigger (2) | 1 | 1 | 1 |
| concurrency (1) | 1 | 1 | 1 |
| environment_variable (2) | 0 | 2 | 2 |
| job (15) | 3 | 15 | 15 |
| dependency (62) | 1 | 62 | 62 |

**Zero hallucinations (False) in any candidate.** The control's low score is
entirely a Missing problem (facts never attempted, by prompt design — it asks
for "2-4 short paragraphs," not full coverage), not a False problem.

#### Reasons for every Missing/False fact

**Candidate 0 (control) — 76 Missing, grouped by cause:**

| Cause | Affected facts | Count |
|---|---|---|
| Job named in a summary sentence, but its specific `uses: build_reusable.yml` delegation is never individually attributed to it (only a blanket "Most of these jobs delegate to reusable workflows" over the whole list) | `job.4, job.6, job.8, job.10, job.11, job.13, job.22, job.23, job.30, job.33, job.34, job.37` | 12 |
| Dependency edge never individually named — either no dependency statement at all for that job, or only the vague "runs after nearly all other jobs have completed" for `tests-pass`'s 30 edges | `dependency.3–144` (61 of the 62 dependency facts; `dependency.1` is the one exception, Present via the `changes`-conditional phrasing) | 61 |
| Env var name mentioned in a list, but its value (`=20`/`=22`) is never stated | `environment_variable.1, environment_variable.2` | 2 |
| Fact absent from the input fact sheet (shared by all 3 candidates, see above) | `trigger.2` | 1 |

This is expected and by design — the control prompt explicitly asks for only
2-4 short paragraphs, not full coverage. It is not evidence the control is
"worse" at fact-preservation for the facts it *does* attempt (0 False,
same as the other two) — it simply attempts far fewer.

**Candidates 1 and 2 — 1 Missing each**, both `trigger.2`, both for the
shared reason above (not present in the fact sheet). No other Missing, no
False.

## Readability vs. the naive baseline

For reference, each pipeline's existing naive-baseline text (Tier 4 condition
3: raw YAML → generic "explain this" prompt, from
`evaluation/tier4_scoring/{stem}.scoring.md`, read-only, no new calls) is
pulled in for comparison:

- **`httpie_code_style` naive baseline** (`tier4_scoring/httpie_code_style.scoring.md`,
  Condition B per its answer key): a long, step-by-step markdown walkthrough
  with a `## In summary` recap — fluent and accurate for this tiny pipeline,
  but noticeably padded with "likely purpose" speculation (`**Likely purpose
  of make venv**: ... almost certainly responsible for...`) that the real
  fact sheet never states. Candidates 1/2 read tighter for the same
  information at roughly a third of the length.

- **`nextjs_build_and_test` naive baseline** (`tier4_scoring/nextjs_build_and_test.scoring.md`,
  Condition B): also long and well-organized (grouped into "Initial Setup,"
  "Build Jobs," "Linting," etc. — similar sectioning instinct to Candidate 2),
  but it is built on raw YAML, not the fact sheet, and it is **not bound by
  the "don't infer/speculate" rule** the fact-sheet-only candidates carry.
  It reads confidently but is full of unearned inference throughout —
  `"Purpose: Likely analyzes changes in a PR..."`, `"(likely a JavaScript
  framework like Next.js, given the job names...)"`, `"Purpose: Builds native
  (likely Rust/SWC) components"` — none of which are facts in the checklist
  or the fact sheet; they're the model guessing from raw YAML naming
  conventions. Candidates 1 and 2 achieve comparable or better organization
  and *higher* verifiable fact density without that speculation, because the
  rules explicitly forbid it and the fact sheet gives them no raw material to
  speculate from even if they tried.

Net: Candidates 1 and 2 read as *more* trustworthy than the naive baseline
(same ballpark of length and organizational ambition, zero invented "likely
purpose" narration) while scoring far better than the control on fact
coverage. Whether their length crosses into "too long to skim" for your
purposes is exactly the judgment call left to you below.

## Full candidate texts

See `evaluation/rewrite_experiment/outputs/`:

- `httpie_code_style.fact_sheet.txt`, `.candidate0.txt`, `.candidate1.txt`, `.candidate2.txt`
- `nextjs_build_and_test.fact_sheet.txt`, `.candidate0.txt`, `.candidate1.txt`, `.candidate2.txt`

(Full text also reproduced in the chat response accompanying this report.)

## Observations

1. **The architectural constraint holds at full-rewrite scale.** Restricting
   the LLM to the fact sheet (never raw YAML) does not force short output —
   Candidates 1/2 prove a full, well-organized rewrite of an 82-fact sheet is
   achievable with zero hallucination, using the same input the control
   prompt already had.
2. **The control prompt's low score is a prompt-design ceiling, not a
   capability ceiling.** It was never asked to cover everything; when asked
   to (Candidates 1/2), the same underlying model does so almost completely.
3. **Structured (1) vs. narrative (2) are statistically identical on fact
   coverage** (81/82 each, same single shared-limitation miss). The
   difference between them is purely readability/organization, which is your
   call, not an automated one.
4. **The one genuine gap (`trigger.2`) is upstream of the LLM layer entirely**
   — it's a property of what `generate_text()` puts in the fact sheet, not of
   any beautification prompt. Worth knowing if this experiment's finding
   motivates any real follow-up work, but out of scope for this branch.

---

## Addendum — Candidate 1 only, 2 more pipelines (`celery_python_package`, `scipy_linux`)

**Status: still validation only.** No changes to `llm/gemini_provider.py`'s
real `SYSTEM_PROMPT`, no merge, no PR — this branch stays unmerged regardless
of how these numbers turn out; that decision is explicitly out of scope for
this addendum. Only Candidate 1 (structured rewrite) was tested this time,
not 0 or 2 — the question here is whether Candidate 1's near-perfect
`nextjs_build_and_test` result generalizes to different pipeline shapes, not
a fresh three-way comparison.

### Pipeline selection

Chosen for diversity against the existing `httpie_code_style` (tiny, 2
facts) / `nextjs_build_and_test` (huge, 82 facts, 62 of them dependency
edges) pair:

- **`celery_python_package`** (20 facts) — mid-sized, a genuine
  reusable-workflow-calling pair (`Integration-tests`/`Smoke-tests`) gated on
  another job's `result`, not yet exercised by either existing pipeline.
- **`scipy_linux`** (35 facts) — chosen over `vscode_pr` specifically for
  the "heavy matrix/dependency" slot: `vscode_pr`'s checklist has **zero**
  dependency facts (all 18 of its jobs are independent — no `needs:` chains
  at all), while `scipy_linux` has 11 real dependency facts (a fan-out from
  one gating job) plus 2 matrix facts — the actual dependency/matrix stress
  this addendum was meant to add.

### Generation notes

Both calls used the exact same `CANDIDATE_1_PROMPT`, retry contract, and
timeout as the committed `generate_outputs.py` — no script changes, only a
scratch driver that imports `CANDIDATE_1_PROMPT`/`_call_with_one_retry`
unmodified and runs it against 2 more pipelines. `celery_python_package`
succeeded on the first attempt (12.4s); `scipy_linux` hit the same
`504 DEADLINE_EXCEEDED` pattern seen previously on `nextjs_build_and_test`'s
larger fact sheets, succeeded on retry (34.5s total, 2 attempts). Both final
outputs are genuine LLM generations, no fallback used. Fact sheets and raw
outputs are alongside the existing ones in
`evaluation/rewrite_experiment/outputs/`.

### Scoring method

Identical rubric to the main report: fact-by-fact Present/Missing/False
against each pipeline's existing pre-registered checklist
(`evaluation/tier4_checklists/*.checklist.yml`, read-only, unmodified), same
two conventions applied uniformly (compound facts need every component
stated; dependency facts need an individually-named edge, not a summary
sentence) — no length/polish credit.

### Results

#### `celery_python_package` (20 facts)

| Category (count) | Present | Missing | False |
|---|---|---|---|
| trigger (3) | 3 | 0 | 0 |
| job (4) | 4 | 0 | 0 |
| dependency (4) | 4 | 0 | 0 |
| step (2) | 2 | 0 | 0 |
| condition (2) | 2 | 0 | 0 |
| matrix (1) | 0 | 1 | 0 |
| secret (1) | 0 | 1 | 0 |
| linked_workflow (2) | 2 | 0 | 0 |
| permissions (1) | 1 | 0 | 0 |
| **Total (20)** | **18** | **2** | **0** |

**Coverage: 90% (18/20), zero hallucinations.**

Both Missing facts trace to the **deterministic fact sheet itself never
carrying the required detail down** — a shared limitation of
`generate_text()`'s rendering, not a Candidate-1-specific defect, same
category as the main report's `nextjs_build_and_test.trigger.2` finding:

- `matrix.1` ("python-version (6 values) x os (2 values), with 6 exclude
  entries pruning Windows combos") — the fact sheet's own line reads only
  `matrix: up to 12 combinations (python-version, os), 6 excluded`. It never
  breaks the 12 down into per-axis cardinalities, and never says "Windows"
  anywhere — that word appears nowhere in the fact sheet. Candidate 1
  correctly reports the aggregate (12 combinations, 6 excluded) but cannot
  state axis-level counts or the Windows detail without inventing
  information not in its input, which the prompt explicitly forbids.
- `secret.1` ("in a `with:` block, not `env:`") — the fact sheet's SECRETS
  REQUIRED section states the secret name and which job/step uses it, but
  never which YAML block (`with:` vs `env:`) it came from; `ir.schema.Secret`
  doesn't carry that distinction into the rendered text at all. Same
  shared-limitation shape.

#### `scipy_linux` (35 facts)

| Category (count) | Present | Missing | False |
|---|---|---|---|
| trigger (2) | 2 | 0 | 0 |
| job (12) | 12 | 0 | 0 |
| dependency (11) | 11 | 0 | 0 |
| step (2) | 2 | 0 | 0 |
| condition (1) | 1 | 0 | 0 |
| matrix (2) | 0 | 1 | 1 |
| linked_workflow (1) | 1 | 0 | 0 |
| permissions (1) | 1 | 0 | 0 |
| concurrency (1) | 1 | 0 | 0 |
| environment_variable (2) | 2 | 0 | 0 |
| **Total (35)** | **33** | **1** | **1** |

**Coverage: 94.3% (33/35) — the first False in this experiment across all
four pipelines tested.**

All 11 dependency facts are individually Present — Candidate 1 states, in
each job's own paragraph, "It runs after `get_commit_message` and only if
[condition]," for every one of the 11 dependent jobs by name. This is a
stronger dependency result than the main report's control ever achieved and
matches Candidates 1/2's `nextjs_build_and_test` performance, on a
fan-out-from-one-job topology rather than a many-to-many web.

**`matrix.1`** ("python-version (2 values) x maintenance-branch (1 value),
with 1 exclude entry") — Missing, same shared-limitation category as
`celery_python_package.matrix.1` above: the fact sheet states only the
aggregate ("up to 2 combinations ... 1 excluded"), never per-axis
cardinalities, for any job, anywhere in this pipeline's fact sheet.

**`matrix.2`** ("Job 'free-threaded' has a single-axis matrix: parallel with
2 values") — **False, not Missing, and the specific reason is worth stating
precisely.** The fact sheet's line for this job reads: `matrix: 2
combinations (parallel)`. Every other job's matrix line in this same fact
sheet uses the identical convention — the parenthetical names the axis
(`(python-version)`, `(python-version, maintenance-branch)`) — and
confirmed against the real YAML, `free-threaded`'s matrix is literally
`strategy.matrix.parallel: ["0", "1"]`: `parallel` is the axis *name*, not a
claim about execution behavior. Candidate 1 rewrote this as *"It uses a
build matrix with 2 combinations that run in parallel"* — reading the axis
label as an adjective describing how the combinations execute, rather than
as the axis's name. This is a real misreading, not a length/polish issue:
the model asserted something (concurrent execution) that is not stated
anywhere in its input and is not what the fact means. It's also a narrow,
specific failure mode — one axis-name string, on one job, out of 35 facts —
not evidence the prompt fabricates freely; every other fact in this same
35-fact pipeline, including 11 individually-named dependency edges and 12
job attributions, came through with zero error. Worth flagging clearly
rather than folding into the Missing count, since "stated something
incorrect" and "stated nothing" are different failure modes and this
report's whole point is not blurring that line for the sake of a cleaner
number.

### Combined numbers across all 4 pipelines tested (Candidate 1 only)

| Pipeline | Facts | Present | Missing | False | Coverage |
|---|---|---|---|---|---|
| `httpie_code_style` | 2 | 2 | 0 | 0 | 100% |
| `nextjs_build_and_test` | 82 | 81 | 1 | 0 | 98.8% |
| `celery_python_package` | 20 | 18 | 2 | 0 | 90% |
| `scipy_linux` | 35 | 33 | 1 | 1 | 94.3% |
| **Total** | **139** | **134** | **4** | **1** | **96.4%** |

**1 False in 139 scored facts across 4 pipelines of varying shape and size.**
Every Missing across all four pipelines traces to a fact genuinely absent
from the deterministic fact sheet itself (an architectural constraint of
`generate_text()`, not a prompt failure) — none is a case of Candidate 1
skipping something it could see. The one False is a real, specific,
narrow misreading of an axis-name label as a behavior claim, isolated to a
single fact on a single job — not a pattern repeated elsewhere in the same
output or in any of the other three pipelines.

### What this addendum adds to the main report's conclusions

1. **Candidate 1's near-perfect dependency handling generalizes** beyond
   `nextjs_build_and_test`'s many-to-many web to a fan-out-from-one-job
   topology (`scipy_linux`, 11/11) and a small reusable-workflow-gated pair
   (`celery_python_package`, 4/4) — not an artifact of one pipeline's shape.
2. **The "zero hallucination" finding from the main report does not hold at
   139 facts** — it holds at 138/139. The one exception is informative
   precisely because it's narrow and specific (a label-vs-behavior
   misreading), not because it's large or because it invalidates the
   broader pattern.
3. **Every Missing fact across all 4 pipelines is a fact-sheet-level gap,
   not a prompt-level one** — reinforcing the main report's Observation 4
   that the real ceiling on completeness is upstream of the beautification
   layer entirely.
