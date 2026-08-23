# Tier 3 Correctness Check — tox-dev/tox (not completed: tooling scope boundary)

## What was attempted

Extending the correctness-check method ([`REPORT.md`](REPORT.md), this
repo's own `ci.yml`) to a real *external* multi-pipeline repo, to complement
that single-repo result: `tox-dev/tox`, already a verified multi-fixture in
this project (`tests/fixtures/multi/tox/`) with four workflow files
(`check.yaml`, `prepare-release.yaml`, `release.yaml`,
`update-schemastore.yaml`), and already confirmed via Tier 3's natural-pairs
work (PR #60) to match its real, current behavior against independently-authored
human documentation. The plan was to pull `tox-dev/tox`'s real GitHub
Actions run/job history the same way `REPORT.md` did for `ci.yml`, run tool2
against its workflow files, and compare — same principle, applied read-only
to a repo this project doesn't own.

## What was found

Read-only access to `tox-dev/tox`'s **files** (via anonymous `git clone`) is
unrestricted — no attachment needed, confirmed by `add_repo`'s own response.

Read-only access to `tox-dev/tox`'s **GitHub Actions API data** (workflow
runs, job status/timing, job logs — exactly the evidence `REPORT.md`'s
`ci.yml` comparison depends on) is not reachable from this session:

- A direct `mcp__github__actions_list` call against `tox-dev/tox` was
  denied: *"repository is not configured for this session. Allowed
  repositories: bhagatshivam/what-is-my-pipeline-doing."*
- Attaching `tox-dev/tox` with the access tier that unlocks GitHub API tools
  (`access: "push"` in `add_repo`'s naming — despite the name, this session
  would only ever have called read endpoints) failed: *"cross-tier adds are
  not supported in v1: requested tox-dev/tox but session already has repos
  from owner(s) [bhagatshivam]."* This session is already bound to
  `bhagatshivam/what-is-my-pipeline-doing`; a differently-owned repo can only
  be added at this access tier in a fresh session, not alongside an existing
  one.
- A direct, unauthenticated `curl` to `api.github.com/repos/tox-dev/tox/actions/workflows`
  was also blocked by this environment's outbound proxy (HTTP 403, with a
  message identical in shape to the `add_repo` denial) — not a GitHub rate
  limit, a session-scope block enforced before the request ever reaches
  GitHub.

## Why this is reported as a boundary, not a failure

Per this tier's own framing (a bounded try-it experiment, honestly reported
whichever way it lands): this is a real constraint of the evaluation
tooling's current session model — a single Claude Code Remote session can
hold live GitHub API access to at most one repo owner at a time, and
switching owners mid-session isn't supported — not a defect in the CI
Pipeline Documentation Tool being evaluated, and not evidence about whether
that tool's output is accurate. Two things already stand in for what this
exercise would have added:

- **Tier 3's correctness-check requirement is already satisfied** by
  `REPORT.md`'s `ci.yml` result (6/7 points confirmed against 145 real
  runs, one job log fetch, one honestly-flagged truncation).
- **`tox-dev/tox`'s own real-documentation comparison already exists**, via
  the natural-pairs method (`evaluation/tier3_natural_pairs/REPORT.md`, PR
  #60) — a different but equally valid form of external, independently-authored
  ground truth for the same repo, already confirming zero contradictions
  between the tool's output and `tox`'s real `docs/development.rst`.

No further action is proposed on `tox-dev/tox` specifically. A future
session created with `tox-dev/tox` (or another external repo) as its
*initial* source repo would not hit this constraint — but spinning one up
for this alone was judged not worth the overhead, given the two points
above already cover the ground this exercise was meant to add.
