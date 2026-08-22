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
