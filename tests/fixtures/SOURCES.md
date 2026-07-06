# Fixture sources

The `.yml`/`.yaml` files in this directory are unmodified, real-world CI
config files pulled from public open-source repositories, used here as
test fixtures under their original licenses. They are **not** original
work product of this project — only the JSON ground-truth IR fixtures
(`simple_pipeline_ir.json`, `medium_pipeline_ir.json`,
`complex_pipeline_ir.json`) and `build_ir_fixtures.py` are.

Each license below was confirmed by fetching the source repository's actual
`LICENSE` file directly (not assumed from the project's reputation).

| Fixture | Source repo | Original path | URL fetched from | License | Date fetched |
|---|---|---|---|---|---|
| `checkout_check_dist.yml` | actions/checkout | `.github/workflows/check-dist.yml` | https://raw.githubusercontent.com/actions/checkout/main/.github/workflows/check-dist.yml | MIT | 2026-07-06 |
| `flask_tests.yml` | pallets/flask | `.github/workflows/tests.yaml` | https://raw.githubusercontent.com/pallets/flask/main/.github/workflows/tests.yaml | BSD-3-Clause | 2026-07-06 |
| `node_test_linux.yml` | nodejs/node | `.github/workflows/test-linux.yml` | https://raw.githubusercontent.com/nodejs/node/main/.github/workflows/test-linux.yml | MIT | 2026-07-06 |
| `eslint_ci.yml` | eslint/eslint | `.github/workflows/ci.yml` | https://raw.githubusercontent.com/eslint/eslint/main/.github/workflows/ci.yml | MIT | 2026-07-06 |
| `fastapi_test.yml` | fastapi/fastapi | `.github/workflows/test.yml` | https://raw.githubusercontent.com/fastapi/fastapi/master/.github/workflows/test.yml | MIT | 2026-07-06 |
| `rust_ci.yml` | rust-lang/rust | `.github/workflows/ci.yml` | https://raw.githubusercontent.com/rust-lang/rust/master/.github/workflows/ci.yml | MIT OR Apache-2.0 (dual-licensed) | 2026-07-06 |
| `pytorch_lint.yml` | pytorch/pytorch | `.github/workflows/lint.yml` | https://raw.githubusercontent.com/pytorch/pytorch/main/.github/workflows/lint.yml | BSD-3-Clause | 2026-07-06 |
| `upload_artifact_test.yml` | actions/upload-artifact | `.github/workflows/test.yml` | https://raw.githubusercontent.com/actions/upload-artifact/main/.github/workflows/test.yml | MIT | 2026-07-06 |
| `pandas_unit_tests.yml` | pandas-dev/pandas | `.github/workflows/unit-tests.yml` | https://raw.githubusercontent.com/pandas-dev/pandas/main/.github/workflows/unit-tests.yml | BSD-3-Clause | 2026-07-06 |
| `setup_python_test.yml` | actions/setup-python | `.github/workflows/test-python.yml` | https://raw.githubusercontent.com/actions/setup-python/main/.github/workflows/test-python.yml | MIT | 2026-07-06 |

All ten licenses are permissive (MIT, BSD-3-Clause, or MIT/Apache-2.0
dual-licensed) and permit this use. None required substitution.
