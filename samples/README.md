# Sample outputs (for SME review)

These are illustrative outputs generated from **Tier 1 fixture pipelines** —
the same workflow files used by the project's golden tests under
`tests/fixtures/` / `tests/golden/`. They are **not** held-out evaluation
data: nothing in `evaluation/held_out_workflows/` was touched to produce
these samples, and none of them feed into any Tier 4 scoring.

## Naming convention

Every file is named `<tool>.<fixture>.<variant>.md`:

- **`tool1.*`** — Tool 1 (`cli.py tool1`), documents a single workflow file.
- **`tool2.*`** — Tool 2 (`cli.py tool2`), documents a whole repository's
  `.github/workflows/` folder as one unified doc.
- **`*.deterministic.md`** — Layers 1–3 only (parse → IR → deterministic
  text + Mermaid generators). No LLM involved, no API key needed.
- **`*.beautified.md`** — the same deterministic output, plus a
  `## Overview` section from the Layer 4 Gemini beautifier
  (`llm/gemini_provider.py`), inserted verbatim between marker comments.
  Everything below the Overview section (the fact block and diagram(s))
  is byte-identical to the deterministic version — the LLM only ever adds
  prose, never edits extracted facts.

Each pair was generated via the existing, unmodified entrypoints
(`tool1.single_pipeline.document_pipeline()` / `tool2.multi_pipeline.document_repository()`
— the same code paths as `cli.py tool1 <path>` / `cli.py tool2 <path>`). No
tool, generator, evaluation, or fixture code was modified to produce them,
and their deterministic sections are verified byte-identical to the
corresponding committed golden files under `tests/golden/`.

## Tool 1 pairs (single pipeline)

### `tool1.rust_ci.*` (dependency structure → real diagram)

Source: `tests/fixtures/rust_ci.yml`

This pipeline has real `needs:` edges (`job` depends on `calculate_matrix`;
`outcome` depends on both). What to look at:

- The `## Pipeline Diagram` section renders an actual Mermaid flowchart
  showing the `calculate_matrix → job → outcome` dependency chain.
- In the beautified version, check that the `## Overview` prose accurately
  summarizes the job graph, triggers, secrets, and conditional deployment
  logic **without inventing anything** beyond what the deterministic fact
  sheet states.

### `tool1.eslint_ci.*` (no declared dependencies → honest prose note)

Source: `tests/fixtures/eslint_ci.yml`

This pipeline's 6 jobs have no `needs:` between them at all. What to look
at:

- Instead of a Mermaid diagram with no edges (which would just be 6
  disconnected boxes conveying nothing), the `## Pipeline Diagram` section
  shows a one-line note: "All 6 jobs are independent — no job-dependency
  diagram is shown." This is a deliberate document-assembly decision (see
  `tool1/single_pipeline.py`'s module docstring, "Phase 7.5 fix") — not a
  bug or a missing feature.
- In the beautified version, check that the Overview prose doesn't
  fabricate a dependency relationship that isn't there.

**Compare deterministic vs. beautified**: facts (triggers, jobs, secrets,
diagram) should be identical between the two; only readability/prose
should differ.

## Tool 2 pairs (whole repository)

### `tool2.black.*` (workflows that reference each other)

Source: `tests/fixtures/multi/black/.github/workflows/` (3 files)

`diff_shades_comment.yml` runs `on: workflow_run` after `diff_shades.yml`
completes. What to look at:

- The `## Workflow Relationships` table marks `diff_shades_comment_yml` as
  "follows diff_shades_yml", and a `### Workflow-to-Workflow Diagram`
  Mermaid diagram renders that cross-file edge — on top of the normal
  `## Pipeline Diagram` for job-level dependencies within `diff_shades.yml`
  itself.
- In the beautified version, check the Overview prose correctly separates
  "runs after this other workflow finishes" from ordinary intra-file
  `needs:` dependencies, since both exist in this repo at once.

### `tool2.starlette.*` (workflows that don't reference each other)

Source: `tests/fixtures/multi/starlette/.github/workflows/` (3 files)

None of this repo's workflow files trigger each other. What to look at:

- The `## Workflow Relationships` table marks every workflow file
  "independent", and — since two files happen to share the exact same
  push trigger — a note explains that GitHub Actions gives no ordering
  between them even though they fire on the same event. No
  Workflow-to-Workflow Diagram is shown, since there's no cross-file edge
  to draw (same "don't draw an empty diagram" philosophy as Tool 1's
  `eslint_ci` case above, applied at the repo level instead of the job
  level).
- In the beautified version, check the Overview prose doesn't imply an
  execution order between files that GitHub Actions doesn't actually
  guarantee.

**Compare deterministic vs. beautified**: facts (the relationship table,
diagrams, triggers, jobs, secrets) should be identical between the two;
only readability/prose should differ.
