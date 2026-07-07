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

Deliberately deferred this pass, each with a dedicated `Step` field already
in the schema waiting for a specific future pass: `env:` (step env vars —
"env/secrets" pass), `if:` (step conditions — "if conditions" pass),
`continue-on-error:` (bundled into the env/secrets pass since it's a small
structural addition alongside it). None of these are stored anywhere yet,
including `raw_extras` — they have a promised home, so there's no data-loss
risk in leaving them for those passes to fill in directly from the YAML.

- **`StepType.SCRIPT` is never produced by this parser.** GH Actions has no
  distinct YAML construct for "external script reference" vs. an inline
  command — `run: ./deploy.sh` is syntactically identical to `run: npm
  test`. Every `run:` step maps to `StepType.COMMAND`; `SCRIPT` exists in
  the IR for platforms that do distinguish the two (e.g. a dedicated
  `script:` file reference) and may go entirely unused by this parser.
- **Name-fallback heuristic when `name:` is absent** (37 of 299 steps
  across the 10 fixtures — not rare). `uses:` steps fall back to the action
  ref itself; `run:` steps fall back to the first non-empty line, truncated
  to ~60 chars. This is a parser design choice that can affect the
  *readability* of generated documentation (a truncated first line is a
  weaker step label than a hand-written name), not a silent data-loss
  concern — the original `run:`/`uses:` value is always intact in
  `Step.value` regardless of what name was derived.
- **`shell:` and `working-directory:`** (33 and 4 occurrences respectively)
  have no dedicated `Step` field and no pass currently scheduled to add
  one, unlike env/if/continue-on-error above — preserved in
  `Step.raw_extras["shell"]` / `["working-directory"]` rather than dropped.
- **A step with neither `uses:` nor `run:`.** Not valid GH Actions syntax
  as far as we've seen (0 of 299 steps) — the whole step body is preserved
  in `Step.raw_extras["unrecognized_step"]` and `StepType.COMMAND` is used
  as a neutral placeholder type, rather than raising or guessing. Untested
  against real-world data.
- **A non-dict entry inside `steps:`.** Same treatment as above — not seen
  in any current fixture, defensive only.
