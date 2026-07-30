# Held-out evaluation set sources

The `.yml` files in this directory are unmodified, real-world CI config
files pulled from public open-source repositories — the **held-out
evaluation set** for Phase 4.5 Item 5 (Round 2) plus its Phase 7 Step 1
expansion (4 more fixtures, added ahead of Tier 4 to close out the
held-out-expansion decision before any Tier 4 output is generated).
Unlike `tests/fixtures/`, these are never used to develop or tune the
parser: their manifests (`.manifest.yml` siblings) were authored by
reading this raw YAML by hand, before the parser/generators were ever run
against them, and the set exists specifically to provide independent,
non-circular ground truth for scoring this project's actual output. None
of these 10 repos overlap with `tests/fixtures/`'s existing 10
(`actions/checkout`, `pallets/flask`, `nodejs/node`, `eslint/eslint`,
`fastapi/fastapi`, `rust-lang/rust`, `pytorch/pytorch`,
`actions/upload-artifact`, `pandas-dev/pandas`, `actions/setup-python`),
`tests/fixtures/multi/`'s (`psf`, `tox-dev`, `encode`), or each other
(`psf`, `httpie`, `encode`, `urllib3`, `celery`, `scipy`, `pre-commit`,
`python`, `vercel`, `microsoft`) — reconfirmed by inspection for this
expansion.

Each license below was confirmed by fetching the source repository's actual
`LICENSE`/`LICENSE.txt`/`LICENSE.md` file directly (not assumed from the
project's reputation).

| Fixture | Source repo | Original path | URL fetched from | License | Date fetched |
|---|---|---|---|---|---|
| `requests_lint.yml` | psf/requests | `.github/workflows/lint.yml` | https://raw.githubusercontent.com/psf/requests/main/.github/workflows/lint.yml | Apache-2.0 | 2026-07-22 |
| `httpie_code_style.yml` | httpie/cli | `.github/workflows/code-style.yml` | https://raw.githubusercontent.com/httpie/cli/master/.github/workflows/code-style.yml | BSD-3-Clause | 2026-07-22 |
| `httpx_test_suite.yml` | encode/httpx | `.github/workflows/test-suite.yml` | https://raw.githubusercontent.com/encode/httpx/master/.github/workflows/test-suite.yml | BSD-3-Clause | 2026-07-22 |
| `urllib3_ci.yml` | urllib3/urllib3 | `.github/workflows/ci.yml` | https://raw.githubusercontent.com/urllib3/urllib3/main/.github/workflows/ci.yml | MIT | 2026-07-22 |
| `celery_python_package.yml` | celery/celery | `.github/workflows/python-package.yml` | https://raw.githubusercontent.com/celery/celery/main/.github/workflows/python-package.yml | BSD-3-Clause | 2026-07-22 |
| `scipy_linux.yml` | scipy/scipy | `.github/workflows/linux.yml` | https://raw.githubusercontent.com/scipy/scipy/main/.github/workflows/linux.yml | BSD-3-Clause | 2026-07-22 |
| `pre_commit_main.yml` | pre-commit/pre-commit | `.github/workflows/main.yml` | https://raw.githubusercontent.com/pre-commit/pre-commit/main/.github/workflows/main.yml | MIT | 2026-07-30 |
| `cpython_reusable_macos.yml` | python/cpython | `.github/workflows/reusable-macos.yml` | https://raw.githubusercontent.com/python/cpython/main/.github/workflows/reusable-macos.yml | PSF License | 2026-07-30 |
| `nextjs_build_and_test.yml` | vercel/next.js | `.github/workflows/build_and_test.yml` | https://raw.githubusercontent.com/vercel/next.js/canary/.github/workflows/build_and_test.yml | MIT | 2026-07-30 |
| `vscode_pr.yml` | microsoft/vscode | `.github/workflows/pr.yml` | https://raw.githubusercontent.com/microsoft/vscode/main/.github/workflows/pr.yml | MIT | 2026-07-30 |

All ten licenses are permissive (Apache-2.0, BSD-3-Clause, MIT, or the PSF
License) and permit this use. None required substitution.

**Note on `nextjs_build_and_test.yml`'s LICENSE path**: the repo's license
file is `license.md` (lowercase, not the usual `LICENSE`/`LICENSE.md`
casing) on the `canary` branch — `LICENSE`/`LICENSE.md` both 404 there.
Confirmed by directly probing all common casings/extensions before
fetching, not assumed.

**Structural-gap corrections from the original Phase 7 Step 1 recon
proposal** (the recon table's candidate gaps were speculative — "proposed
from general/public knowledge... not fetched" — and two turned out wrong
once the actual current repo content was checked):
- `pre_commit_main.yml` was expected to be a "trivial lint-only single
  job" but pre-commit/pre-commit's actual `main.yml`/`languages.yaml` are
  both more complex than that (2-job external-reusable-workflow-calling
  file, and a 3-stage dynamic-matrix pipeline, respectively — neither
  trivial). `main.yml` was kept anyway because it fills a different, real,
  currently-untested gap: an external (cross-repo) reusable-workflow call
  that passes typed `with:` input parameters — `tests/fixtures/eslint_ci.yml`'s
  existing external `uses:` call is bare, no inputs, confirmed by direct
  comparison.
- `vscode_pr.yml` was expected to demonstrate job-level `defaults:` and
  multi-stage `workflow_run:` triggers; neither pattern exists anywhere in
  microsoft/vscode's 15 current `.github/workflows/*.yml` files (checked
  all of them). Kept anyway because `pr.yml` fills a different, real,
  currently-untested gap that `LIMITATIONS.md` already names explicitly:
  list-form `runs-on` with genuine self-hosted runner labels embedding
  dynamic `${{ }}` expressions (e.g.
  `[self-hosted, 1ES.Pool=..., "JobId=...-${{ github.run_id }}-..."]`) —
  distinct from `tests/fixtures/upload_artifact_test.yml`'s list-form
  `runs-on` of plain hosted-runner names, which doesn't exercise this case.
