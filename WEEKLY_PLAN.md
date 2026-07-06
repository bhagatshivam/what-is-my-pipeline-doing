# Weekly Execution Plan — CI Pipeline Documentation Tool

**Student:** Shivam Balasaheb Bhagat
**Supervisor:** Professor Suzanne Embury
**Plan created:** 1 July 2026
**Build window:** 1 July – 14 August 2026 (45 days)
**Report/video window:** 15 August – 29 August 2026 (15 days)
**Buffer before deadline:** 30 August – 3 September 2026 (~4-5 days)
**Official project period:** 15 June – 3 September 2026

This plan sits alongside `PROJECT_PLAN.md` (the architecture reference). This document is the *schedule* — it doesn't repeat design decisions, it maps them onto weeks.

---

## Ground rules

- Every week ends with a short update to Suzanne: what was completed, what's blocked, what's planned next, and any decision that needs her input.
- Every week is split into **Must-complete / Should-complete / Explicit out-of-scope**, matching the pattern already used for supervision prep.
- Literature review and the open-source documentation survey (deliverables 1 and 2) are **not** parked until report-writing — they're threaded through the build weeks so they don't become a 15-day panic in August.
- Human evaluation requires other people's time (evaluators). This has a lead time, so recruitment starts in Week 5, not Week 6.

---

## Week 1 — 1 July to 7 July: Foundations

**Must-complete**
- Repository set up on GitHub (structure: `parsers/`, `ir/`, `generators/`, `llm/`, `tests/`, `docs/`)
- PyYAML fundamentals solidified — safe_load, nested dict/list traversal, anchors/aliases if encountered
- IR data structures implemented in Python (dataclasses or TypedDicts, matching the schema already defined in `PROJECT_PLAN.md`)
- First-draft GitHub Actions parser: handles `on`, `jobs`, `steps`, `runs-on`, `needs` for a simple single-file workflow

**Should-complete**
- Parser tested against 2-3 real GitHub Actions files pulled from open-source repos
- Start a running literature log (one paragraph per paper as you read it — saves rewriting later)

**Explicit out-of-scope**
- Matrix strategies, reusable workflows, composite actions (defer to Week 2)
- Any LLM integration
- GitLab CI

**To ask Suzanne:** Confirm the IR field-naming table is final, or if she wants any changes before more code depends on it.

---

## Week 2 — 8 July to 14 July: Robust GitHub Actions parsing

**Must-complete**
- Parser extended to handle: `matrix` strategies, `if` conditions, secrets references, environment variables, `uses` (actions), reusable workflow calls
- Parser tested against 8-10 real-world GitHub Actions files of varying complexity (pull from popular open-source repos)
- Structured Text Generator (Layer 3a) — pure Python, IR → plain-text summary (no LLM)

