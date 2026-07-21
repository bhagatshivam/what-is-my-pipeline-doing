# Known parser limitations

Tracked as they're discovered during `parsers/github_actions.py` development
(BUILD_PLAN.md Phase 3), for write-up in the dissertation report. This file
didn't exist before the `jobs:` parsing pass — it's seeded here with the
limitations already present as inline `# LIMITATION:` comments from the
`on:` trigger-parsing pass, plus the new ones this pass introduces.

Every entry below follows the same rule as the code itself: nothing is
silently dropped. Where the IR schema has no structured field for something,
the original data still survives in `Trigger.raw` or `Job.raw_extras`.

## Triggers (`on:`)

- **`types:` activity filter** (e.g. `pull_request: {types: [opened, ...]}`,
  `release: {types: [published]}`) narrows which activity types fire the
  event. The IR's `Trigger` schema has no field for this — preserved only in
  `Trigger.raw`, not structured. Seen in `tests/fixtures/node_test_linux.yml`.
- **`schedule:` with a non-list value.** GH Actions always documents
  `schedule:` as a list of `{cron: "..."}` entries; if it were ever anything
  else, the parser preserves `raw` and doesn't guess a cron string. Not seen
  in any current fixture — defensive only.
- **`workflow_call`'s `secrets:` and `outputs:` blocks** aren't modelled by
  `Trigger` (only `inputs:` is) — preserved only in `raw`.
- **`workflow_run` listing multiple upstream workflow names**
  (`workflows: [A, B]`). `Trigger.source_workflow` is a single string, so
  only the first is captured structurally; the full list stays in `raw`.
- **Non-string items inside the list form of `on:`** (e.g. `on: [push, {weird: true}]`).
  Only bare event-name strings are documented as valid there; an unexpected
  entry is preserved as `TriggerType.OTHER` with `raw` set, not guessed at.
  Not seen in any current fixture — defensive only.
- **An `on:` value that's neither a string, list, nor map at all.** Same
  treatment as above (`TriggerType.OTHER`, `raw` preserved). Not seen in any
  current fixture — defensive only.

## Jobs (`jobs:`)

- **Matrix-templated `runs-on`** (e.g. `runs-on: ${{ matrix.os }}`, or with a
  fallback like `${{ matrix.os || 'ubuntu-latest' }}` in
  `tests/fixtures/flask_tests.yml`). Stored as the raw expression string,
  unresolved. **Revisited now that matrix parsing has landed** (see
  `## Matrix strategy` below) — this is *not* reconciled against
  `Job.matrix.axes`, and that's a final decision, not a "later pass" TODO:
  resolving which concrete runner each matrix *combination* gets requires
  expanding one YAML job definition into N resolved instances (one per
  combination), which is a fan-out/expansion concern for a downstream
  generator or consumer, not a single `Job` object's parsing concern
  (`Job.runner` is a single `Optional[str]`, not a per-combination list).
  `Job.matrix.axes` now separately exposes the actual axis values a
  consumer would need to do that expansion itself. This is the *majority*
  shape across the 10 fixtures, not an edge case (e.g. every job in
  `tests/fixtures/setup_python_test.yml`).
- **List-form `runs-on`** (self-hosted runner labels, e.g.
  `runs-on: [self-hosted, linux, x64]`). `Job.runner` is a single
  `Optional[str]`, so the labels are joined into one comma-separated string;
  the original list structure isn't preserved separately. Not seen in any
  current fixture — untested against real-world data.
- **Job-level `name:` vs. the job's YAML key.** These frequently differ
  (e.g. `tests/fixtures/eslint_ci.yml`'s `verify_files` job displays as
  "Verify Files"; several jobs' `name:` values are themselves GH Actions
  expressions, like `tests/fixtures/pytorch_lint.yml`'s
  `` lintrunner-clang-${{ needs.get-changed-files.outputs.changed-files == '*' && 'all' || 'partial' }} ``).
  `Job.name` must stay the YAML key since it's what `needs:`/`dependencies`
  will reference once implemented; the display name is preserved in
  `Job.raw_extras["display_name"]` rather than dropped, but is not
  otherwise interpreted or evaluated. **Revisited now that matrix parsing
  has landed**: some display names are themselves matrix expressions
  (e.g. `tests/fixtures/pandas_unit_tests.yml`'s `ubuntu` job:
  `"${{ matrix.name || format('{0} {1}', matrix.platform, matrix.environment)
  }}"`) — this pass doesn't change anything about that. Resolving a
  per-combination display name is the same matrix-expansion concern as the
  `runs-on` case above, not a matrix-*strategy*-parsing concern, so it
  stays verbatim and unresolved.

## Steps (`steps:`)

`env:`, `continue-on-error:`, and `if:` (all deferred when this section was
first written) are now implemented — see `## Environment variables and
secrets`, `## continue-on-error`, and `## Conditions (if:)` below.

- **`StepType.SCRIPT` is never produced by this parser.** GH Actions has no
  distinct YAML construct for "external script reference" vs. an inline
  command — `run: ./deploy.sh` is syntactically identical to `run: npm
  test`. Every `run:` step maps to `StepType.COMMAND`; `SCRIPT` exists in
  the IR for platforms that do distinguish the two (e.g. a dedicated
  `script:` file reference) and may go entirely unused by this parser.
- **Name-fallback heuristic when `name:` is absent** (37 of 299 steps
  across the 10 fixtures — not rare). `uses:` steps fall back to the action
  ref itself; `run:` steps fall back to the first non-empty line, truncated
  to ~60 chars at the last word boundary (preferring to complete the word
  straddling the cutoff, up to a 75-char ceiling, over cutting mid-word —
  a strict cut at the 60-char boundary was tried first and found to drop
  meaningful words like `typing` in `flask_tests.yml`'s `typing` job
  entirely). This is a parser design choice that can affect the
  *readability* of generated documentation (a truncated first line is a
  weaker step label than a hand-written name), not a silent data-loss
  concern — the original `run:`/`uses:` value is always intact in
  `Step.value` regardless of what name was derived. Separately, a
  SHA-pinned `uses:` ref (40 hex chars after `@`, e.g.
  `actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0` — 15 of 30
  `uses:` fallbacks across the fixtures) is shortened to just the
  `owner/repo` part for the name fallback, since the full SHA is unreadable
  as a display label; tag/branch-pinned refs (e.g. `actions/checkout@v7`)
  are left as the full string, since those are already readable.
  `Step.value` is unaffected by this either way.
