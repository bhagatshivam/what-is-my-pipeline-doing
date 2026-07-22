> **Status: living build plan, not a finalised spec.** This document exists to keep Shivam and Claude Code aligned on what phase we're in, what "done" looks like for that phase, and what's deliberately deferred. Edit it freely as reality overtakes the plan — update the checklists, cross out what's wrong, add what's missing. It sits alongside `PROJECT_PLAN.md` (architecture reference), `WEEKLY_PLAN.md` (calendar), and `EVALUATION_PLAN.md` (evaluation detail); this document is the one meant to be open while actually writing code.

# BUILD_PLAN.md — CI Pipeline Documentation Tool

**Student:** Shivam Balasaheb Bhagat · **Supervisor:** Professor Suzanne Embury · MSc Computer Science, University of Manchester

---

## 0. How to use this document with Claude Code

- Each phase below has a **Goal**, a **Task checklist**, an **Explicitly deferred** list, and a **Definition of done**.
- Work through phases in order. Don't start a phase's "Should-complete" items until that phase's "Must-complete" items are checked off.
- When starting a Claude Code session for a specific phase, point it at: this file, `PROJECT_PLAN.md` (for the *why*), and the relevant section of `EVALUATION_PLAN.md` once you reach Phase 7.
- When a phase's scope changes mid-build, edit the checklist in place rather than leaving it stale — the point of this doc is that it stays true, not that it stays original.

---

## 1. Prototype-first scoping (read this before anything else)

The single most important scoping decision: **build both Tool 1 and Tool 2 end-to-end for GitHub Actions only, first.** Do not start any other platform's parser until Tool 1 and Tool 2 both work fully on GitHub Actions, are polished with the LLM layer, and have been through at least Tier 1–2 evaluation.

Rationale: a working, evaluated, GitHub-Actions-only pair of tools is a complete, defensible dissertation on its own — the platform-agnostic IR is what makes a *second* platform cheap to add later, and that "cheap to add" claim is far more convincing in the report if you've actually got a fully-finished vertical slice to point to, rather than three half-finished parsers. Expansion to other platforms is explicitly its own later phase (Phase 9) and is scoped as extension work, not core work.

---

## 2. Repository structure

```
what-is-my-pipeline-doing/
├── parsers/
│   ├── base.py              # abstract parser interface
│   └── github_actions.py    # first and only parser until Phase 9
├── ir/
│   ├── schema.py            # IR dataclasses / TypedDicts
│   └── validate.py          # sanity checks on a built IR object
├── generators/
│   ├── text_generator.py    # Layer 3a — IR -> structured plain text
│   └── mermaid_generator.py # Layer 3b — IR -> Mermaid syntax
├── llm/
│   ├── base.py               # swappable LLM interface
│   ├── gemini_provider.py    # Layer 4, cloud mode
│   └── ollama_provider.py    # Layer 4, local mode (stub until future work)
├── tool1/
│   └── single_pipeline.py   # orchestrates parser -> IR -> generators -> LLM for one file
├── tool2/
│   └── multi_pipeline.py    # orchestrates the above across a repo's workflow folder
├── evaluation/
│   ├── coverage_check.py
│   ├── diagram_diff.py
│   ├── variance_check.py
│   ├── readability.py
│   └── error_injection/
├── tests/
│   └── fixtures/            # sample real-world GitHub Actions YAML files
├── docs/                    # generated output lands here during dev
└── cli.py                   # entry point
```

Create this skeleton in Phase 1 even if most files are empty stubs — it keeps every later phase's task list unambiguous about where code goes.

---

## 3. Phase-by-phase build plan

### Phase 1 — Environment & repo setup

**Goal:** a working Python project skeleton, dependency management, and a small set of real GitHub Actions YAML files to develop against.

**Tasks**
- [x] Initialise GitHub repo with the structure in Section 2
- [x] Set up virtual environment, `requirements.txt` / `pyproject.toml` (PyYAML at minimum)
- [x] Pull 8–10 real GitHub Actions workflow files from open-source repos into `tests/fixtures/`, ranging from trivial (lint-only) to complex (matrix builds, reusable workflows, multi-job with `needs`)
- [x] Write `parsers/base.py` — an abstract interface (`parse(file_path) -> IR`) that every future platform parser must implement, even though only one implementation exists yet

**Explicitly deferred:** any parsing logic, IR schema detail, LLM setup.

**Definition of done:** `pip install -r requirements.txt && python cli.py --help` runs cleanly in a fresh clone; fixtures are committed; base parser interface exists and is documented with a docstring explaining the contract.

---

### Phase 2 — Intermediate Representation (IR)

**Goal:** lock the platform-agnostic data structure everything else depends on. This is the highest-leverage phase to get right early — get Suzanne's sign-off before Phase 3 depends heavily on it.