**Should-complete**
- Edge-case notes documented (anything the parser can't yet handle — useful later for the "limitations" section of the report)
- 2-3 more literature entries logged

**Explicit out-of-scope**
- Mermaid diagrams (Week 3)
- LLM beautification (Week 4)

**To ask Suzanne:** Share 2-3 sample outputs of the structured text generator — is the level of detail right, or too much/little?

---

## Week 3 — 15 July to 21 July: Diagrams + Tool 1 complete (non-LLM)

**Must-complete**
- Mermaid Diagram Generator (Layer 3b) — IR job structure → Mermaid flowchart syntax
- End-to-end Tool 1 pipeline working: YAML → parser → IR → structured text + Mermaid diagram (no LLM yet)
- This is a real milestone: **the first deliverable ("tool for converting a single CI pipeline into documentation") technically exists**, even before LLM polish

**Should-complete**
- Start the open-source documentation survey (deliverable 2): sample 15-20 repos, note whether they have pipeline docs, how detailed, how stale
- Literature reading continues (GLITCH, Decan et al., Rahman et al., Schwarz et al.)

**Explicit out-of-scope**
- LLM integration
- Multi-pipeline tool

**To ask Suzanne:** Show the non-LLM output — this is a good moment for her to sanity-check the whole approach before you build further layers on top.

---

## Week 4 — 22 July to 28 July: LLM Layer + survey continues

**Must-complete**
- Gemini API integration (Layer 4) — structured text → natural prose
- Prompt engineering pass: test on 5+ pipelines, check for hallucination (the LLM should never introduce facts not present in the IR — this is a testable property, write a quick check for it)
- Tool 1 fully complete: YAML → polished Markdown doc with embedded Mermaid diagram

**Should-complete**
- Finish or substantially progress the open-source documentation survey (deliverable 2)
- Continue literature log

**Explicit out-of-scope**
- Local LLM (Ollama) — stays as a documented future-work item, not implemented, per existing scope decision
- Multi-pipeline tool

**To ask Suzanne:** Discuss the survey findings so far — do they support the "documentation gap" motivation from Bajpai & Lewis?

---

## Week 5 — 29 July to 4 August: Multi-pipeline tool + start evaluation recruitment

**Must-complete**
- Tool 2: multi-pipeline documentation — reads a folder of workflow files, produces a unified doc + unified Mermaid diagram
- Handles cross-pipeline relationships (which pipelines fire on which events, how they relate)
- **Start recruiting human evaluators now** — this has lead time. Identify 5-10 people (fellow students, developers) willing to rate documentation samples in Week 6

**Should-complete**
- Draft the evaluation rubric (accuracy, clarity, completeness, usefulness — as already planned) so it's ready to send to evaluators
- Pick the 5-10 real repositories that will be used for both evaluation methods

**Explicit out-of-scope**
- Any new features beyond Tool 1 + Tool 2
- Report writing

**To ask Suzanne:** Sign off on the evaluation rubric and the repo selection before you commit evaluator time to it.

---

## Week 6 — 5 August to 11 August: Evaluation execution

**Must-complete**
- **Method 1 (correctness check):** trigger real pipelines on the 5-10 selected repos, compare GitHub's actual job/status output against the tool's documentation
- **Method 2 (human evaluation):** send materials to recruited evaluators, collect ratings against the rubric
- Begin compiling evaluation results into tables/charts usable in the report

**Should-complete**
- Bug fixes surfaced by evaluation (parser edge cases, LLM inconsistencies)
- Literature review reading essentially finished by end of this week

**Explicit out-of-scope**
- New features — this week is evaluation and stabilization only, resist scope creep

**To ask Suzanne:** Flag early results — if something in the evaluation looks off, better to know now than during write-up.

---

## Week 6.5 — 12 August to 14 August: Buffer + wrap-up

**Must-complete**
- Finish collecting all evaluator responses (chase stragglers)
- Finalize evaluation analysis — numbers, any statistical summary, key quotes/observations from evaluators
- Freeze the codebase for reporting purposes (tag a release on GitHub)
- Assemble a folder of report assets: architecture diagram, example outputs, evaluation charts

**Should-complete**
- Skim back through supervision log to make sure nothing discussed with Suzanne got lost

**Explicit out-of-scope**
- New code changes after this point unless a critical bug blocks the report

---

## Report + Video: 15 August – 29 August (15 days)

Word count target: 8,000 (7,000-9,000 acceptable). Weighting reminder: Abstract 5%, Introductory Material 20%, Methodology 20%, Evaluation/Reflection 20%, Conclusion 10%, Format/Structure 5%, Project Achievement 20%. Video is 15% of the overall grade, separate from the report.

| Days | Focus | Notes |
|---|---|---|
| Day 1-2 (Aug 15-16) | Introductory Material (~1,600 words) | State the problem, cite Bajpai & Lewis for the security motivation, scope the subject area, state objectives clearly. Concise lit review lives here, not a separate section. |
| Day 3-5 (Aug 17-19) | Methodology (~1,600 words) | Architecture (4 layers), IR design and justification, why Python-first/LLM-selective, GLITCH precedent, alternatives considered and why rejected. Use the architecture diagram from the buffer week. |
| Day 6-8 (Aug 20-22) | Evaluation and/or Reflection (~1,600 words) | Both evaluation methods, results, tables/charts, honest discussion of what the correctness check vs. human evaluation each show, justify the methodology choice via Hu et al. (2022). This section is 20% — don't rush it. |
| Day 9 (Aug 23) | Conclusion (~800 words) | Tie back to objectives stated in the introduction, thoughtful future work (local LLM, GitLab CI, animation feature — these become *strengths* here, framed as a considered roadmap rather than things you didn't get to). |
| Day 10 (Aug 24) | Abstract (~400 words) | Write this last, once the whole story is settled — it's only 5% but it's the reader's first impression. |
| Day 11-12 (Aug 25-26) | Format, structure, references, figures | Number all figures/tables, check reference formatting consistency, read the whole thing aloud once for flow. |
| Day 13-14 (Aug 27-28) | Video (6-8 min) | Script first, then record. Use it to show things the report can't — the tool actually running, the diagram rendering live, a real pipeline being documented in real time. A talking-head overlay is encouraged by the rubric. |
| Day 15 (Aug 29) | Final review | Full read-through, check word count is in range, submit. |

**Buffer:** 30 August – 3 September is deliberately unallocated. Use it for anything that slipped, not for new work.

---

## Deliverable-to-week mapping (sanity check)

| Deliverable | Covered in |
|---|---|
| Literature survey on doc generators | Threaded Weeks 1-6, written up Week "Intro" |
| Survey of existing OSS pipeline docs | Weeks 3-4 |
| Single pipeline → documentation tool | Weeks 1-4 |
| Multi-pipeline → documentation tool | Week 5 |
| Evaluation vs. human-written docs | Weeks 5-6.5 |

All five deliverables from the original project proposal are accounted for before report writing starts.

---

## Risks worth flagging to Suzanne now

- **Evaluator recruitment (Week 5-6)** is the piece most dependent on other people's availability — starting it a week early (Week 5) is a deliberate buffer against people being slow to respond.
- **45 build days assumes close to full-time hours.** If a week slips, the buffer at the end (Aug 30 - Sep 3) is the safety net, not extra build time — protect it.
- GitLab CI and local LLM (Ollama) remain explicitly out of scope for the build, staying as documented future work — this was already agreed and keeps the 45 days realistic.

---

*Living document — update actuals vs. plan at the end of each week.*