- **`shell:` and `working-directory:`** (33 and 4 occurrences respectively)
  have no dedicated `Step` field and no pass currently scheduled to add
  one, unlike env/continue-on-error/if (all now implemented) — preserved
  in `Step.raw_extras["shell"]` / `["working-directory"]` rather than
  dropped.
- **A step with neither `uses:` nor `run:`.** Not valid GH Actions syntax
  as far as we've seen (0 of 299 steps) — the whole step body is preserved
  in `Step.raw_extras["unrecognized_step"]` and `StepType.COMMAND` is used
  as a neutral placeholder type, rather than raising or guessing. Untested
  against real-world data.
- **A non-dict entry inside `steps:`.** Same treatment as above — not seen
  in any current fixture, defensive only.

## Job dependencies (`needs:`)

No limitations found, all shapes handled cleanly. Across all 10 fixtures
(58 jobs total), `needs:` is either absent (42 jobs), a single job-key
string (6 jobs, 6 edges), or a list of job-key strings (10 jobs, 17 edges)
— 23 dependency edges total. Every referenced key resolves to an actual
sibling job key in the same file, and `ir.validate.is_valid()` passes with
zero errors on all 10 parsed pipelines, including the dependency-existence
and circular-dependency checks now exercised for the first time against
real multi-job graphs.

Two shapes remain defensive-only (`# LIMITATION:` comments in
`_parse_dependencies`, `parsers/github_actions.py`), since no fixture
exercises them: a `needs:` list containing a non-string item (coerced via
`str()` rather than raised), and a `needs:` value that's neither a string
nor a list, e.g. a dict (treated as no dependencies). Both are untested
against real-world data.

## Environment variables and secrets

Across all 10 fixtures: 3 have a top-level `env:` (`fastapi_test.yml`,
`node_test_linux.yml`, `rust_ci.yml`), 6 job-level `env:` blocks, and 20
step-level `env:` blocks. `${{ secrets.X }}` references: 8 total, across
exactly 2 fixtures (`pandas_unit_tests.yml`: 1, inside a step's `with:`
arg, not `env:`; `rust_ci.yml`: 7, across pipeline/job/step-level `env:`).
`ir.validate.is_valid()` passes with zero errors on all 10 parsed
pipelines, exercising `_check_secret_and_env_scopes` against real
multi-scope data for the first time.

- **Textual regex scan for secret references, not an expression parser.**
  `_extract_secret_names` matches `secrets\.([A-Za-z0-9_]+)` against the
  stringified value of any `env:`/`with:`/`run:` entry. It cannot catch a
  secret referenced via unusual indirection — bracket syntax
  (`secrets['X']`) or a name built dynamically from a matrix/context value.
  Not seen in any of the 10 fixtures' 8 real secret references.
- **`EnvironmentVariable.value` always stores the raw string, never `None`
  for an expression.** `ir/schema.py`'s inline comment on `value` suggests
  `None` "if the value is itself a secret/dynamic reference, not a
  literal." This parser instead stores the raw expression string verbatim
  for *every* non-null value, including secret references — a deliberate
  divergence. Reasons: (1) the majority of real env values across these
  fixtures are expressions in general (e.g. `${{ matrix.python-version }}`),
  not just secrets, and `EnvironmentVariable` has no separate `raw` field
  the way `Trigger`/`Condition` do — nulling every non-literal value would
  silently drop most of the real data with nowhere else for it to live;
  (2) it's structurally safe to store a secret-referencing expression
  string verbatim: this parser only ever reads static workflow YAML
  source, where `${{ secrets.X }}` is always the literal, unresolved
  reference expression. GitHub Actions resolves the actual secret value at
  runtime inside GitHub's own infrastructure, and that resolved value is
  never written back into the workflow file this parser reads — so
  storing the expression string can never leak a real secret value,
  because the real value never appears in the input at all. The secret's
  *identity* is also captured separately as its own `Secret` entry in
  `Pipeline.secrets` regardless of this choice, so nothing about "this is
  a secret" is lost either way.
- **Secret deduplication: by `(name, scope, scope_ref)`.**
  `ir.validate._check_secret_and_env_scopes` does no uniqueness checking
  at all — it tolerates duplicate `Secret` entries freely. This parser
  still dedupes by the `(name, scope, scope_ref)` tuple: the same secret
  referenced twice in the exact same scope location collapses to one
  entry (no new information), but the same secret referenced from two
  different jobs/steps stays as two separate entries, since those are
  genuinely different usage sites. No fixture has an actual duplicate
  reference to exercise this — covered by a hand-written snippet test
  instead.
- **`scope_ref` for `STEP` scope is `f"{job_key}.{step_index}"`** (0-based
  step index, not step name) — steps frequently lack a stable, unique
  `name:`. Safe by GH Actions spec, not just by luck: job-id syntax only
  permits `[A-Za-z_][A-Za-z0-9_-]*`, so a job key can never itself contain
  a `.` that would confuse `scope_ref.split(".")[0]` (what
  `_check_secret_and_env_scopes` uses to find the owning job). Confirmed
  empirically too: no job key in any of the 10 fixtures contains a `.`.
- **Boolean env values are lowercased.** GH Actions coerces `env:` values
  to strings at runtime, and a YAML boolean becomes `"true"`/`"false"`
  (lowercase) — not Python's `str(True)` == `"True"`. `_stringify_env_value`
  special-cases bools to match. Seen in `fastapi_test.yml`'s
  `UV_NO_SYNC: true`.
- **Job-level `with:` secret-scanning is defensive-only.** `_iter_scoped_blocks`
  scans job-level `with:` (relevant for a reusable-workflow-call job
  passing literal values) alongside job-level `env:`, but no fixture's
  job-level `with:` happens to contain a secret reference.
