# Held-out evaluation set sources

The `.yml` files in this directory are unmodified, real-world CI config
files pulled from public open-source repositories — the **held-out
evaluation set** for Phase 4.5 Item 5 (Round 2). Unlike `tests/fixtures/`,
these are never used to develop or tune the parser: their manifests
(`.manifest.yml` siblings) were authored by reading this raw YAML by hand,
before the parser/generators were ever run against them, and the set exists
specifically to provide independent, non-circular ground truth for scoring
this project's actual output. None of these 6 repos overlap with
`tests/fixtures/`'s existing 10 (`actions/checkout`, `pallets/flask`,
`nodejs/node`, `eslint/eslint`, `fastapi/fastapi`, `rust-lang/rust`,
`pytorch/pytorch`, `actions/upload-artifact`, `pandas-dev/pandas`,
`actions/setup-python`).

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

All six licenses are permissive (Apache-2.0, BSD-3-Clause, or MIT) and
permit this use. None required substitution.

**Commit SHAs below are best-effort** (the "most recent commit that
touched this specific file," read from each repo's commit-history page via
WebFetch during candidate research) — `api.github.com` was blocked (403)
in this environment, so these are not cryptographically verified against
the GitHub API. Recorded for traceability, not as a guarantee of exactness:

| Fixture | Commit (best-effort) |
|---|---|
| `requests_lint.yml` | `4c800e9aea2059660b8306b0fc8f9e9a4232cb3e` |
| `httpie_code_style.yml` | `c995fd9b24840657387f2f4bfb33a2efde85afcc` |
| `httpx_test_suite.yml` | `435e1dac899adeb0c156c00721ecbb1124d75842` |
| `urllib3_ci.yml` | `24954df928e412065e76cbe5eaf4d6a2e8f413fb` |
| `celery_python_package.yml` | `e1c419a0cc4b9b3ace211eb5ed1e11b493470cf2` |
| `scipy_linux.yml` | `932080fcf6768e32724edba1afa1887cfe6b64f3` |
