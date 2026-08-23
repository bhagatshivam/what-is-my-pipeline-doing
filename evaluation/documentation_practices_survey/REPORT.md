# CI Documentation Practices in Open-Source: A Small Survey

**This is background research for the dissertation's Introduction, not an
evaluation of this project's own tool.** It addresses the original project
brief's explicit deliverable: *"A survey of the kind of documentation
currently written for CI pipelines in open source code bases, and its
update frequency."* It is not Tier 1, 2, 3, or 4 of `EVALUATION_PLAN.md` —
see that document for the actual evaluation of the CI Pipeline Documentation
Tool itself. Nothing here scores, tests, or judges this project's own
output; it looks only at how other real projects document (or don't
document) their own CI.

## Method

Reuses the 11 repos already investigated during Tier 3's natural-pairs work
(`evaluation/tier3_natural_pairs/REPORT.md` and its investigation history)
rather than searching for new ones — both the 3 repos that turned out to
have genuine, current CI documentation, and the 8 that didn't, since the
ruled-out cases are the more informative half of this particular question.
For each repo, the already-identified README/CONTRIBUTING/docs page and the
already-identified workflow YAML file(s) were checked via `git log` against
a fresh, read-only, blobless partial clone (`git clone --filter=blob:none
--no-checkout`) of the real upstream repository — real commit history, no
file content downloaded, nothing pushed or modified anywhere.

**11 repos, not ~12.** `cpython_reusable_macos` is excluded: its "the real
docs describe a different, retired CI system (buildbot)" finding was a
prior observation relayed at the start of Tier 3's investigation, not
something independently verified with a citation in this project's own
work, so it isn't included here as a sourced data point.

## Findings

| Repo | Category | Doc last updated | Workflow last updated | Gap (workflow − doc) |
|---|---|---|---|---|
| `vscode_pr` (microsoft/vscode) | No CI documentation found (`CONTRIBUTING.md`/`README.md`) | 2026-05-21 | 2026-08-10 | +81d |
| `scipy_linux` (scipy/scipy) | Detailed and current | 2026-08-03 | 2026-08-20 | +17d |
| `urllib3_ci` (urllib3/urllib3) | Vague one-liner | 2026-04-29 | 2026-08-04 | +97d |
| `requests_lint` (psf/requests) | Vague one-liner | 2026-05-07 | 2026-07-27 | +81d |
| `celery_python_package` (celery/celery) | Detailed but describes a retired CI system (Travis/AppVeyor) | 2026-02-23 | 2026-07-20 | +147d |
| `httpie_code_style` (httpie/cli) | Vague one-liner | 2023-08-06 | 2022-06-09 | −423d |
| `httpx_test_suite` (encode/httpx) | Detailed but outdated shape (doc drift — confirmed in Tier 3) | 2024-11-12 | 2025-10-04 | +326d |
| `nextjs_build_and_test` (vercel/next.js) | Detailed but describes different workflow files | 2026-06-04 | 2026-08-20 | +77d |
| `black` diff-shades (psf/black) | Detailed and current | 2026-01-15 | 2026-08-03 | +200d |
| `tox` (tox-dev/tox) | Detailed and current | 2026-08-23 | 2026-08-21 | −2d |
| `starlette` (encode/starlette) | Vague one-liner | 2026-05-01 | 2026-08-02 | +93d |

Only **3 of 11** (scipy, black, tox) had CI documentation both detailed
enough to be useful and confirmed, independently, to still match current
behavior — and that confirmation came from Tier 3's own comparison work, not
from this table alone. **1 of 11** has no CI documentation at all. **5 of
11** acknowledge CI exists in one vague sentence with no operational
detail — no trigger, no job, no "when does this actually run." **2 of 11**
have documentation that is detailed and confident, but wrong: one describing
a CI system the project no longer runs, one describing a shape of the
current system that has since changed underneath it.

### Two concrete examples

**`httpie_code_style` (httpie/cli) — old on both sides.** The CONTRIBUTING.md
mention of CI ("GitHub Actions will automatically run HTTPie's test suite
against your code") was last touched 2023-08-06; the actual
`code-style.yml` workflow it's nominally describing was last touched
2022-06-09 — over three years stale relative to today on both sides. The
gap is *negative* (the doc is technically newer than the workflow), which
is a useful reminder that a gap's sign alone doesn't tell you which side is
the stale one — here, both are old, and the doc was never more than a
one-line acknowledgment to begin with, so there was little for the workflow
to drift away from.

**`tox` (tox-dev/tox) — the positive counterexample, and how fragile it
is.** `docs/development.rst`'s "Automated testing"/"Creating a new release"
sections — the ones Tier 3 confirmed accurately describe `check.yaml`,
`prepare-release.yaml`, and `release.yaml` in exact structural detail,
including exact job names and input choice lists — were last touched
**the same day this data was gathered** (2026-08-23, a real, unrelated
upstream commit: *"docs: drop the claim that tox -e py skips tests with
missing dependencies"*). This is the one repo in the sample where the doc
is newer than the workflow it describes. It's also a coincidence of
timing, not a stable property of the project — the doc could just as
easily have gone eight months without a touch, the way black's did, and
this survey would have caught it at a different point in that cycle. A
"currently accurate" doc in this sample is a snapshot of a moving target,
not a guarantee.

## Synthesis

Across 11 real repos, only 3 had CI documentation that was both detailed
and currently accurate (and one of those, `tox`, only stayed current
because it happened to be edited the same day this data was gathered — a
coincidence, not a stable state). One repo has no CI documentation at all.
Five have only vague, one-line acknowledgments that CI exists, with no
operational detail. Two have documentation that's detailed but wrong — one
describing a CI system the project no longer uses, one describing a shape
of the current system that's since changed underneath it. The gap sizes
themselves (77–326 days between a doc's last edit and its subject
workflow's) suggest documentation and pipeline configuration are maintained
on independent, uncoordinated schedules in practice, not gaps introduced by
neglect alone — plausibly because keeping them in sync requires a human to
remember to do it every time either one changes, which this sample suggests
doesn't reliably happen even in well-maintained projects (scipy, black, tox
are all actively developed, not abandoned). This motivates the tool's core
premise directly: the cost and reliability of keeping documentation current
changes categorically once generation is automatic. Regenerating
documentation from the workflow file is a cheap, deterministic operation
with no risk of introducing new inaccuracy, whereas every stale or vague
case in this sample required a human to notice a change, remember to
update the doc, and describe it correctly — three independent points of
failure that, per this sample, don't reliably all succeed even in
actively-maintained projects.

This synthesis should be read with its own limits in view: 11 repos is
illustrative, not a rigorous sample — no random selection, drawn from
repos already in this project's fixture set for reasons unrelated to this
question. "3 of 11 detailed and current" could be read as "a 27% success
rate isn't catastrophic" just as easily as "a 73% failure rate is the
norm" — both readings are available from the same table, and this note
doesn't pick the more dramatic one as if it were the only honest
conclusion.