- **Job-level `secrets:` (reusable-workflow-call jobs) is out of scope
  this pass.** GH Actions has a distinct mechanism for a job that calls a
  reusable workflow (`jobs.<id>.uses: ./path/to/workflow.yml`) to pass
  secrets into it — a job-level `secrets:` key, either explicit
  name→value pairs or the literal `secrets: inherit`. This is different
  from `with:`/`env:` and isn't scanned by `_iter_scoped_blocks`. Checked
  directly: `eslint_ci.yml`'s `test_package_manager` job (the only
  `uses:`-based reusable-workflow-call job across all 10 fixtures) has no
  `secrets:` key, and no fixture has one at all. Deferred to a future
  reusable-workflows pass rather than scanned here — a deliberate scope
  boundary, not an oversight.
- **Resolved: secrets referenced inside `if:` condition expressions are now
  scanned.** This was previously deferred here since `if:` parsing didn't
  exist yet. Now that it does (see `## Conditions (if:)` below),
  `_iter_scoped_blocks` yields each scope's `if:` value alongside
  `env:`/`with:`/`run:`, and `_parse_secret_references` scans it via the
  same `_extract_secret_names` — no new regex/extraction logic. Checked
  directly: none of the 44 real `if:` expressions across the 10 fixtures
  reference a secret, so this has zero behavioral impact on current
  fixtures; the wiring is proven correct via hand-written snippet tests
  instead (`tests/test_github_actions_conditions.py`).

## continue-on-error

GH Actions allows `continue-on-error:` at **both** job and step level, not
just step level as initially assumed — confirmed directly in
`rust_ci.yml`, which has one job-level occurrence and two step-level
occurrences (all three confined to that single fixture; no other fixture
uses `continue-on-error:` at all).

- **Step-level** (`Step.continue_on_error`): both real occurrences
  (`rust_ci.yml`, steps 31 and 32 of job `job`) are literal `true`. Handled
  via `_parse_continue_on_error`: a literal bool is used as-is; anything
  else defaults to `False`. GH Actions allows an expression here in
  principle, but `Step.continue_on_error` is strictly bool-typed with no
  raw-expression fallback field, so a non-bool value can't be faithfully
  represented — untested against real step-level data, since no fixture
  has this shape.
- **Job-level** (`Job.allow_failure`): `rust_ci.yml`'s `job` job has
  `continue-on-error: ${{ matrix.continue_on_error || false }}` — an
  **expression**, not a literal boolean. `ir/schema.py`'s `Job.allow_failure`
  (a pre-existing field for exactly this GitLab/GH-Actions concept — no
  schema change needed) is wired to a literal bool as-is via
  `_parse_job_continue_on_error`; for the expression case, `allow_failure`
  stays at its safe default `False` (coercing an expression to bool would
  be guessing) and the raw expression string is preserved in
  `Job.raw_extras["continue_on_error_expression"]` instead of being
  silently dropped.

## Conditions (`if:`)

Across all 10 fixtures: **44 total `if:` occurrences** (19 job-level, 25
step-level), spread across 6 fixtures (`checkout_check_dist.yml`,
`fastapi_test.yml`, `node_test_linux.yml`, `pandas_unit_tests.yml`,
`pytorch_lint.yml`, `rust_ci.yml`); 4 fixtures have zero `if:` usage.
`ir.validate.is_valid()` passes with zero errors on all 10 parsed
pipelines, exercising `_check_conditions` against real data for the first
time.

- **`Condition.expression` always preserves the original text verbatim,
  `${{ }}` wrapper included or omitted exactly as written.** GH Actions
  allows both (12 of 44 real conditions are wrapped, 32 are bare) —
  `expression` is never normalized to one form, since it's documented as
  the ground truth. A `${{ }}`-stripped copy is used only internally, for
  structured-pattern matching, and is never stored.
- **Only two structured patterns are recognized**, deliberately narrow —
  this is not a general expression parser:
  - a bare (optionally negated) status-check function call — `always()`,
    `success()`, `failure()`, `cancelled()` — → `{"type": "status_check",
    "function": ..., "negated": bool}`. 2 real matches (both `always()`:
    `fastapi_test.yml`'s `test-alls-green` job, `rust_ci.yml`'s `job` step
    28). Negation isn't exercised by any real fixture — untested against
    real data, covered by a snippet test instead.
  - a bare `github.ref == 'X'` / `github.event_name == 'X'` equality → 
    `{"type": "ref_equals"/"event_equals", "value": ...}`. 1 real match
    (`rust_ci.yml`'s `calculate_matrix` step 1, a `ref_equals`); zero real
    `event_equals` matches — every real `github.event_name` occurrence is
    combined with `&&`/`||`, never bare — covered by a snippet test.
  - Everything else (41 of 44 real conditions) → `{"type": "unparsed"}`,
    including 9 real `github.repository_owner`/`github.repository`
    equality checks that are structurally just as simple as the recognized
    `github.ref`/`github.event_name` patterns but intentionally not
    matched, to keep the recognized set small and explicit rather than
    open-ended.
  - **`needs.<job>.outputs.*`/`needs.<job>.result` references are a
    meaningfully common real shape** (7 occurrences across `fastapi_test.yml`,
    `pytorch_lint.yml`, `rust_ci.yml`) that isn't structured-parsed this
    pass — a reasonable future enhancement, not an oversight.
- **A real (not hypothetical) literal-boolean `if:` case.**
  `pandas_unit_tests.yml`'s `python-dev` job has `if: false` — a literal
  YAML boolean, not a `${{ }}` string at all. `_parse_condition` lowercases
  this to `"false"`/`"true"` (mirroring `_stringify_env_value`'s precedent
  from the env/secrets pass), not Python's `str(False) == "False"`.
- **A real multi-line block-scalar case.** `pytorch_lint.yml`'s
  `lintrunner-clang`/`lintrunner-pyrefly` jobs use `if: |` spanning ~10
  lines with chained `contains(...)` calls. No special handling was
  needed — the loaded string (embedded newlines and all) is stored as-is
  in `expression`, and correctly falls through to `unparsed` since it
  doesn't match either recognized pattern.
- **A non-string, non-bool `if:` value** (not seen in any fixture) is
  stringified defensively via `str(if_value)` rather than raised —
  untested against real data.

## Matrix strategy

**24 of 60 jobs** across 9 of the 10 fixtures have a `strategy.matrix`
block (only `checkout_check_dist.yml` has none); `setup_python_test.yml`
has one in every one of its 14 jobs. `ir.validate.is_valid()` stays `True`
on all 10 parsed pipelines, but `validate_pipeline()` is genuinely **not**
clean for 3 of them — see below, this is expected and accepted, not
suppressed.

- **`_check_matrix_structures` produces exactly 20 real warnings across 5
  jobs in 5 distinct fixtures** (computed by hand against the real data,
  then confirmed by running `validate_pipeline()` directly): 3 "matrix
  object with no axes defined" (`flask_tests.yml`'s `tests`,
  `pytorch_lint.yml`'s `test_collect_env`, `rust_ci.yml`'s `job` — all
  three are `include:`-only matrices with zero declared axes, a common and
  valid real GH Actions pattern, not a typo) plus 17 "include references
  axes not in the matrix" (7 for `fastapi_test.yml`'s `test` — `coverage`/
  `codspeed`/`without-httpx2` are real extra per-combination keys added via
  `include:` beyond the base axes, also valid usage — and 10 for
  `pandas_unit_tests.yml`'s `ubuntu`, mostly the `name` key). All
  warning-severity, never error, so nothing here fails validation — the
  parser's job is just to populate the data faithfully and let the
  existing validator flag what it's designed to flag, not to pre-filter or
  suppress.
