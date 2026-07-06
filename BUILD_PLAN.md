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
- [ ] Implement `parsers/github_actions.py` against the IR schema from Phase 2
- [ ] Handle incrementally, in this order (simplest first): `on` triggers (push/PR/schedule/manual) → `jobs` + `runs-on` → `steps` (both `run:` and `uses:`) → `needs` (dependencies) → `env`/`secrets` references → `if` conditions → `strategy.matrix` → reusable workflows (`uses: ./.github/workflows/...` or external)
- [ ] Test against all fixtures from Phase 1 as each feature is added — don't wait until the end
- [ ] Document parser limitations as you hit them (dynamic expressions like `${{ matrix.python-version }}`, unusual anchor/alias usage) — this becomes report material later, not just a to-do list

**Explicitly deferred:** any other CI platform. Composite actions can be partially deferred if they prove complex — note it and move on rather than blocking the phase.

**Definition of done:** all 8–10 fixture files parse into valid IR without raising, `ir/validate.py` passes on all of them, and there's a written note of known limitations.

---

### Phase 4 — Generators (Layer 3, no LLM) — Tool 1 non-LLM milestone

**Goal:** IR → human-readable structured text, and IR → Mermaid diagram, both pure Python, no LLM. This is a real milestone: **Tool 1 technically exists** end-to-end after this phase, even before the LLM polish pass.

**Tasks**
- [ ] `generators/text_generator.py`: IR → structured plain-text summary (triggers, jobs in order, secrets required — matching the example format in `PROJECT_PLAN.md`)
- [ ] `generators/mermaid_generator.py`: IR job dependency graph → Mermaid `flowchart` syntax
- [ ] Wire both into `tool1/single_pipeline.py`: `YAML file → parser → IR → text output + Mermaid output`, written to a `.md` file in `docs/`
- [ ] Run against all fixtures, visually check the Mermaid renders correctly in a Markdown viewer (GitHub itself renders Mermaid — good sanity check)
- [ ] Show Suzanne this non-LLM output — good moment for her to sanity-check the whole approach before more layers sit on top

**Explicitly deferred:** LLM beautification, Tool 2, animation/step-through feature.

**Definition of done:** running `python cli.py tool1 <path/to/workflow.yml>` produces a Markdown file with an accurate structured summary and a correctly-rendering Mermaid diagram, for every fixture file.

---

### Phase 5 — LLM beautification layer — Tool 1 complete (prototype)

**Goal:** natural, readable prose on top of the Phase 4 output, without the LLM ever seeing raw YAML.

**Tasks**
- [ ] `llm/base.py`: minimal interface (`beautify(structured_text, ir_context) -> prose`) that any provider implements
- [ ] `llm/gemini_provider.py`: Gemini API integration (Google AI Studio free tier)
- [ ] Prompt engineering pass: the prompt must make clear the LLM is rewriting already-verified facts into prose, not analysing or inferring new ones
- [ ] Write a hallucination check as a standalone, importable module (not inlined in the LLM call) — Phase 7 Tier 1 reuses it unmodified, so it needs a clean function signature now, not a refactor later.
- [ ] Test on 5+ pipelines across the complexity range in fixtures
- [ ] `llm/ollama_provider.py`: stub only — interface implemented, not filled in (local LLM stays documented future work per existing scope decision, unless time allows later)

**Explicitly deferred:** full local-LLM mode, multi-provider switching UI, Tool 2.

**Definition of done:** Tool 1 fully complete — `YAML → polished Markdown doc with embedded Mermaid diagram` — for every fixture, with the hallucination check passing on all of them.

---

### Phase 6 — Tool 2: multi-pipeline documentation (GitHub Actions prototype)

**Goal:** the same quality bar as Tool 1, but across a whole repository's `.github/workflows/` folder, producing one unified picture.

**Tasks**
- [ ] `tool2/multi_pipeline.py`: discover all workflow files in a folder, parse each into IR, build a combined view
- [ ] Cross-pipeline relationships: which pipelines fire on which events, any explicit dependencies between workflows (e.g. one workflow triggering another via `workflow_run`)
- [ ] Unified Mermaid diagram covering all pipelines' triggers and jobs
- [ ] Reuse the Phase 4/5 generators and LLM layer — Tool 2 should not need its own separate text/Mermaid/LLM code, just a layer that merges multiple IR objects before handing off to the same generators
- [ ] Test against 2–3 real multi-workflow repos (not just single-file fixtures — pull whole `.github/workflows/` folders)

**Explicitly deferred:** any non-GitHub-Actions repo, animation feature.

**Definition of done:** running `python cli.py tool2 <path/to/repo>` produces one unified Markdown doc + unified Mermaid diagram correctly describing a multi-workflow repository, for at least 2–3 real test repos.

---

### Phase 7 — Evaluation

**Goal:** run the evaluation methods from `EVALUATION_PLAN.md` against the now-complete GitHub Actions prototype of Tool 1 and Tool 2. Full method detail lives in that document — this phase just sequences it.

**Tasks (Tier 1 & 2 — start these as soon as Phase 5/6 land, don't wait)**
- [ ] Coverage check (every IR field appears in output)
- [ ] Diagram-structure check (Mermaid graph matches IR dependency graph exactly)
- [ ] Determinism/variance check (same pipeline, multiple LLM runs, measure drift)
- [ ] Readability metrics (Flesch-Kincaid or similar)
- [ ] Error injection (broken dependency, malformed `if`, undefined secret — does the tool flag it or silently hallucinate?)

**Tasks (Tier 3 — moderate setup)**
- [ ] Correctness check: trigger real pipelines on 4–5 real repos, compare GitHub's actual job/status output to the tool's documentation
- [ ] Natural-pairs comparison: find repos with existing human-written CI docs (README/CONTRIBUTING/wiki), compare tool output directly against them

**Tasks (Tier 4 — needs recruitment lead time, start early)**
- [ ] Recruit 6–8 evaluators
- [ ] Blind three-way comparison (Tool 1): plain structured text vs. full LLM-polished output vs. naive "dump raw YAML into an LLM" baseline
- [ ] Task-based comprehension test (Tool 2): comprehension questions answered using the unified doc vs. raw YAML, split-group

**Explicitly deferred to stretch (Tier 5–6):** think-aloud sessions, real PR submission to open-source repos, generation-time/cost logging (log automatically now, write up only if there's room later).

**Definition of done:** Tiers 1–3 complete with results recorded; Tier 4 evaluator data collected and analysed. See `EVALUATION_PLAN.md` for full rubric and method detail.

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
- [ ] Hallucination check passes on all test fixtures
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
- [ ] Ethics approval for Tier 4 human evaluation recruitment
- [ ] Whether a partial second-platform implementation (Phase 9) is expected to count toward the "platform-agnostic" claim, or whether the architecture argument alone is sufficient

---

## 7. Change log

- *[Add a dated line here each time this document is materially edited, so it's easy to see how the plan actually evolved — useful for the report's process narrative too.]*
- 2026-07-06: Phase 1 skeleton created, IR (schema.py/validate.py) integrated as ir/ package, Phase 2 ground-truth fixtures added.
