# Tier 4 scoring — pre_commit_main

Pre-registered checklist: `evaluation/tier4_checklists/pre_commit_main.checklist.yml` (open separately -- not duplicated here).

Score each condition fact-by-fact against the checklist: present / missing / false (hallucination). Presentation order below is randomized per EVALUATION_PLAN.md's Method 9 bias mitigation -- the mapping back to conditions 1/2/3 is in `pre_commit_main.answer_key.md`, intentionally kept out of this file.

---

## Condition A

This CI/CD pipeline is a **GitHub Actions workflow** designed to automatically test a Python project across different operating systems and Python versions.

Here's a breakdown of what each section does:

1.  **`name: main`**
    *   This simply gives the workflow a name, which will appear in the GitHub Actions tab.

2.  **`on:`**
    *   This section defines **when** the workflow will be triggered.
    *   **`push:`**:
        *   `branches: [main, test-me-*]`
            *   The workflow will run whenever code is pushed to the `main` branch.
            *   It will also run for any branch whose name starts with `test-me-` (e.g., `test-me-feature-x`, `test-me-bugfix`). This is useful for testing experimental features or specific branches without affecting the main development line.
        *   `tags: '*'`
            *   The workflow will run whenever *any* Git tag is pushed (e.g., `v1.0.0`, `release-candidate`). This is typically used for release validation.
    *   **`pull_request:`**:
        *   The workflow will run whenever a pull request is opened, synchronized (new commits pushed to an existing PR), or reopened. This ensures that all proposed changes are tested before they can be merged.