- **A real, genuinely dynamic matrix**: `rust_ci.yml`'s `job` has
  `strategy.matrix.include: ${{ fromJSON(needs.calculate_matrix.outputs.jobs)
  }}` (a string expression, not a literal list — the whole job matrix is
  populated at runtime from a prior job's output) *and*
  `strategy.fail-fast: ${{ needs.calculate_matrix.outputs.run_type != 'try' }}`
  (also a dynamic expression, not a literal bool) — the only fixture/job
  with either shape. Neither can be resolved statically: `MatrixStrategy.include`
  stays `[]` and `.fail_fast` stays `None` (safe defaults, not guesses),
  with the raw expressions preserved in `Job.raw_extras["matrix_include_expression"]`
  / `["matrix_fail_fast_expression"]` instead of being silently dropped. A
  dynamic `exclude:` is handled symmetrically (`_parse_matrix_combinations`
  is shared by both `include:`/`exclude:`) but isn't exercised by any real
  fixture — untested against real data.
- **`max-parallel:`** doesn't appear anywhere in any of the 10 fixtures,
  and `MatrixStrategy` has no field for it — if it were ever present, it
  would be preserved in `Job.raw_extras["max_parallel"]` rather than
  dropped. Untested against real data.
- **Axis values are stringified defensively** (reusing
  `_stringify_env_value`'s bool-lowercase + `str()` logic, with an
  explicit `None -> "null"` mapping for the "axis element is itself
  YAML null" case, which `_stringify_env_value` doesn't need to handle on
  its own) even though every real axis value across all 10 fixtures is
  already a YAML string — including tricky-looking cases like
  `setup_python_test.yml`'s `3.9.13`, which doesn't match YAML's float
  regex and loads as a string regardless. Purely defensive, not a real
  need this pass.
- **`_parse_matrix`'s signature deviates from a simple `Optional[MatrixStrategy]`
  return** — it returns `(Optional[MatrixStrategy], Dict[str, str])`,
  generalizing `_parse_job_continue_on_error`'s established "return the
  unresolvable raw expression alongside the resolved value, let the caller
  stash it in `raw_extras`" pattern from the continue-on-error pass to
  matrix's four independent unresolvable sub-values (`fail-fast`,
  `include`, `exclude`, `max-parallel`) rather than inventing a second
  mechanism for the same underlying problem.

## Reusable workflows

This is the last item in `BUILD_PLAN.md`'s original Phase 3 ordering —
after this pass, `GitHubActionsParser` implements every field Phase 3
scoped for it.

GH Actions relates one workflow file to another in three distinct ways,
and each is handled differently:

- **Job-level `uses:`** (a job that IS a reusable-workflow call) ->
  `Pipeline.linked_workflows` gets a `LinkedWorkflow(relationship="calls")`
  entry. Real in 2 of the 10 fixtures: `eslint_ci.yml`'s
  `test_package_manager` job (1 occurrence) and `pytorch_lint.yml` (10
  occurrences across 10 distinct jobs). The other 8 fixtures have zero.
- **`on: workflow_run`** (this pipeline fires when another workflow
  completes) -> `LinkedWorkflow(relationship="triggered_by")`, reusing
  `Trigger.source_workflow` (already extracted by PR #3's
  `_parse_workflow_run`) rather than re-deriving it from the raw data a
  second time — this is why `_parse_linked_workflows(data, triggers)`
  takes the already-parsed triggers list too, deviating from a
  `data`-only signature (same precedent as `_parse_matrix`'s signature
  deviation above). Not exercised by any of the 10 fixtures — covered
  only by a hand-written snippet test.
