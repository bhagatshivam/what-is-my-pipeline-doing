# Coverage check results, manifest-free (Tier 1, Method 2)

IR-to-output coverage: does every job/trigger/secret the parser extracted into the IR appear somewhere in generators/text_generator.py's output? This is a Layer 3 completeness check (did the generator drop what the parser extracted), not a claim that the parser extracted everything the source YAML contains -- see evaluation/fact_scoring.py (E1) for that. Coverage means presence, not exact wording.

Totals across all 10 fixtures: 76 correct, 0 missing.

| Fixture | Correct | Missing | Missing detail |
|---|---|---|---|
| checkout_check_dist.yml | 2 | 0 |  |
| eslint_ci.yml | 7 | 0 |  |
| fastapi_test.yml | 6 | 0 |  |
| flask_tests.yml | 3 | 0 |  |
| node_test_linux.yml | 2 | 0 |  |
| pandas_unit_tests.yml | 10 | 0 |  |
| pytorch_lint.yml | 15 | 0 |  |
| rust_ci.yml | 11 | 0 |  |
| setup_python_test.yml | 15 | 0 |  |
| upload_artifact_test.yml | 5 | 0 |  |