- `cpython_reusable_macos.yml` (workflow_call with typed inputs) and
  `nextjs_build_and_test.yml` (large `needs:` fan-out/fan-in — 40 jobs,
  144 dependency edges — plus internal reusable-workflow chaining) matched
  their originally-proposed gaps as found.

**Commit SHAs below are best-effort** (the "most recent commit that
touched this specific file," read from each repo's commit-history page via
WebFetch) — `api.github.com` returns 400 in this environment, so these
are not cryptographically verified against the GitHub API. Recorded for
traceability, not as a guarantee of exactness:

| Fixture | Commit (best-effort) |
|---|---|
| `requests_lint.yml` | `4c800e9aea2059660b8306b0fc8f9e9a4232cb3e` |
| `httpie_code_style.yml` | `c995fd9b24840657387f2f4bfb33a2efde85afcc` |
| `httpx_test_suite.yml` | `435e1dac899adeb0c156c00721ecbb1124d75842` |
| `urllib3_ci.yml` | `24954df928e412065e76cbe5eaf4d6a2e8f413fb` |
| `celery_python_package.yml` | `e1c419a0cc4b9b3ace211eb5ed1e11b493470cf2` |
| `scipy_linux.yml` | `932080fcf6768e32724edba1afa1887cfe6b64f3` |
| `pre_commit_main.yml` | `f415f6c4d72224363ba794429b25cc3f52e04933` |
| `cpython_reusable_macos.yml` | `1402ac74aa3f0529a15d31aab4f392c4ece3db97` |
| `nextjs_build_and_test.yml` | `bd770878647212b23dc7643d2a9c6126df45aa2c` |
| `vscode_pr.yml` | `1263c0f6ca7d2b23950f11a274d35c2ab33ca0f8` |
