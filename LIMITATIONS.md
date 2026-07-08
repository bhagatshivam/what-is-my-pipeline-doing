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
  unresolved — matrix parsing isn't implemented yet (a later Phase 3 pass),
  which will need to reconcile `Job.runner` against the job's `matrix` once
  it lands. This is the *majority* shape across the 10 fixtures, not an edge
  case (e.g. every job in `tests/fixtures/setup_python_test.yml`).
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
  otherwise interpreted or evaluated.

## Steps (`steps:`)

`env:` and `continue-on-error:` (deferred when this section was first
written) are now implemented — see `## Environment variables and secrets`
and `## continue-on-error` below. `if:` (step conditions) remains
deliberately deferred to a future "if conditions" pass; `Step.condition`
stays at its dataclass default (`None`) for now — nothing is stored
anywhere yet for it, but it has a promised home (`Condition`) so there's no
data-loss risk in leaving it for that pass to fill in directly from the
YAML.

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
  one, unlike env/continue-on-error (now implemented) or `if:` (still
  deferred but has a promised field) — preserved in
  `Step.raw_extras["shell"]` / `["working-directory"]` rather than dropped.
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
- **Secrets referenced inside `if:` condition expressions aren't scanned.**
  `if:` parsing itself is a separate, not-yet-implemented pass (see
  `## Steps` above). Checked directly: none of the 8 real
  `${{ secrets.X }}` references found across the 10 fixtures fall inside
  an `if:` line — a real gap for future data, not a currently-observed one.

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