3.  **`concurrency:`**
    *   This section manages how multiple workflow runs behave, especially for the same branch or PR.
    *   `group: ${{ github.workflow }}-${{ github.head_ref || github.run_id }}`
        *   This creates a unique concurrency group.
            *   For a Pull Request, `github.head_ref` will be the branch name of the PR. So, all runs for the *same PR branch* will belong to the same group.
            *   For a direct push (e.g., to `main` or a `test-me-*` branch), `github.head_ref` is usually empty, so it falls back to `github.run_id`, making each direct push run unique.
    *   `cancel-in-progress: true`
        *   If a new workflow run is triggered for a group that already has a run in progress (e.g., you push a new commit to an open PR while the previous commit's tests are still running), the *older, in-progress run will be automatically cancelled*.
        *   **Purpose:** This saves CI/CD resources and ensures you're only testing the very latest changes, preventing redundant runs.

4.  **`jobs:`**
    *   This section defines the actual tasks (jobs) that the workflow will execute.
    *   **`main-windows:`**
        *   `uses: asottile/workflows/.github/workflows/tox.yml@v1.8.1`
            *   This job is using a **reusable workflow** from another repository (`asottile/workflows`). This is a common practice to share and maintain CI/CD logic across multiple projects. The specific workflow being used is `tox.yml` at version `v1.8.1`. The `tox.yml` workflow likely sets up a Python environment and runs tests using `tox`, a popular Python testing automation tool.
        *   `with:`
            *   `env: '["py310"]'`
                *   This passes a parameter to the `tox.yml` reusable workflow, instructing it to run the tests specifically against **Python 3.10**.
            *   `os: windows-latest`
                *   This specifies that this job should run on the latest available **Windows** operating system runner provided by GitHub Actions.
        *   **In essence:** This job runs the project's Python tests (likely using `tox`) on Windows, specifically targeting Python 3.10.

    *   **`main-linux:`**
        *   `uses: asottile/workflows/.github/workflows/tox.yml@v1.8.1`
            *   Again, it uses the same reusable `tox.yml` workflow.
        *   `with:`
            *   `env: '["py310", "py311", "py312", "py313"]'`
                *   This instructs the `tox.yml` workflow to run tests against **multiple Python versions**: 3.10, 3.11, 3.12, and 3.13.
            *   `os: ubuntu-latest`
                *   This specifies that this job should run on the latest available **Ubuntu (Linux)** operating system runner.
        *   **In essence:** This job runs the project's Python tests (likely using `tox`) on Linux, targeting a range of Python versions from 3.10 to 3.13.

**Overall Summary:**

This CI/CD pipeline automatically tests a Python project whenever code is pushed to `main`, `test-me-*` branches, or any tag, and also for every pull request. It uses a shared `tox` testing workflow to run these tests. It performs two main testing jobs:
1.  **Windows testing:** Runs tests against Python 3.10 on a Windows environment.
2.  **Linux testing:** Runs tests against Python 3.10, 3.11, 3.12, and 3.13 on an Ubuntu (Linux) environment.

The `concurrency` setting ensures that only the latest commit for a given branch/PR is actively being tested, cancelling older, in-progress runs to save resources and provide faster feedback. This setup is typical for ensuring cross-platform and cross-Python-version compatibility for a Python library or application.

---

## Condition B

# main

<!-- llm-overview:start -->
## Overview

The `main` pipeline, defined as a GitHub Actions workflow at `/home/user/what-is-my-pipeline-doing/evaluation/held_out_workflows/pre_commit_main.yml`, runs on every push to `main` or `test-me-*` branches (with any tag), and on every pull request. It uses a concurrency group named `${{ github.workflow }}-${{ github.head_ref || github.run_id }}` which cancels any in-progress runs.

This pipeline contains two independent jobs, `main-windows` and `main-linux`, which GitHub may run in parallel as there are no job dependencies.

The `main-windows` job delegates to the reusable workflow `asottile/workflows/.github/workflows/tox.yml@v1.8.1` from `https://github.com/asottile/workflows`. It executes on `windows-latest` and uses the `py310` environment. The `main-linux` job also delegates to the same reusable workflow, `asottile/workflows/.github/workflows/tox.yml@v1.8.1`. It runs on `ubuntu-latest` and uses the `py310`, `py311`, `py312`, and `py313` environments.
<!-- llm-overview:end -->

```text
Pipeline: main
Source: /home/user/what-is-my-pipeline-doing/evaluation/held_out_workflows/pre_commit_main.yml (GitHub Actions)
Concurrency: group ${{ github.workflow }}-${{ github.head_ref || github.run_id }}; cancels in-progress runs

AT A GLANCE
This workflow runs on pushes to `main`, `test-me-*` and pull requests.
It contains 2 jobs, with no job dependencies, so GitHub may run them in parallel.

WHEN IT RUNS
- Runs on every push to main or test-me-* branches; with tag matching *
- Runs on every pull request

EXECUTION SUMMARY
Independent jobs (no dependencies): main-windows, main-linux

IMPLEMENTATION DETAILS
1. main-windows — delegates to reusable workflow asottile/workflows/.github/workflows/tox.yml@v1.8.1 (https://github.com/asottile/workflows); with: env: ["py310"], os: windows-latest
2. main-linux — delegates to reusable workflow asottile/workflows/.github/workflows/tox.yml@v1.8.1 (https://github.com/asottile/workflows); with: env: ["py310", "py311", "py312", "py313"], os: ubuntu-latest

LINKED WORKFLOWS
- calls asottile/workflows/.github/workflows/tox.yml@v1.8.1 (https://github.com/asottile/workflows)
```

## Pipeline Diagram

All 2 jobs are independent — no job-dependency diagram is shown; see EXECUTION SUMMARY above.

---

## Condition C

Pipeline: main
Source: /home/user/what-is-my-pipeline-doing/evaluation/held_out_workflows/pre_commit_main.yml (GitHub Actions)
Concurrency: group ${{ github.workflow }}-${{ github.head_ref || github.run_id }}; cancels in-progress runs

AT A GLANCE
This workflow runs on pushes to `main`, `test-me-*` and pull requests.
It contains 2 jobs, with no job dependencies, so GitHub may run them in parallel.

WHEN IT RUNS
- Runs on every push to main or test-me-* branches; with tag matching *
- Runs on every pull request

EXECUTION SUMMARY
Independent jobs (no dependencies): main-windows, main-linux

IMPLEMENTATION DETAILS
1. main-windows — delegates to reusable workflow asottile/workflows/.github/workflows/tox.yml@v1.8.1 (https://github.com/asottile/workflows); with: env: ["py310"], os: windows-latest
2. main-linux — delegates to reusable workflow asottile/workflows/.github/workflows/tox.yml@v1.8.1 (https://github.com/asottile/workflows); with: env: ["py310", "py311", "py312", "py313"], os: ubuntu-latest

LINKED WORKFLOWS
- calls asottile/workflows/.github/workflows/tox.yml@v1.8.1 (https://github.com/asottile/workflows)

---
