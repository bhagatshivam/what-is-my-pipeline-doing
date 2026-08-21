# CI

```text
Pipeline: CI
Source: tests/fixtures/eslint_ci.yml (GitHub Actions)
Permissions: contents: read

AT A GLANCE
This workflow runs on pushes to `main` and pull requests.
It contains 6 jobs, with no job dependencies, so GitHub may run them in parallel.
1 of 6 jobs use a build matrix.

WHEN IT RUNS
- Runs on every push to main branch
- Runs on every pull request targeting main branch

EXECUTION SUMMARY
Independent jobs (no dependencies): verify_files, test_on_node, test_on_browser, test_types, test_package_manager, pnpm_test

IMPLEMENTATION DETAILS
1. verify_files — runs on ubuntu-latest; 14 steps
   - actions/checkout@v7 (https://github.com/actions/checkout)
   - actions/setup-go@v6 (https://github.com/actions/setup-go)
   - actions/setup-node@v6 (https://github.com/actions/setup-node)
   - Lint GitHub Actions workflows
   - Install Packages
   - Install Docs Packages
   - Lint Files
   - Check Rule Files
   - Check Licenses
   - Lint Docs JS Files
   - ... and 4 more steps
2. test_on_node — runs on ${{ matrix.os }}; 6 steps; matrix: 5 base combinations (os, node, NODE_OPTIONS) + 3 via include
   - actions/checkout@v7 (https://github.com/actions/checkout)
   - actions/setup-node@v6 (https://github.com/actions/setup-node)
   - Install Packages
   - Test
   - Fuzz Test
   - Test EMFILE Handling
3. test_on_browser — runs on ubuntu-latest; 5 steps
   - actions/checkout@v7 (https://github.com/actions/checkout)
   - actions/setup-node@v6 (https://github.com/actions/setup-node)
   - Install Packages
   - Test
   - Fuzz Test
4. test_types — runs on ubuntu-latest; 9 steps
   - actions/checkout@v7 (https://github.com/actions/checkout)
   - actions/setup-node@v6 (https://github.com/actions/setup-node)
   - Install Packages
   - Test types (eslint)
   - Test types (eslint-config-eslint)
   - Test types (@eslint/js)
   - Check types compile (TypeScript 5.3)
   - Check types compile (TypeScript 5.x)
   - Check types compile (TypeScript 7 preview)
5. test_package_manager — delegates to reusable workflow eslint/workflows/.github/workflows/ci-package-manager.yml@main (https://github.com/eslint/workflows)
6. pnpm_test — runs on ubuntu-latest; 4 steps
   - actions/checkout@v7 (https://github.com/actions/checkout)
   - pnpm/action-setup (https://github.com/pnpm/action-setup)
   - actions/setup-node@v6 (https://github.com/actions/setup-node)
   - Run pnpm test

LINKED WORKFLOWS
- calls eslint/workflows/.github/workflows/ci-package-manager.yml@main (https://github.com/eslint/workflows)

ENVIRONMENT VARIABLES
- NODE_OPTIONS: ${{ matrix.NODE_OPTIONS }} (used in job: test_on_node, step: Test)
- TERM: xterm-256color (used in job: test_on_browser)
```

## Pipeline Diagram

All 6 jobs are independent — no job-dependency diagram is shown; see EXECUTION SUMMARY above.
