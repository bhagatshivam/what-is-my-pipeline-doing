# Sample outputs (for SME review)

These are illustrative outputs generated from **Tier 1 fixture pipelines** —
the same workflow files used by the project's golden tests under
`tests/fixtures/` / `tests/golden/`. They are **not** held-out evaluation
data: nothing in `evaluation/held_out_workflows/` was touched to produce
these samples, and none of them feed into any Tier 4 scoring.

Each pipeline is documented twice, using the existing, unmodified tool
chain (`generate_text()` + `generate_mermaid()`, optionally followed by
the Gemini `beautify()` layer):

- `*.deterministic.md` — Layers 1–3 only (parse → IR → deterministic text
  + Mermaid generators). No LLM involved, no API key needed.
- `*.beautified.md` — the same deterministic output, plus a `## Overview`
  section from the Layer 4 Gemini beautifier (`llm/gemini_provider.py`),
  inserted verbatim between marker comments. Everything below the
  Overview section (the fact block and diagram) is byte-identical to the
  deterministic version — the LLM only ever adds prose, never edits
  extracted facts.

## Pairs included

### `rust_ci` (dependency structure → real diagram)

Source: `tests/fixtures/rust_ci.yml`

This pipeline has real `needs:` edges (`job` depends on `calculate_matrix`;
`outcome` depends on both). What to look at:

- The `## Pipeline Diagram` section renders an actual Mermaid flowchart
  showing the `calculate_matrix → job → outcome` dependency chain.
- In the beautified version, check that the `## Overview` prose accurately
  summarizes the job graph, triggers, secrets, and conditional deployment
  logic **without inventing anything** beyond what the deterministic fact
  sheet states.

### `eslint_ci` (no declared dependencies → honest prose note)

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

## How these were generated

Via the existing `tool1.single_pipeline.document_pipeline()` entrypoint
(same code path as `cli.py tool1 <path>`), called directly against the two
fixture files above — no tool, generator, or fixture code was modified to
produce these samples.
