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