**Tasks**
- [x] Implement the IR as Python dataclasses/TypedDicts matching the schema already drafted in `PROJECT_PLAN.md` (`pipeline`, `jobs`, `steps`, `triggers`, `secrets`, `environment_variables`)
- [x] Write `ir/validate.py`: a function that checks a built IR object is well-formed (no job depends on a job that doesn't exist, no empty required fields, etc.) — this becomes useful later for the Tier 1 evaluation checks too
- [x] Write 2–3 IR objects by hand (not via a parser) representing simple/medium/complex pipelines, to use as ground truth in tests before the parser exists
- [ ] Share the field-naming table with Suzanne for sign-off

**Explicitly deferred:** GitLab/Jenkins/CircleCI field mappings — the table in `PROJECT_PLAN.md` can stay aspirational for now; only the GitHub Actions → IR mapping needs to be solid.

**Definition of done:** IR schema is implemented, documented, has at least one validation test per field, and Suzanne has confirmed the field names in writing (email/meeting note is fine).

---

### Phase 3 — GitHub Actions parser

**Goal:** raw YAML in, valid IR out, for real-world files — this is Layer 1 for the one platform in scope.

**Tasks**
- [x] Implement `parsers/github_actions.py` against the IR schema from Phase 2
- Handle incrementally, in this order (simplest first):
  - [x] `on` triggers (push/PR/schedule/manual)
  - [x] `jobs` + `runs-on`
  - [x] `steps` (both `run:` and `uses:`)
  - [x] `needs` (dependencies)
  - [x] `env`/`secrets` references
  - [x] `if` conditions
  - [x] `strategy.matrix`
  - [x] reusable workflows (`uses: ./.github/workflows/...` or external)
- [x] Test against all fixtures from Phase 1 as each feature is added — don't wait until the end
- [x] Document parser limitations as you hit them (dynamic expressions like `${{ matrix.python-version }}`, unusual anchor/alias usage) — this becomes report material later, not just a to-do list (see `LIMITATIONS.md`, updated alongside every merged pass)

**Explicitly deferred:** any other CI platform. Composite actions can be partially deferred if they prove complex — note it and move on rather than blocking the phase.

**Definition of done:** all 8–10 fixture files parse into valid IR without raising, `ir/validate.py` passes on all of them, and there's a written note of known limitations.

---

### Phase 4 — Generators (Layer 3, no LLM) — Tool 1 non-LLM milestone

**Goal:** IR → human-readable structured text, and IR → Mermaid diagram, both pure Python, no LLM. This is a real milestone: **Tool 1 technically exists** end-to-end after this phase, even before the LLM polish pass.

**Tasks**
- [x] `generators/text_generator.py`: IR → structured plain-text summary (triggers, jobs in order, secrets required — matching the example format in `PROJECT_PLAN.md`)
- [x] `generators/mermaid_generator.py`: IR job dependency graph → Mermaid `flowchart` syntax
- [x] Wire both into `tool1/single_pipeline.py`: `YAML file → parser → IR → text output + Mermaid output`, written to a `.md` file in `docs/`
- [x] `tool1/single_pipeline.py`: add a `--check` flag — generate the
  doc in-memory and diff it against whatever `.md` file is already
  committed for that pipeline, exiting non-zero on mismatch. Inspired
  by `terraform-docs` (industry-standard Terraform documentation
  generator), which runs the same way in CI to catch documentation
  that has drifted out of sync with the underlying config. This also
  directly implements the "documentation drift" evaluation method
  already listed in Phase 7 / EVALUATION_PLAN.md — no separate script
  needed later, Phase 7 can reuse this flag as-is.
- [x] Close a spec gap found during a cross-verification review of all 10
  fixtures' generated output against source YAML: `PROJECT_PLAN.md`'s
  Tool 1 deliverable list normatively includes "What each step in each
  job does", but `text_generator.py` surfaced only an aggregate step
  count. Added a capped per-job step-name listing; see `LIMITATIONS.md`'s
  "## Text generator" section, "No step-level detail is surfaced"
  bullet, for the full resolution and the cap's justification. The same
  review also found and closed three smaller output-clarity gaps (secret
  `scope_ref` decoding, reusable-workflow-calling jobs no longer reading
  as "0 steps", oversized Mermaid nodes from long job conditions) — see
  `LIMITATIONS.md` for each.
- [x] Run against all fixtures, visually check the Mermaid renders correctly in a Markdown viewer (GitHub itself renders Mermaid — good sanity check)
- [ ] Show Suzanne this non-LLM output — good moment for her to sanity-check the whole approach before more layers sit on top. A supervision meeting is scheduled to cover this; this box stays unchecked until it happens.

**Explicitly deferred:** LLM beautification, Tool 2, animation/step-through feature.

**Definition of done:** running `python cli.py tool1 <path/to/workflow.yml>` produces a Markdown file with an accurate structured summary and a correctly-rendering Mermaid diagram, for every fixture file.

---

### Phase 4.5 — Tool 1 Hardening and Evaluation Foundations

**Goal:** strengthen Tool 1's correctness boundary and establish independent, practical evaluation foundations before adding the constrained LLM layer, without expanding the dissertation scope or delaying the software/evaluation freeze beyond 10 August 2026.

**Tasks (P0 — required before Phase 5)**
- [x] Integrate IR validation into Tool 1's user-facing generation path: `YAML → parser → IR validation → generators`. Validation lives at Tool 1's shared `_build_documentation()` boundary, so normal generation and `--check` both pass through it while `generate_documentation()` and both generators remain unchanged.
  - [x] Stop generation when any error-level validation finding exists; do not write partial or plausible-looking documentation after validation fails
  - [x] Report actionable validation findings, with warnings clearly distinguishable from errors
  - [x] Define and document a non-zero CLI exit code for invalid IR (`3`, preserving `1` for failed drift checks and `2` for parse/input/operational failures)
  - [x] Add focused integration tests for important failure paths, including dangling dependencies, dependency cycles, non-mapping `jobs:`, and non-mapping individual job bodies
- [ ] Correct terminology and documentation claims throughout project-facing documentation
  - [ ] Replace claims that extracted facts are "verified" with accurate wording such as "deterministically extracted and structurally validated facts"
  - [ ] State that golden-file tests detect regression against accepted output; they do not independently prove semantic correctness
  - [ ] Clearly distinguish implemented, evaluated, and future functionality
- [ ] Expand linting and CI across the complete maintained Python codebase, including `generators/`, `tool1/`, `tool2/`, `llm/`, `evaluation/`, and `cli.py` where those paths exist, rather than only `ir/`, `parsers/`, and `tests/`
  - [ ] Add or record proportionate checks for validation-failure paths and evaluation utilities, without introducing an expensive or elaborate CI design
- [x] Add a limited set of security-relevant typed fields if achievable without delaying Phase 5
  - [x] Prioritise workflow/job permissions and deployment environment; these are currently preserved in `raw_extras`, but are not typed or surfaced
  - [x] Add concurrency only if straightforward; it is currently preserved in `raw_extras` — straightforward: every real occurrence at both levels is a mapping, so promoted alongside permissions/deployment_environment rather than deferred
  - [x] Continue preserving unsupported fields in `raw_extras`
  - [x] Keep job-output modelling, artifact-flow analysis, and extensive security analysis out of current scope unless already substantially implemented
- [ ] Prepare independent evaluation foundations
  - [ ] Define and validate a small machine-readable fact-manifest schema, with manifests manually derived from workflow YAML and never generated by the project parser
  - [ ] Keep development fixtures separate from held-out evaluation workflows; begin with 3–4 held-out workflows and expand towards 6 only if time permits
  - [ ] Record repository/source information and commit SHA where applicable
  - [ ] Plan automated YAML-to-IR fact scoring and documentation factual-coverage scoring
  - [ ] Plan simple Mermaid job-node and dependency-edge comparison
  - [ ] Plan a small robustness/mutation set
  - [ ] Treat unsupported-claim or hallucination scoring as post-hoc evaluation, not as a runtime fact-ID or provenance system
- [ ] Update project-facing documentation
  - [ ] Bring `README.md` into line with the actual implemented state and correct stale plans or claims
  - [ ] Remove evaluator-recruitment assumptions; evaluation is self-conducted and mostly automated
  - [ ] Clearly document supported features, known limitations, and validation behaviour
  - [ ] Keep this practical; extensive visual polish is not part of the hardening phase

**Explicitly deferred:** fact-ID preservation for LLM output; per-sentence source provenance; a complex runtime hallucination detector; rich Mermaid redesign or multiple diagram views; multiple LLM providers; a GUI or GitHub application; Jenkins, GitLab CI, or other CI-platform support; full external reusable-workflow resolution; a large performance benchmark; and a production-grade CLI redesign unless existing functionality requires it. Phase 5 implementation is not part of this phase-planning update and must not begin until this plan is approved.

**Definition of done:** Tool 1 validates its IR before generation; error-level findings prevent all output generation and focused failure-path tests pass; terminology and overstated claims are corrected; CI/linting covers the maintained project code; the reduced evaluation design and independent manifest approach are documented; supported security fields are implemented and tested or explicitly deferred; `README.md`, this build plan, and relevant planning documents no longer contradict the current methodology; and Phase 5 can begin without relying on unvalidated IR or circular evaluation ground truth.

---

### Phase 5 — LLM beautification layer — Tool 1 complete (prototype)

**Goal:** natural, readable prose on top of the Phase 4 output, without the LLM ever seeing raw YAML.

**Tasks**
- [ ] `llm/base.py`: minimal interface (`beautify(structured_text, ir_context) -> prose`) that any provider implements
- [ ] `llm/gemini_provider.py`: Gemini API integration (Google AI Studio free tier)
- [ ] Prompt engineering pass: the prompt must make clear the LLM is rewriting deterministically extracted and structurally validated facts into prose, not analysing or inferring new ones
- [ ] Keep unsupported-claim/hallucination scoring in the post-hoc evaluation path defined in Phase 4.5 and Phase 7; do not build a runtime fact-ID, provenance, or complex hallucination-detection protocol
- [ ] Test on 5+ pipelines across the complexity range in fixtures
- [ ] `llm/ollama_provider.py`: stub only — interface implemented, not filled in (local LLM stays documented future work per existing scope decision, unless time allows later)

**Explicitly deferred:** full local-LLM mode, multi-provider switching UI, Tool 2.

**Definition of done:** Tool 1 fully complete — `YAML → validated IR → polished Markdown doc with embedded Mermaid diagram` — for every fixture, with post-hoc unsupported-claim scoring recorded during evaluation rather than presented as a runtime correctness guarantee.

---

### Phase 6 — Tool 2: multi-pipeline documentation (GitHub Actions prototype)

**Goal:** the same quality bar as Tool 1, but across a whole repository's `.github/workflows/` folder, producing one unified picture.

**Tasks**
- [ ] `tool2/multi_pipeline.py`: discover all workflow files in a folder, parse each into IR, build a combined view
- [ ] Cross-pipeline relationships: which pipelines fire on which events, any explicit dependencies between workflows (e.g. one workflow triggering another via `workflow_run`)
- [ ] Unified Mermaid diagram covering all pipelines' triggers and jobs
- [ ] Support injecting the generated unified doc between
  `<!-- ci-docs:start -->` / `<!-- ci-docs:end -->` marker comments in
  an existing file (e.g. an existing README.md), instead of only
  writing a fresh standalone file. Inspired by `terraform-docs`, which
  uses the same marker-based injection so it can update a doc section
  without overwriting the rest of the file.
- [ ] Reuse the Phase 4/5 generators and LLM layer — Tool 2 should not need its own separate text/Mermaid/LLM code, just a layer that merges multiple IR objects before handing off to the same generators
- [ ] Test against 2–3 real multi-workflow repos (not just single-file fixtures — pull whole `.github/workflows/` folders)

**Explicitly deferred:** any non-GitHub-Actions repo, animation feature.

**Definition of done:** running `python cli.py tool2 <path/to/repo>` produces one unified Markdown doc + unified Mermaid diagram correctly describing a multi-workflow repository, for at least 2–3 real test repos.

---

### Phase 7 — Evaluation

**Goal:** run the evaluation methods from `EVALUATION_PLAN.md` against the now-complete GitHub Actions prototype of Tool 1 and Tool 2. Full method detail lives in that document — this phase just sequences it. Per Supervisor guidance, recruiting developer evaluators is off the table for this project — every task below is self-conducted, zero participants.

**Tasks (Tier 1 & 2 — start as soon as Phase 3/4 land, don't wait for Phase 5/6)**
- [ ] Golden-file regression testing: commit expected `.md` output for all 10 fixtures, regenerate + diff in CI on every PR (reuses the `--check` flag already implemented in Phase 4)
- [ ] Coverage check (every IR field appears in output)
- [ ] Diagram-structure check (Mermaid graph matches IR dependency graph exactly)
- [ ] Determinism/variance check (LLM layer only, once Phase 5 lands — golden-file testing above already covers the non-LLM layers)
- [ ] Readability metrics (Flesch-Kincaid or similar)
- [ ] Error injection (broken dependency, malformed `if`, undefined secret — does the tool flag it or silently hallucinate?)

**Tasks (Tier 3 — moderate setup)**
- [ ] Correctness check: trigger real pipelines on 4–5 real repos, compare GitHub's actual job/status output to the tool's documentation
- [ ] Natural-pairs comparison: find repos with existing human-written CI docs (README/CONTRIBUTING/wiki), compare tool output directly against them

**Tasks (Tier 4 — self-conducted, zero recruitment; must happen in this order)**
- [ ] Pre-register the fact checklist for each evaluation pipeline — every objectively checkable fact in its YAML (triggers, `needs:` edges, required secrets, gating conditions) — and commit it to the repo *before* generating any of the three conditions' outputs. This is a distinct, ordered prerequisite, not just documentation: the protocol is invalid if the checklist is written after seeing what each condition got right or wrong.
- [ ] Pre-registered fact-checklist protocol (Tool 1): generate the three conditions (non-LLM structured text / full LLM-polished output / naive raw-YAML-to-LLM baseline), score each fact-by-fact in randomised order against the pre-registered checklist — facts correct, facts missing, hallucinated facts
- [ ] Answerability audit (Tool 2): write ground-truth questions derived from the YAML, check whether each is answerable from the unified doc alone, report the answerability rate

**Explicitly deferred to stretch (Tier 5):** real PR submission to open-source repos (attempt as early as output quality allows — maintainer response time isn't controllable, and this is now the only external human signal available with recruitment off the table), generation-time/cost logging (log automatically now, write up only if there's room later).

**Definition of done:** Tiers 1–4 complete with results recorded — Tier 4's fact-checklist and answerability-audit results collected and analysed under the pre-registered protocol (checklist commit predates output generation). Tier 5 (real-PR submission) attempted and reported honestly regardless of outcome. See `EVALUATION_PLAN.md` for full method detail and rubric, including the "Threats to validity — single-author evaluation" section this phase's results should be read alongside.

---

### Phase 8 — Refinement pass on Tool 1 + Tool 2

**Goal:** fix what evaluation revealed, before touching scope expansion or the report.

**Tasks**
- [ ] Triage evaluation findings: parser edge cases, LLM inconsistencies, low-scoring comprehension tasks
- [ ] Fix highest-impact issues only — this is not a rewrite phase
- [ ] Freeze the codebase for reporting purposes (tag a release on GitHub) once stable
- [ ] Assemble report assets: architecture diagram, example outputs, evaluation charts

**Definition of done:** codebase tagged and stable, known remaining issues documented (these become "limitations" material in the report, not silent gaps).

---

### Phase 9 — Expand beyond GitHub Actions (extension phase, explicitly secondary)

**Goal:** prove the platform-agnostic claim by adding a second platform, now that Tool 1/2 are solid on GitHub Actions. Do not start this phase until every item in Section 4's checklist is checked off. If time runs out before Section 4 is complete, Phase 9 is skipped entirely and the report frames multi-platform support as future work — a fully working, evaluated GitHub-Actions-only tool is the shippable deliverable, not a partially-working multi-platform one.

**Tasks**
- [ ] Pick one additional platform (GitLab CI is the structurally straightforward choice per existing notes; CircleCI is a similar shape; Jenkins is the outlier — Groovy, not YAML — and should be the last choice if attempted at all)
- [ ] Write `parsers/gitlab_ci.py` (or equivalent) implementing the same `base.py` interface from Phase 1
- [ ] Map its fields onto the *existing* IR schema — if new IR fields are genuinely required, that's a signal worth flagging to Suzanne rather than silently patching the schema
- [ ] Re-run Tool 1 and Tool 2 against a handful of real repos using the new platform
- [ ] No new generator or LLM code should be required at all — if it is, that's worth noting as a gap in the "platform-agnostic" design claim

**Definition of done:** at least one additional platform's pipelines produce correct documentation using the same generators and LLM layer, unmodified. Even a partial implementation here is legitimate to write up honestly as "attempted, here's how far it got" — this phase is explicitly not load-bearing for the dissertation grade.

---

### Phase 10 — Report & video

Not a coding phase — see `WEEKLY_PLAN.md`'s day-by-day breakdown for this (Introductory Material → Methodology → Evaluation/Reflection → Conclusion → Abstract → Format pass → Video → final review), and the rubric weightings in `MSc_Report_and_Video_Rubric_12418018.pdf`. Keep this `BUILD_PLAN.md` and its final state as a primary source when writing the Methodology and Project Achievement sections — the phase history is itself evidence of process.

---

## 4. Definition of "prototype done" (top-level)

Before considering the GitHub-Actions-only prototype complete and moving attention to Phase 9 or report-writing:

- [ ] Tool 1: any single real-world GitHub Actions workflow file produces an accurate, LLM-polished Markdown doc with a correct Mermaid diagram
- [ ] Tool 2: any real-world repo's full `.github/workflows/` folder produces one accurate unified doc + diagram
- [ ] Post-hoc unsupported-claim scoring is complete for the agreed evaluation set
- [ ] Tier 1 & 2 evaluation checks are automated and passing
- [ ] At least Tier 3 evaluation has been run once against real repos

---

## 5. Tech stack reference

| Component | Technology |
|---|---|
| Language | Python |
| YAML parsing | PyYAML |
| Diagram generation | Pure Python string building → Mermaid syntax |
| Primary LLM | Gemini API (Google AI Studio free tier) |
| Optional local LLM (future work) | Ollama (Llama 3.1 8B or Mistral 7B) |
| Output format | Markdown (.md) with embedded Mermaid |
| IDE / assistants | VS Code, GitHub Copilot Pro, Claude Code, Claude Pro |
| Version control | GitHub (open-sourced on completion, Suzanne credited as supervisor) |

---

## 6. Open decisions / pending sign-off

Carried over from `PROJECT_PLAN.md` — resolve before they block a phase above:

- [ ] IR field-naming table — final sign-off from Suzanne (blocks nothing in Phase 1, but should land before Phase 3 goes deep)
- [ ] How to handle dynamic YAML values (`${{ matrix.python-version }}` etc.) in documentation output
- [ ] Open-source licence + IP formal confirmation
- [ ] Confirm with Suzanne that zero-recruitment, self-conducted evaluation (Phase 7 / `EVALUATION_PLAN.md` Tier 4) requires no ethics paperwork — very likely moot, but to be confirmed rather than assumed
- [ ] Whether a partial second-platform implementation (Phase 9) is expected to count toward the "platform-agnostic" claim, or whether the architecture argument alone is sufficient
- [x] ~~**Known gap, small contained follow-up, not a redesign:** `GitHubActionsParser.parse()`'s final `Pipeline(...)` construction never passes `raw_extras=`, so `Pipeline.raw_extras` is unconditionally empty on every parse — no workflow-level YAML concept (`permissions:`, `concurrency:`, `defaults:`, etc.) can currently be preserved regardless of the schema's `raw_extras` design intent.~~ **Fixed 2026-07-15**, before Phase 5 as planned: `parse()` now passes `raw_extras=_parse_pipeline_raw_extras(data)`, and `_parse_jobs` captures job-level `permissions:`/`outputs:`/`concurrency:`/deployment `environment:` (as `deployment_environment`, distinct from `Job.environment`). See `LIMITATIONS.md`'s "Consciously unmodeled concepts — verified preservation status" section for the per-concept resolution notes and `tests/test_github_actions_raw_extras.py` for coverage. Job-level `defaults:` remains unhandled — no fixture exercises it, out of this fix's scope.

---

## 7. Change log

- *[Add a dated line here each time this document is materially edited, so it's easy to see how the plan actually evolved — useful for the report's process narrative too.]*
- 2026-07-06: Phase 1 skeleton created, IR (schema.py/validate.py) integrated as ir/ package, Phase 2 ground-truth fixtures added.
- 2026-07-09: Phase 3 parser progressed through 8 merged PRs (#3–#10) — `on:` triggers, `jobs:`/`runs-on`, `steps:`, `needs:` dependencies, `env:`/secret references/`continue-on-error:`, `if:` conditions, and `strategy.matrix` are all implemented and tested against every fixture; only reusable workflows remain before Phase 3 is complete. `LIMITATIONS.md` has been updated alongside every pass and now serves as the living limitations log.
- 2026-07-09: Added two additive tasks after researching `terraform-docs` (industry-standard Terraform documentation generator) as a prior-art reference: a Phase 4 `--check` drift-detection flag for `tool1/single_pipeline.py`, and Phase 6 marker-comment (`<!-- ci-docs:start/end -->`) injection support for Tool 2's unified doc.
- 2026-07-09: Phase 3 is now fully complete — PR #11 merged reusable-workflow relationships (`uses:`/`workflow_run` → `Pipeline.linked_workflows`), the last outstanding sub-item. All Phase 3 checklist boxes are checked off.
- 2026-07-14: Phase 4's first slice merged (PR #12) — `generators/text_generator.py`'s `generate_text()`, a structured plain-text summary generator with topological job ordering. Phase 4's second slice merged (PR #13) — `generators/mermaid_generator.py`'s `generate_mermaid()`, IR job graph → Mermaid `flowchart` syntax — sharing its topological-order/matrix-summary/condition-phrase logic with `text_generator.py` via a new `generators/common.py`. Both checklist items are checked off; remaining Phase 4 tasks (wiring both generators into `tool1/single_pipeline.py`, the `--check` drift flag) are still open.
- 2026-07-14: `tool1/single_pipeline.py` implemented — `generate_documentation()` combines `generate_text()`/`generate_mermaid()` output verbatim into one Markdown file, `document_pipeline()` writes it to `docs/`, `check_pipeline()` does the `--check` drift comparison (exact string equality, `difflib` unified diff on mismatch). `cli.py`'s `tool1` subcommand is wired up with the new `--check` flag. **Tool 1 technically exists end-to-end** (`python cli.py tool1 <path>` produces a Markdown doc with an embedded Mermaid diagram for every fixture) — the Phase 4 "wire both into `tool1/single_pipeline.py`" and "`--check` flag" tasks are checked off. `generators/text_generator.py`/`generators/mermaid_generator.py` were not modified — treated as a fixed contract. Still open before Phase 4 is fully done: visually eyeballing the Mermaid rendering in a Markdown viewer and Suzanne's non-LLM-output sanity check, both inherently manual/social steps.
- 2026-07-14: Evaluation strategy changed to entirely self-conducted, zero participant recruitment (confirmed Supervisor guidance: recruiting developers is off the table for this project). `EVALUATION_PLAN.md` rewritten accordingly — golden-file regression testing added to Tier 1 (citing `terraform-docs`/HashiCorp's `terraform-equivalence-testing` precedent), Tier 4's recruited blind three-way comparison and task-based comprehension test replaced with a pre-registered fact-checklist protocol and an answerability audit respectively (both self-conducted, objective, fact-level scoring instead of subjective ratings), Tier 5 (think-aloud sessions) removed with no self-conducted equivalent, and a new "Threats to validity — single-author evaluation" section added covering the recruited study as explicit future work rather than silently dropped. Phase 7 above re-sequenced to match: "Recruit 6–8 evaluators" removed, golden-file testing added to the Tier 1/2 task group, Tier 4 tasks replaced with checklist pre-registration (called out as an ordered prerequisite) plus the two new methods, and Definition of Done rewritten. Section 6's stale "ethics approval for Tier 4 recruitment" line reworded to match. This removes Phase 7's only external lead-time dependency — the Week 5 evaluator-recruitment scheduling constraint no longer drives its start date, since every method is now self-conducted and can start as soon as the relevant tool component is ready.
- 2026-07-15: Verification pass on 6 GH Actions concepts not modeled in the IR schema (`permissions:`, `Job.outputs`, `concurrency:`, deployment `environment:`, trigger `types:` filter, `defaults:`) found that 5 of the 6 are genuinely silently dropped, not preserved in `raw_extras` as `parsers/base.py`'s contract requires — only the trigger `types:` filter is actually preserved (via `Trigger.raw`, already tested). Root cause: `GitHubActionsParser.parse()` never populates `Pipeline.raw_extras` at all. Full findings, fixture citations, and occurrence counts in `LIMITATIONS.md`'s new "Consciously unmodeled concepts — verified preservation status" section; the gap itself is now tracked in Section 6 above as a small, contained follow-up (wiring up the existing `raw_extras` field, not a redesign) worth fixing before Phase 5. No parser or schema change made this pass — reported for discussion, not fixed inline, per instruction.
- 2026-07-15: The `Pipeline.raw_extras` gap tracked above is now fixed. `GitHubActionsParser.parse()` passes `raw_extras=_parse_pipeline_raw_extras(data)` (workflow-level `permissions:`/`concurrency:`/`defaults:`), and `_parse_jobs` gained job-level `permissions:`/`outputs:`/`concurrency:`/deployment `environment:` (stored as `deployment_environment` — deliberately distinct from the existing `Job.environment` env-vars field, so the two can never be confused). Same presence-checked, verbatim-preservation pattern `_parse_jobs` already used for `display_name`/matrix-extras/etc. New `tests/test_github_actions_raw_extras.py` (12 tests) covers every fixed concept against the real fixtures the earlier audit identified, including an explicit non-collision check between `Job.environment` and `deployment_environment` on `rust_ci.yml`'s `job`. Confirmed via `scripts/update_golden_files.py` that `tests/golden/` is unaffected — neither generator reads `raw_extras`. Section 6's tracked line and `LIMITATIONS.md`'s findings both updated with "Resolved" notes, keeping the original audit prose intact as history rather than deleting it. Full suite: 401 passed (389 baseline + 12 new), 10 deselected.
- 2026-07-16: A cross-verification review of all 10 fixtures' generated output against source YAML found and closed 4 gaps, 3 in `generators/text_generator.py` and 1 in `generators/mermaid_generator.py` (the two generator files are otherwise treated as a fixed contract elsewhere in this project, but these were direct fixes to that contract, not additions on top of it). (1) **Step-level detail** — `PROJECT_PLAN.md`'s Tool 1 deliverable list normatively includes "What each step in each job does"; the prior aggregate-count-only behavior was closed by adding a per-job step-name listing, capped at 10 with an overflow line (`_step_lines`/`_STEP_LIST_CAP`) — the cap chosen because 53 of 58 real jobs across all fixtures have 10 or fewer steps. (2) **Mermaid condition truncation** — `pytorch_lint.yml`'s `lintrunner-clang`/`lintrunner-pyrefly` jobs' ~12-line block-scalar conditions were producing enormous diagram nodes; `_condition_annotation` now truncates a diagram-only annotation past 80 chars (or at the first line, if multiline) — chosen because it's the natural cut point between the 16 normal real conditions (≤75 chars) and the 3 oversized ones. `text_generator.generate_text()` is untouched and still renders the full expression verbatim, so this stays lossy only at the single-annotation level, not the document level. (3) **Secret `scope_ref` decoding** — `rust_ci.yml` was showing the parser's internal `job.26` convention verbatim; `_secret_line` now decodes STEP-scope refs into the real step name via a job-name lookup, while leaving PIPELINE/JOB-scope refs (which have no step index) unchanged. (4) **Reusable-workflow-calling jobs** — `eslint_ci.yml`'s `test_package_manager` read as "0 steps", which is technically true but misleading; the job line now reads "delegates to reusable workflow `<target>`", sourced from `Job.raw_extras["uses"]` (a deliberate, narrow exception to `text_generator`'s "raw_extras never read" rule — `Pipeline.linked_workflows` was considered but rejected since its dedup loses per-job attribution). All 4 changes, their justifications, and their real-fixture citations are documented in `LIMITATIONS.md`'s "## Text generator"/"## Mermaid generator" sections as "Resolved (2026-07-16)" notes appended to the original limitation prose (kept as history, not rewritten). New tests added for each gap against the specific real fixtures named above; `tests/golden/*.md` regenerated for all 10 fixtures and every diff reviewed by hand — each change traced to exactly one of the 4 gaps, nothing else moved. Full suite: 411 passed, 10 deselected; `ruff check` clean.
- 2026-07-21: Phase 4 is now functionally complete pending only Suzanne's sanity-check of the non-LLM output. The generator-gaps fix above is merged, so its checklist line is checked off; the remaining "run against all fixtures, visually check the Mermaid renders correctly" task is also checked off, done against the regenerated (post-gap-fix) output on the throwaway `docs/phase4-visual-review` branch (recreated from current `main` and re-pushed after the gap fixes landed, since the previous copy predated them). Only "Show Suzanne this non-LLM output" remains unchecked — a supervision meeting is scheduled to cover it, noted inline on that checklist item. Once the visual check is confirmed satisfactory, the `docs/phase4-visual-review` branch can be deleted; it was always a throwaway review artifact, never merged into `main`.
- 2026-07-21: Added Phase 4.5 — Tool 1 Hardening and Evaluation Foundations — as the required gate before Phase 5. It records IR-validation integration, terminology corrections, proportionate CI/lint expansion, limited security-field decisions, independent fact manifests and held-out evaluation workflows, and project-documentation alignment, together with explicit scope exclusions and the 10 August software/evaluation freeze. Phase 5 and the top-level prototype checklist were also corrected so unsupported-claim/hallucination scoring is post-hoc evaluation rather than a runtime fact-ID or provenance guarantee. No implementation work was started.
- 2026-07-21: Completed Phase 4.5's Tool 1 IR-validation integration. Normal generation and `--check` now share a parser → validation → generators boundary; warnings remain non-blocking and distinct on `stderr`, while error-level findings raise a typed `IRValidationError`, block both generators, preserve existing output, and return CLI exit code 3. Parseable non-mapping `jobs:` values and individual job bodies are preserved in `raw_extras` and rejected actionably; top-level/parse/input failures retain exit code 2. Focused verification: 37 passed, 10 deselected; Ruff clean. The full Windows non-slow run reached 415 passed and 10 deselected, with 11 pre-existing environment-sensitive failures (10 POSIX-vs-Windows golden source paths and 1 fixture text-decoding mismatch), none in the changed validation paths.
- 2026-07-21: Found and closed a test-coverage gap in the IR-validation integration above: an empty/comment-only YAML file (`None` root) was already being rejected at exit code 2 via the same non-mapping-root check in `_load_workflow_yaml()`, an unintentional side effect of `a7ecac9` rather than a designed feature, but had no test exercising it; added as a third case to `test_cli_tool1_top_level_or_yaml_parse_failure_stays_exit_code_2` and documented in `LIMITATIONS.md`.
- 2026-07-22: Phase 4.5 Item 2 — corrected terminology overclaims ("verified"/"Python-verified" implying proof of semantic correctness) in `PROJECT_PLAN.md`, `README.md`, and `generators/text_generator.py`'s docstring, replacing them with "deterministically extracted and structurally validated"; rewrote `README.md`'s stale pre-build placeholder status into an accurate current-state section (Tool 1 implemented end-to-end, CLI usage and exit codes, Tool 2/LLM layer not yet built, pointer to `LIMITATIONS.md`); removed `WEEKLY_PLAN.md`'s Week 5/6 evaluator-recruitment/rubric/rating-collection tasks that contradicted `EVALUATION_PLAN.md`'s zero-recruitment pivot, flagging the rest of that schedule as stale pending a fuller pass; and softened `EVALUATION_PLAN.md`'s Tier 1-3 "proves"/"guarantees" language and reframed its terraform-docs comparisons as context rather than a sufficiency argument. `PROJECT_PLAN.md`'s own stale recruited-evaluator "Evaluation Plan" section (lines 203-224) was left untouched, out of scope for this pass.
- 2026-07-22: Phase 4.5 Item 3 — expanded `.github/workflows/ci.yml`'s lint job from `ruff check ir/ parsers/ tests/` to the full maintained project (`generators/ tool1/ tool2/ llm/ evaluation/ cli.py scripts/` added), including the still-near-empty `tool2/`/`llm/`/`evaluation/` stubs so CI doesn't need touching again as Phase 5/6 fill them in. Fixed the 2 pre-existing `E402` errors this surfaced in `scripts/update_golden_files.py` (lines 25-26) via targeted `# noqa: E402` comments rather than restructuring — the `sys.path.insert(0, REPO_ROOT)` two lines above is functionally required before those imports can resolve, so the E402 is a known, standard false-positive pattern, not a real ordering bug. Ruff clean across the full new scope; full non-slow suite unaffected.
