# Readability results (Tier 1, Method 5)

Caveat: Flesch-Kincaid-family formulas assume connected prose. The 'deterministic' column scores generators/text_generator.py's structured header/bullet-fragment output, not prose -- treat it as a rough density proxy, not a literal reading grade level. The 'llm' column is the headline comparison (does LLM polish help or hurt readability), but only reflects a genuine live measurement when source=llm_live; source=llm_fallback means either no GEMINI_API_KEY was available or the live call itself failed -- the 'LLM error' column distinguishes the two ('GEMINI_API_KEY not set' vs. the real exception), and the row duplicates the deterministic score either way.

| Fixture | Det. FKGL | Det. Reading Ease | Det. Gunning Fog | LLM source | LLM FKGL | LLM Reading Ease | LLM Gunning Fog | LLM error |
|---|---|---|---|---|---|---|---|---|
| checkout_check_dist.yml | 9.41 | 42.35 | 10.90 | llm_live | 10.53 | 43.98 | 11.74 |  |
| eslint_ci.yml | 13.96 | 19.18 | 13.78 | llm_live | 11.58 | 40.16 | 12.73 |  |
| fastapi_test.yml | 11.92 | 35.01 | 14.68 | llm_live | 11.23 | 43.87 | 14.20 |  |
| flask_tests.yml | 11.46 | 33.81 | 13.64 | llm_live | 9.49 | 51.99 | 11.05 |  |
| node_test_linux.yml | 7.72 | 52.16 | 10.32 | llm_live | 8.37 | 54.97 | 10.19 |  |
| pandas_unit_tests.yml | 10.62 | 36.00 | 12.51 | llm_live | 9.61 | 48.88 | 11.98 |  |
| pytorch_lint.yml | 17.69 | -21.25 | 17.37 | llm_live | 11.27 | 35.69 | 12.74 |  |
| rust_ci.yml | 10.37 | 42.65 | 12.14 | llm_live | 10.68 | 43.81 | 12.97 |  |
| setup_python_test.yml | 11.08 | 28.10 | 12.38 | llm_live | 15.20 | 18.70 | 14.38 |  |
| upload_artifact_test.yml | 10.42 | 44.73 | 12.78 | llm_live | 12.13 | 40.77 | 14.47 |  |