- **`on: workflow_call`** (this pipeline being callable BY another
  workflow) -> **deliberately NOT promoted to a `LinkedWorkflow` entry.**
  This isn't a deferral, it's structural: the callee has no way to learn
  its callers' identity from its own file, so there's no `target` to
  populate. This data remains solely on the existing
  `Trigger(type=WORKFLOW_CALL)` object (see PR #3). Not exercised by any
  fixture either.

**Deduplication is by `(target, relationship)` alone**, not by job or
usage site. Unlike `Secret` (deduped by `(name, scope, scope_ref)`, which
preserves distinct usage sites), `LinkedWorkflow` has no field recording
*which* job made a given call — the relationship is file-to-file per its
own docstring, not job-to-file. 7 of `pytorch_lint.yml`'s 10 `uses:` jobs
point at the identical `./.github/workflows/_lint.yml` and collapse to a
single entry; across all 10 fixtures this produces exactly **5 distinct
`LinkedWorkflow` entries** (1 from `eslint_ci.yml`, 4 from
`pytorch_lint.yml`), all `relationship="calls"`.

**A calling job's own `uses:`/`with:`/`secrets:` are preserved on that
job's `raw_extras`**, not on `LinkedWorkflow` — `LinkedWorkflow` has no
escape hatch at all (just `target`+`relationship`), so `raw_extras["uses"]`
(the raw string), `raw_extras["with"]` (present on 10 of the 11 real
`uses:`-jobs — only `eslint_ci.yml`'s `test_package_manager` lacks a
`with:` block), and `raw_extras["secrets"]` (when present) live there
instead. A calling job still gets its `condition`/`environment`/
`allow_failure`/`matrix` parsed normally — job-level `uses:` doesn't
disable any of that. `raw_extras["secrets"]` is untested against real
data: none of the 11 real `uses:`-jobs across all 10 fixtures has a
`secrets:` key.

## Text generator

`generators/text_generator.py`'s `generate_text()` is a purely mechanical,
non-LLM transform over the IR — it never infers semantic meaning from job
or step names/commands (that's Layer 4's job on top of these
Python-verified facts, not this layer's). Verified against all 10 real
fixtures plus the 3 Phase 2 ground-truth fixtures by reading the actual
generated output, not just checking it doesn't raise.

- **Matrix combination counts are exact only when `axes` is the sole
  populated field (or when `include` is the sole populated field with
  empty `axes`).** When `axes` and `include` are both non-empty (real in
  `eslint_ci.yml`'s `test_on_node`, `fastapi_test.yml`'s `test`,
  `pandas_unit_tests.yml`'s `ubuntu`), the output states the axis-product
  base count plus a separate "+N via include" rather than a single merged
  figure — true GH Actions `include:` merge semantics (extend a matching
  combo vs. append a new row) aren't replicated. Similarly, when `axes`
  and `exclude` are both non-empty (real in `setup_python_test.yml`'s
  `setup-versions-from-tool-versions-file`), the output is phrased as "up
  to N combinations, M excluded" rather than a precise subtraction, since
  a partial-key exclude entry could remove more than one row. A fully
  dynamic matrix (`rust_ci.yml`'s `job`: empty axes and empty include,
  populated at runtime via `fromJSON(...)`) is reported as "combinations
  determined at runtime" rather than falsely claiming 0 or 1.
- **`Job`/`LinkedWorkflow` are not mapped 1:1 in the output, by design.**
  A `uses:`-only reusable-workflow-calling job (real in `eslint_ci.yml`
  and `pytorch_lint.yml`) shows up in `JOBS (in order)` with `runner`
  omitted and "0 steps" — nothing about *what* it calls, since that
  detail lives only in `Job.raw_extras`, which this generator never
  reads. The separate `LINKED WORKFLOWS` section lists the call targets
  pipeline-wide instead, deduped by `(target, relationship)` (matching
  the parser's own dedup precedent) — e.g. `pytorch_lint.yml` has 10
  calling jobs but only 4 distinct `LinkedWorkflow` entries, so a
  specific job cannot be traced back to a specific entry. Nothing is lost
  between the two sections, they're just organized at different levels.
  **Resolved (2026-07-16):** the misleading "0 steps" half of this was
  closed — a job line now reads `job_name — delegates to reusable
  workflow <target>` (sourced from `Job.raw_extras["uses"]`) in place of
  the step-count clause, e.g. `eslint_ci.yml`'s `test_package_manager`.
  This is a deliberate, narrow exception to "raw_extras is never read
  here": only this one pre-existing parser-established key, scoped to
  exactly this fact. `Pipeline.linked_workflows` was considered instead
  but rejected — its `(target, relationship)` dedup has no per-job field
  at all, so it cannot answer "what does *this specific job* call" once
  two jobs call different targets, which is already true across these
  fixtures. The separate `LINKED WORKFLOWS` section and its dedup are
  otherwise unchanged; a job's own line and that section still aren't
  literally 1:1, they're just no longer misleading in isolation.
- **Dependencies never imply success-gating.** `"after X"` in a job line
  states execution order only; it never becomes "only runs if X
  succeeds", even though that's GitHub Actions' real default runtime
  behavior for `needs:`, because that semantic isn't literally encoded in
  the IR's `dependencies` field and isn't guaranteed true for every
  future platform this schema might model. Only an explicit
  `Job.condition` is ever rendered as a gating rule.
- **No step-level detail is surfaced** — only an aggregate step count per
  job. A step-level `Condition` (e.g. `complex_pipeline_ir.json`'s `test`
  job, an `"unparsed"` condition on its "run integration tests" step) is
  present in the parsed `Pipeline` but not projected into this text
  format; this matches `PROJECT_PLAN.md`'s target shape, which has no
  step-level granularity either.
  **Resolved (2026-07-16):** this justification didn't hold up under
  review — `PROJECT_PLAN.md`'s Tool 1 deliverable list normatively
  includes "What each step in each job does", and the no-step-level-
  granularity example elsewhere in that document is illustrative prose,
  not the spec; the deliverable list wins. Each job now also lists its
  steps' `Step.name` (nothing else — no `with_args`/env/raw_extras, no
  step-level `Condition`, still out of scope), capped at 10 with an
  `... and N more steps` overflow line (see `_step_lines`). 10 was chosen
  from real data: 53 of 58 jobs across all 10 fixtures have 10 or fewer
  steps, so the cap shows the vast majority in full while still bounding
  the outliers (`rust_ci.yml`'s `job` has 33, `upload_artifact_test.yml`'s
  `build` has 28) rather than producing a wall of text. The aggregate
  step count in the job line itself is untouched and always reflects the
  true total regardless of the cap.
- **`Pipeline.environment_variables` has no dedicated section**, and
  job-level `Job.environment` names are not surfaced in job lines either
  — out of scope for this slice, not a data-loss concern (the IR still
  has the data; a future revision could add an "ENVIRONMENT" section).
- **PROJECT_PLAN.md's illustrative prose ("checks code style using
  flake8", "deploys to production") is deliberately not reproduced.**
  Fabricating that kind of description from a job name alone would be
  guessing intent this tool has no basis for; this generator only ever
  renders facts the IR actually contains (step counts, matrix shape,
  conditions verbatim/typed, dependency edges, secrets, linked workflows).
- **Cycle fallback**: if a pipeline's job graph were cyclic (a state
  `ir.validate._check_no_circular_dependencies` should already catch and
  which should never legitimately occur), `_topological_job_order` does
  not attempt to detect or report the cycle itself — it silently falls
  back to YAML declaration order. Reporting cycles is `ir.validate`'s
  responsibility; this generator's only obligation is to never crash or
  hang on one. Proven via a hand-written 2-job cycle test, since no real
  fixture has one.
- **A real multi-line `unparsed` condition disrupts the one-line-per-job
  format.** `pytorch_lint.yml`'s `lintrunner-clang`/`lintrunner-pyrefly`
  jobs have a block-scalar `if: |` condition spanning ~10 lines; since
  `Condition.expression` is rendered verbatim (never guessed at), the
  embedded newlines appear directly inside the job line. Faithful to the
  data, not silently truncated, but visually breaks the "one job per
  numbered line" convention for these two real jobs.
- **Step-scoped secrets surface the raw `job.stepindex` `scope_ref`
  convention verbatim**, e.g. `rust_ci.yml` produces "`CACHES_AWS_ACCESS_KEY_ID
  (used in job: job.26)`" rather than a decoded "step 26 of job job" —
  this generator doesn't parse or reinterpret `scope_ref`'s internal
  `f"{job_key}.{step_index}"` format (a parser-side convention documented
  above under `## Environment variables and secrets`), it only ever
  displays it as-is.
  **Resolved (2026-07-16):** `_secret_line` now decodes this — a STEP-
  scope `scope_ref` is split on `.` into `(job_key, step_index)` (safe
  per the job-key-can't-contain-`.` guarantee already noted above) and
  resolved to the real step name via a `jobs_by_name` lookup, e.g.
  `rust_ci.yml` now reads "`CACHES_AWS_ACCESS_KEY_ID (used in job: job,
  step: run the build)`". Branches explicitly on `secret.scope` (PIPELINE
  / JOB / STEP) rather than inferring shape from the string, so PIPELINE
  (no `scope_ref` at all) and JOB (`scope_ref` is already just the job
  key) render exactly as before — only the STEP case changed. An
  unresolvable `scope_ref` (shouldn't occur against real parser output)
  falls back to the job-only reference rather than crashing.

## Mermaid generator

`generators/mermaid_generator.py`'s `generate_mermaid()` shares its
topological-order, matrix-summary, and condition-phrase logic with
`text_generator.py` via a new `generators/common.py` (a pure relocation of
`_topological_job_order`/`_matrix_summary`/`_condition_phrase`, no logic
changes — both generators' existing tests pass unmodified). Verified
against all 10 real fixtures plus the 3 Phase 2 ground-truth fixtures,
including an actual render through `@mermaid-js/mermaid-cli` (not just a
no-raise check) for the complex ground-truth fixture and the 14-job
`pytorch_lint.yml` fan-out/fan-in graph.

- **Matrix jobs render as a single annotated node, never fanned out into
  one node per combination** — the same approximation `text_generator`
  makes (reusing `_matrix_summary` directly), for the same reason:
  resolving concrete matrix combinations is a deferred downstream concern
  (see `## Matrix strategy` above), not something either generator
  attempts.
- **`Pipeline.secrets`, `Pipeline.environment_variables`, and
  `Pipeline.linked_workflows` are out of scope for this diagram**, by
  design — it's specifically the job dependency graph.
  `LinkedWorkflow` in particular has no per-job attribution after the
  parser's `(target, relationship)` dedup (`pytorch_lint.yml`'s 10 calling
  jobs collapse to 4 entries), so it couldn't be placed accurately on the
  graph even if it were in scope. All three stay `text_generator`-only.
- **Node labels carry only name + compact annotations** (matrix/condition/
  `allow_failure`) — no step count, runner, or artifact detail, unlike
  `text_generator`'s job lines. Kept deliberately terse so larger graphs
  (e.g. `pytorch_lint.yml`'s 14 jobs) stay readable.
- **Trigger nodes use `trigger_<index>` IDs** (0-based position in
  `pipeline.triggers`), not a `TriggerType`-derived ID — a pipeline can
  have multiple triggers of the same type (e.g. several `schedule:`
  entries, one per cron string), which would otherwise collide on a
  type-derived ID. This makes a collision with any `Job.name` structurally
  impossible rather than merely unlikely, since no real job key in any
  fixture takes this form.
- **An "entry" job** (one that gets an edge from every trigger node) is
  defined as a job with no dependency that resolves to a real job in this
  pipeline — either `dependencies` is empty, or every listed dependency is
  dangling. This mirrors `_topological_job_order`'s own dangling-dependency
  skip, so a job whose only `needs:` reference doesn't exist still gets at
  least one incoming edge instead of floating disconnected in the diagram.
  Verified with a hand-written case, since no real fixture has a dangling
  dependency.
- **Label escaping is a new concern this generator has that
  `text_generator` doesn't** (plain text has no equivalent syntax risk):
  literal `"` becomes `#quot;`, and literal newlines become `<br/>`. The
  newline case is real, not hypothetical — `pytorch_lint.yml`'s
  `lintrunner-clang`/`lintrunner-pyrefly` jobs have the same ~10-line
  block-scalar `if: |` condition noted above under `## Text generator`,
  and it falls through to `_condition_phrase`'s verbatim-expression
  fallback here too. Converting (not stripping) the newlines keeps the
  "never silently drop content" rule intact while staying valid Mermaid
  syntax — confirmed by actually rendering this fixture's diagram through
  `mermaid-cli` rather than just checking it doesn't raise.
- **A job condition's diagram annotation is truncated past 80 characters
  (or at its first line, if multi-line), added 2026-07-16.** Before this,
  a long/multiline `Job.condition` was embedded into the node label
  verbatim (via `_escape_label`'s newline-to-`<br/>` conversion above),
  which for `pytorch_lint.yml`'s `lintrunner-clang`/`lintrunner-pyrefly`
  jobs — a ~12-line block-scalar `if:`, 786/236 chars once rendered —
  produced an enormous node that dominated the graph. `_condition_annotation`
  now renders the condition's first line (if multiline) or the first 80
  chars (if a single long line, real in `pr-sanity-checks`'s 161-char
  condition), plus an ellipsis, for exactly this diagram annotation. 80
  was chosen from real data: of 19 real job-level conditions across all
  10 fixtures, 16 are 75 chars or fewer and single-line, and exactly 3
  are not (the two above plus `pr-sanity-checks`) — 80 is the natural cut
  point between the two groups, not an arbitrary round number. This is a
  diagram-only, deliberately lossy trade-off: `text_generator.generate_text()`
  is untouched and still renders `Condition.expression` verbatim in the
  same document's text section (see `## Text generator`'s "A real
  multi-line `unparsed` condition..." bullet above), so "never silently
  drop content" holds at the document level even though this one
  annotation does not show the full expression.

## Tool 1 (`tool1/single_pipeline.py`)

`generate_documentation()`/`document_pipeline()`/`check_pipeline()` are a
purely structural layer on top of `text_generator`/`mermaid_generator` —
both generators' output is embedded verbatim, never reformatted or
reinterpreted, and neither generator module was modified to build this.
Verified against all 10 real fixtures (written via `document_pipeline()`,
each embedded diagram actually rendered through `mermaid-cli` to a real
SVG, not just checked for no-raise) plus a ground-truth fixture for exact
fence-content assertions.

- **The "Pipeline Diagram" section is an `## ` (H2) Markdown heading**, a
  small resolved ambiguity: no other part of the spec this was built
  against says so explicitly, but nothing else about the file (a `#`
  top-level heading, fenced code blocks) makes sense as anything other
  than real Markdown, so treating it as a heading rather than a bare line
  is the consistent reading.
- **`check_pipeline()`'s comparison is exact string equality**, not
  whitespace-tolerant or fuzzy — deliberate, since both generators are
  fully deterministic pure functions with no LLM in the loop yet (Phase
  5). This will need revisiting once Phase 5 puts non-deterministic LLM
  prose into the document; exact-match drift detection stops being the
  right check at that point.
- **Only `GitHubActionsParser` is wired in** — `document_pipeline()`/
  `check_pipeline()` have no platform-dispatch logic, matching every other
  module's current GitHub-Actions-only scope (Phase 9 is where multi-platform
  dispatch would be added, not here).
- **Parse/generation failures surface as a single one-line `stderr`
  message via `cli.py`'s `except Exception`**, not a typed error hierarchy
  — deliberately minimal per this slice's scope; a missing file, a YAML
  syntax error, and a validation failure are all reported the same
  generic way for now.

## Consciously unmodeled concepts — verified preservation status

Six GitHub Actions concepts with no dedicated IR schema field were audited
against all 10 real fixtures: for each, whether any fixture actually uses
it, and — by directly parsing the fixture and inspecting the resulting
`Pipeline`/`Job` objects, not by assuming — whether it's preserved
somewhere (`raw_extras`, or a dedicated raw-fallback field like
`Trigger.raw`) or silently dropped. `parsers/base.py`'s `BaseParser`
contract requires the latter never happen; this audit found it does.

**Root cause, confirmed by an exhaustive grep of every `raw_extras[...]`/
`raw_extras.update(...)` write site in `parsers/github_actions.py`:**
`GitHubActionsParser.parse()`'s final `Pipeline(...)` construction never
passes a `raw_extras=` argument at all. `Pipeline.raw_extras` is
therefore unconditionally `{}` on every parse, regardless of what
workflow-level YAML exists — meaning **no workflow-level concept can
currently be preserved by this parser**, not just the ones checked here.
At job level, `_parse_jobs` only ever writes `display_name`,
`continue_on_error_expression`, the matrix-extras keys, and
reusable-workflow-call `uses`/`with`/`secrets` into `Job.raw_extras` —
nothing else. This is a genuine gap against this file's own stated
"nothing is silently dropped" convention, not a false alarm from a
grep-based check — every finding below was confirmed by actually running
`GitHubActionsParser().parse()` and printing the resulting `raw_extras`.
**Not fixed in this pass** — flagged for discussion (tracked in
`BUILD_PLAN.md` Section 6), since wiring `Pipeline.raw_extras` up is a
parser change warranting its own review, not something to do inline
during a verification pass.

**Resolved (2026-07-15): `Pipeline.raw_extras` is now wired up.**
`GitHubActionsParser.parse()` now passes `raw_extras=_parse_pipeline_raw_extras(data)`
to the `Pipeline(...)` construction, and `_parse_jobs` captures the 4
job-level keys below alongside its existing `display_name`/
`continue_on_error_expression`/matrix-extras/`uses`-`with`-`secrets`
keys — same presence-checked, verbatim-preservation pattern throughout,
no guessing. Covered by a new dedicated test file,
`tests/test_github_actions_raw_extras.py`. Confirmed via
`scripts/update_golden_files.py` that this has zero effect on any
generated `.md` output (`git diff tests/golden/` is empty) — neither
generator reads `raw_extras`.

**`permissions:` (workflow-level and job-level `GITHUB_TOKEN` scope
restrictions) — its own paragraph, deliberately, because it's
security-relevant.** This project's motivating citation, Bajpai & Lewis
(2022), is specifically about undocumented CI/CD pipelines creating real
security risk because developers can't see what their own pipelines are
doing — token permission scope is exactly that kind of fact. Real usage
is not rare: **8 of 10 fixtures** declare workflow-level `permissions:`
(`eslint_ci.yml`, `fastapi_test.yml`, `flask_tests.yml`,
`node_test_linux.yml`, `pandas_unit_tests.yml`, `pytorch_lint.yml`,
`rust_ci.yml`, `upload_artifact_test.yml`), in three distinct shapes — a
mapping (`{contents: read}`), an explicit empty mapping (`{}`, i.e. "no
permissions granted"), and a bare string (`pytorch_lint.yml`'s
`permissions: read-all`). Job-level `permissions:` also occurs for real,
in 2 fixtures (`fastapi_test.yml`'s `changes` job; all 8 jobs in
`pandas_unit_tests.yml` — 9 job-level occurrences total). Confirmed
directly: `Pipeline.raw_extras == {}` after parsing every one of these,
and every affected job's `raw_extras` is likewise empty of any
`permissions` key. **The honest framing is that this fact is currently
not preserved anywhere, not merely "unmodeled but safely retained"** —
this tool does not yet make token-scope information available at all,
structured or raw. That's a real limitation worth naming plainly rather
than a claim that the tool "handles" a security-relevant concern; it
doesn't, yet, even at the raw-preservation level.
**Resolved (2026-07-15):** both workflow- and job-level `permissions:`
are now preserved verbatim in `raw_extras` (all three shapes — mapping,
empty mapping, bare string), tested against `rust_ci.yml`,
`pytorch_lint.yml`, `flask_tests.yml`, and `fastapi_test.yml`'s `changes`
job in `tests/test_github_actions_raw_extras.py`. Preserved is not the
same as surfaced — this data still isn't rendered anywhere in
`generators/text_generator.py`/`generators/mermaid_generator.py`'s
output, which remains a separate, later decision (do trigger
permissions/token-scope facts belong in the human-readable summary, and
if so how) — but the raw fact is no longer lost at the parser layer.

- **`Job.outputs`** (a job's `outputs:` block — the producing side of the
  `needs.<job>.outputs.*` pattern already noted above as unparsed on the
  consuming/`if:`-condition side). Real in 2 of 10 fixtures:
  `fastapi_test.yml`'s `changes` job (`outputs: {src: ...}`) and
  `rust_ci.yml`'s `calculate_matrix` job (`outputs: {jobs: ..., run_type:
  ...}`). Confirmed dropped: neither job's `raw_extras` contains an
  `outputs` key. **Resolved (2026-07-15):** now preserved verbatim under
  `Job.raw_extras["outputs"]` for both jobs, tested in
  `tests/test_github_actions_raw_extras.py`.
- **`concurrency:`** (workflow-level and job-level). Workflow-level is
  real in 4 of 10 fixtures (`flask_tests.yml`, `node_test_linux.yml`,
  `pytorch_lint.yml`, `rust_ci.yml`). Job-level is real in 1 fixture
  (`pandas_unit_tests.yml` — all 8 of its jobs declare their own
  `concurrency:` group, not just a subset). Confirmed dropped at both
  levels — same `Pipeline.raw_extras == {}` root cause for the
  workflow-level case; the affected jobs' `raw_extras` show no
  `concurrency` key. **Resolved (2026-07-15):** now preserved verbatim at
  both levels (`Pipeline.raw_extras["concurrency"]` /
  `Job.raw_extras["concurrency"]`), tested against `flask_tests.yml`
  (workflow-level) and `pandas_unit_tests.yml` (job-level).
- **Deployment `environment:`** (the GH protection-rules kind on a job,
  e.g. `environment: production` — a different concept from this
  schema's `Job.environment`, which maps GH Actions' `env:` key to
  environment *variables*; not to be confused with each other). Real in
  exactly 1 of 10 fixtures: `rust_ci.yml`'s `job` and `outcome` jobs, both
  as a dynamic `${{ ... }}` expression rather than a literal environment
  name. Confirmed dropped: neither job's `raw_extras` contains an
  `environment` key. Two false positives worth recording since they
  looked real on an initial text search: `pandas_unit_tests.yml` has a
  matrix axis literally *named* `environment` (pixi environment
  selection, e.g. `py311`/`py312`) and several `with:` action-input
  parameters named `environment`; `setup_python_test.yml` has an
  unrelated `update-environment:` action input. None of these are the
  deployment-`environment:` concept — confirmed by checking each hit's
  actual YAML structure, not just the matched text. **Resolved
  (2026-07-15):** now preserved verbatim under a deliberately
  distinctly-named `Job.raw_extras["deployment_environment"]` key — never
  `"environment"`, so it can't be confused with `Job.environment` (env
  vars) by anyone reading `raw_extras` later. Tested against both
  `rust_ci.yml` jobs, including an explicit assertion that `job`'s real
  `Job.environment` env vars (`CI_JOB_NAME` etc.) and its
  `deployment_environment` raw_extras entry are both present and neither
  clobbers the other.
- **`defaults:`** (workflow-level and job-level, e.g. `defaults: {run:
  {shell: bash}}`). Workflow-level is real in 2 of 10 fixtures
  (`pandas_unit_tests.yml`, `rust_ci.yml`, both a `run.shell` default).
  Job-level `defaults:` does not appear in any fixture — checked
  structurally across all 10, zero hits; untested against real data.
  Workflow-level usage is confirmed dropped (`Pipeline.raw_extras ==
  {}`). **Resolved (2026-07-15):** workflow-level `defaults:` is now
  preserved verbatim in `Pipeline.raw_extras["defaults"]`, tested against
  `rust_ci.yml`. Job-level `defaults:` was deliberately left unhandled —
  no fixture exercises it, and it wasn't in this fix's concrete scope;
  still untested against real data, same as before.
- **Trigger `types:` activity filter — the one concept in this audit that
  actually is preserved**, and the exception to everything above: real in
  1 of 10 fixtures (`node_test_linux.yml`'s `pull_request: {types:
  [opened, synchronize, reopened, ready_for_review]}`), and already
  documented earlier in this file's Triggers section as living in
  `Trigger.raw` (a dedicated schema fallback field designed for exactly
  this, distinct from the `raw_extras` catch-all) rather than dropped.
  Confirmed still accurate, and already covered by a passing regression
  test — `tests/test_github_actions_triggers.py::test_node_paths_ignore_and_dropped_types_filter_stays_in_raw`
  — so no new test was needed for this audit. One false positive worth
  recording: `eslint_ci.yml` matched an initial text search for `types:`
  but has no trigger-activity-filter usage at all — the hits were a job
  key named `test_types` and `npm run test:types:5.3`-style script names
  inside `run:` commands.
