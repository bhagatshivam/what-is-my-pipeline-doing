# Multi-workflow fixture sources (Tool 2 / Phase 6)

The `.yml`/`.yaml` files under this directory are unmodified, real-world
GitHub Actions workflow files pulled from public open-source repositories,
used here as test fixtures under their original licenses — same standard
as `tests/fixtures/SOURCES.md` and `evaluation/held_out_workflows/SOURCES.md`.
Selected in chat, approved before anything was fetched (see `BUILD_PLAN.md`'s
Phase 6 follow-up changelog entries).

Each license below was confirmed by fetching the source repository's
actual `LICENSE`/`LICENSE.md` file directly (not assumed from reputation).

Commit SHAs were captured via `git ls-remote <repo> HEAD`, run moments
after each repo's files were fetched from the branch-tip path
`raw.githubusercontent.com/<repo>/<branch>/...` (not a SHA-pinned path).
The two calls were not atomic, so each SHA should be read as "the branch
tip at fetch time," not as a guarantee that the SHA's tree byte-for-byte
matches the fetched content. All three were re-verified unchanged during
PR review. This is stronger than `evaluation/held_out_workflows/SOURCES.md`'s
SHAs, which have no fetch-time correlation at all, but "exact" overstated
it.

## `black/` — psf/black

**Repo:** https://github.com/psf/black · **Licence:** MIT (confirmed from
`LICENSE`) · **Commit SHA:** `8960ab0457803c310bf2f3550e1d96c598ca8f70`
(default branch `main`, captured via `git ls-remote`) · **Date fetched:**
2026-07-23

**Curated subset, not the whole repo, and why:** `psf/black`'s real
`.github/workflows/` folder has 13 files. Importing all 13 would produce
an unreadable unified diagram — most of those files are unrelated to the
one genuine cross-file relationship this fixture exists to exercise. Only
3 of the 13 real files are included here, chosen specifically because two
of them form a real `workflow_run` chain (the reason this repo was
selected at all) and the third adds one more independent trigger for
variety without adding much size:

| File | Original path | URL fetched from |
|---|---|---|
| `diff_shades.yml` | `.github/workflows/diff_shades.yml` | https://raw.githubusercontent.com/psf/black/main/.github/workflows/diff_shades.yml |
| `diff_shades_comment.yml` | `.github/workflows/diff_shades_comment.yml` | https://raw.githubusercontent.com/psf/black/main/.github/workflows/diff_shades_comment.yml |
| `lint.yml` | `.github/workflows/lint.yml` | https://raw.githubusercontent.com/psf/black/main/.github/workflows/lint.yml |

**The genuine cross-file relationship:** `diff_shades_comment.yml`'s
`on: workflow_run: workflows: [diff-shades]` names `diff_shades.yml`'s own
`name: diff-shades` exactly — a real `triggered_by` relationship, verified
by reading both files' raw content before fetching, not assumed. This is
the fixture that exercises `Pipeline.linked_workflows` and the
origin-scoped Mermaid trigger-wiring fix (`ir/schema.py`'s `Trigger.origin`/
`Job.origin`, `generators/mermaid_generator.py`'s trigger-wiring loop)
against real data for the first time — confirmed correct:
`generate_mermaid()`'s `trigger_2` node (the `workflow_run` trigger,
belonging to `diff_shades_comment.yml`) wires only to
`diff_shades_comment_yml__comment`, never to any `diff_shades.yml` or
`lint.yml` job.

**Overlap note (nominal, not a real duplication concern):** `psf/black`
shares the umbrella `psf` GitHub org with `evaluation/held_out_workflows/`'s
`psf/requests`, but the two repos have different maintainers and unrelated
CI conventions in practice — PSF hosts many independently-run projects
under one org. Not the same kind of overlap as would come from reusing the
same repo, or a repo from the same tight-knit author/team.

## `tox/` — tox-dev/tox

**Repo:** https://github.com/tox-dev/tox · **Licence:** MIT (confirmed
from `LICENSE`) · **Commit SHA:** `69e1bdcdaee13f46041d9680970f791cec72258b`
(default branch `main`) · **Date fetched:** 2026-07-23

Whole real folder, unmodified — only 4 files, no curation needed:

| File | Original path | URL fetched from |
|---|---|---|
| `check.yaml` | `.github/workflows/check.yaml` | https://raw.githubusercontent.com/tox-dev/tox/main/.github/workflows/check.yaml |
| `release.yaml` | `.github/workflows/release.yaml` | https://raw.githubusercontent.com/tox-dev/tox/main/.github/workflows/release.yaml |
| `prepare-release.yaml` | `.github/workflows/prepare-release.yaml` | https://raw.githubusercontent.com/tox-dev/tox/main/.github/workflows/prepare-release.yaml |
| `update-schemastore.yaml` | `.github/workflows/update-schemastore.yaml` | https://raw.githubusercontent.com/tox-dev/tox/main/.github/workflows/update-schemastore.yaml |

**No cross-file relationship** — all 4 trigger independently (manual
dispatch/push/schedule, tag push, manual dispatch with inputs, tag push).
Deliberately selected as the "N real files, nothing links them" contrast
to `black/`'s chain. `tox-dev` has no relationship, direct or
organizational, to any repo already used anywhere in this project.

## `starlette/` — encode/starlette

**Repo:** https://github.com/encode/starlette · **Licence:** BSD-3-Clause
(confirmed from `LICENSE.md`) · **Commit SHA:**
`5174d4c8358a6f06aa8056bafd14c2272dab8dd1` (default branch `master`) ·
**Date fetched:** 2026-07-23

Whole real folder, unmodified — only 3 files, no curation needed:

| File | Original path | URL fetched from |
|---|---|---|
| `main.yml` | `.github/workflows/main.yml` | https://raw.githubusercontent.com/encode/starlette/master/.github/workflows/main.yml |
| `publish.yml` | `.github/workflows/publish.yml` | https://raw.githubusercontent.com/encode/starlette/master/.github/workflows/publish.yml |
| `zizmor.yml` | `.github/workflows/zizmor.yml` | https://raw.githubusercontent.com/encode/starlette/master/.github/workflows/zizmor.yml |

**No cross-file relationship** — `main.yml` (push/PR to `main`),
`publish.yml` (tag push), and `zizmor.yml` all trigger independently.
Adds BSD-3-Clause licence coverage (the existing `tests/fixtures/`/
`evaluation/held_out_workflows/` sets are otherwise MIT / BSD-3-Clause /
MIT+Apache-2.0, all already represented, but a second BSD-3-Clause example
alongside a second no-relationship contrast was judged worth the low
marginal cost given the folder is only 3 files).

**Overlap note:** `encode/starlette` shares its `encode` org with
`evaluation/held_out_workflows/`'s `encode/httpx` — a real, if small,
codebase/author-convention overlap (a tighter-knit org than `psf`'s),
named here rather than left implicit.
