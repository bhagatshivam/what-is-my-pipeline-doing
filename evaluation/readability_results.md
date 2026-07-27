# Readability results (Tier 1, Method 5)

Caveat: Flesch-Kincaid-family formulas assume connected prose. The 'deterministic' column scores generators/text_generator.py's structured header/bullet-fragment output, not prose -- treat it as a rough density proxy, not a literal reading grade level. The 'llm' column is the headline comparison (does LLM polish help or hurt readability), but only reflects a genuine live measurement when source=llm_live; source=llm_fallback means no GEMINI_API_KEY was available and the row duplicates the deterministic score.

| Fixture | Det. FKGL | Det. Reading Ease | Det. Gunning Fog | LLM source | LLM FKGL | LLM Reading Ease | LLM Gunning Fog |
|---|---|---|---|---|---|---|---|
| checkout_check_dist.yml | 9.41 | 42.35 | 10.90 | llm_fallback | 9.41 | 42.35 | 10.90 |
| eslint_ci.yml | 13.96 | 19.18 | 13.78 | llm_fallback | 13.96 | 19.18 | 13.78 |
| fastapi_test.yml | 11.92 | 35.01 | 14.68 | llm_fallback | 11.92 | 35.01 | 14.68 |
| flask_tests.yml | 11.46 | 33.81 | 13.64 | llm_fallback | 11.46 | 33.81 | 13.64 |
| node_test_linux.yml | 7.72 | 52.16 | 10.32 | llm_fallback | 7.72 | 52.16 | 10.32 |
| pandas_unit_tests.yml | 10.62 | 36.00 | 12.51 | llm_fallback | 10.62 | 36.00 | 12.51 |
| pytorch_lint.yml | 17.69 | -21.25 | 17.37 | llm_fallback | 17.69 | -21.25 | 17.37 |
| rust_ci.yml | 10.37 | 42.65 | 12.14 | llm_fallback | 10.37 | 42.65 | 12.14 |
| setup_python_test.yml | 11.08 | 28.10 | 12.38 | llm_fallback | 11.08 | 28.10 | 12.38 |
| upload_artifact_test.yml | 10.42 | 44.73 | 12.78 | llm_fallback | 10.42 | 44.73 | 12.78 |
