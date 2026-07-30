# Test Linux

```text
Pipeline: Test Linux
Source: tests/fixtures/node_test_linux.yml (GitHub Actions)
Permissions: contents: read
Concurrency: group ${{ github.workflow }}-${{ github.head_ref || github.run_id }}; cancels in-progress runs

AT A GLANCE
This workflow runs on pull requests and pushes to `main`, `canary`, `v[0-9]+.x-staging`, `v[0-9]+.x`.
It contains 1 job, with no job dependencies, so GitHub may run them in parallel.
1 of 1 job use a build matrix; together these define 2 configured combinations.

WHEN IT RUNS
- Runs on every pull request excluding paths .mailmap or README.md or vcbuild.bat or tools/actions/** or tools/clang-format/** or tools/dep_updaters/** or test/internet/** or **.nix or .github/** or !.github/workflows/test-linux.yml
- Runs on every push to main or canary or v[0-9]+.x-staging or v[0-9]+.x branches; excluding paths .mailmap or README.md or vcbuild.bat or tools/actions/** or tools/clang-format/** or tools/dep_updaters/** or test/internet/** or **.nix or .github/** or !.github/workflows/test-linux.yml

EXECUTION SUMMARY
Independent jobs (no dependencies): test-linux

IMPLEMENTATION DETAILS
1. test-linux — runs on ${{ matrix.os }}; 9 steps; matrix: 2 combinations (os); condition: github.event.pull_request.draft == false
   - actions/checkout
   - Install Clang ${{ env.CLANG_VERSION }}
   - Install Rust ${{ env.RUSTC_VERSION }}
   - Set up Python ${{ env.PYTHON_VERSION }}
   - Set up sccache
   - Build
   - Test
   - Ensure running tests did not cause any change in the tree
   - Re-run test in a folder whose name contains unusual chars
```

## Pipeline Diagram

All 1 job is independent — no job-dependency diagram is shown; see EXECUTION SUMMARY above.
