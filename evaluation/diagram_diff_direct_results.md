# Diagram-structure check results, manifest-free (Tier 1, Method 3)

IR-to-diagram structure check: do generators/mermaid_generator.py's job nodes and dependency edges match pipeline.jobs/Job.dependencies exactly? Scope is the job dependency graph specifically, not trigger-to-job entry edges -- same scope decision as evaluation/diagram_diff.py's existing manifest-driven counterpart.

Totals: 10/10 fixtures exact match.

| Fixture | Exact match | Missing nodes | Extra nodes | Missing edges | Extra edges |
|---|---|---|---|---|---|
| checkout_check_dist.yml | True | - | - | - | - |
| eslint_ci.yml | True | - | - | - | - |
| fastapi_test.yml | True | - | - | - | - |
| flask_tests.yml | True | - | - | - | - |
| node_test_linux.yml | True | - | - | - | - |
| pandas_unit_tests.yml | True | - | - | - | - |
| pytorch_lint.yml | True | - | - | - | - |
| rust_ci.yml | True | - | - | - | - |
| setup_python_test.yml | True | - | - | - | - |
| upload_artifact_test.yml | True | - | - | - | - |
