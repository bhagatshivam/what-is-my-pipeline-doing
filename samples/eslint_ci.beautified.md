# CI

<!-- llm-overview:start -->
## Overview

This CI pipeline, defined in `tests/fixtures/eslint_ci.yml` as a GitHub Actions workflow, runs on every push to the `main` branch and on every pull request targeting the `main` branch. It operates with `contents: read` permissions. The workflow consists of 6 independent jobs, which GitHub may run in parallel, and one of these jobs utilizes a build matrix.

The `verify_files` job runs on `ubuntu-latest` across 14 steps, which include checking out the repository, setting up Go and Node, linting GitHub Actions workflows, installing various packages, linting files, checking rule files, checking licenses, and linting documentation JavaScript files. The `test_on_node` job runs on `matrix.os` with 6 steps, using a build matrix with 5 base combinations of os, node, and NODE_OPTIONS, plus 3 additional ones. Its steps involve checking out the repository, setting up Node, installing packages, running tests, performing fuzz tests, and testing EMFILE handling. The `test_on_browser` job runs on `ubuntu-latest` with 5 steps, including checking out the repository, setting up Node, installing packages, running tests, and performing fuzz tests.

The `test_types` job runs on `ubuntu-latest` with 9 steps, which include checking out the repository, setting up Node, installing packages, testing types for `eslint`, `eslint-config-eslint`, and `@eslint/js`, and checking type compilation with TypeScript 5.3, TypeScript 5.x, and TypeScript 7 preview. The `test_package_manager` job delegates its execution to the reusable workflow `eslint/workflows/.github/workflows/ci-package-manager.yml@main`. Finally, the `pnpm_test` job runs on `ubuntu-latest` with 4 steps, involving checking out the repository, setting up pnpm, setting up Node, and running `pnpm test`.
<!-- llm-overview:end -->

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
   - actions/checkout@v7
   - actions/setup-go@v6
   - actions/setup-node@v6
   - Lint GitHub Actions workflows
   - Install Packages
   - Install Docs Packages
   - Lint Files
   - Check Rule Files
   - Check Licenses
   - Lint Docs JS Files
   - ... and 4 more steps
2. test_on_node — runs on ${{ matrix.os }}; 6 steps; matrix: 5 base combinations (os, node, NODE_OPTIONS) + 3 via include
   - actions/checkout@v7
   - actions/setup-node@v6
   - Install Packages
   - Test
   - Fuzz Test
   - Test EMFILE Handling
3. test_on_browser — runs on ubuntu-latest; 5 steps
   - actions/checkout@v7
   - actions/setup-node@v6
   - Install Packages
   - Test
   - Fuzz Test
4. test_types — runs on ubuntu-latest; 9 steps
   - actions/checkout@v7
   - actions/setup-node@v6
   - Install Packages
   - Test types (eslint)
   - Test types (eslint-config-eslint)
   - Test types (@eslint/js)
   - Check types compile (TypeScript 5.3)
   - Check types compile (TypeScript 5.x)
   - Check types compile (TypeScript 7 preview)
5. test_package_manager — delegates to reusable workflow eslint/workflows/.github/workflows/ci-package-manager.yml@main
6. pnpm_test — runs on ubuntu-latest; 4 steps
   - actions/checkout@v7
   - pnpm/action-setup
   - actions/setup-node@v6
   - Run pnpm test

LINKED WORKFLOWS
- calls eslint/workflows/.github/workflows/ci-package-manager.yml@main
```

## Pipeline Diagram

All 6 jobs are independent — no job-dependency diagram is shown; see EXECUTION SUMMARY above.
