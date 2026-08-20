# Tier 4 scoring — requests_lint

Pre-registered checklist: `evaluation/tier4_checklists/requests_lint.checklist.yml` (open separately -- not duplicated here).

Score each condition fact-by-fact against the checklist: present / missing / false (hallucination). Presentation order below is randomized per EVALUATION_PLAN.md's Method 9 bias mitigation -- the mapping back to conditions 1/2/3 is in `requests_lint.answer_key.md`, intentionally kept out of this file.

---

## Condition A

Pipeline: Lint code
Source: /home/user/what-is-my-pipeline-doing/evaluation/held_out_workflows/requests_lint.yml (GitHub Actions)
Permissions: contents: read

AT A GLANCE
This workflow runs on pushes and pull requests.
It contains 1 job, with no job dependencies, so GitHub may run them in parallel.

WHEN IT RUNS
- Runs on every push
- Runs on every pull request

EXECUTION SUMMARY
Independent jobs (no dependencies): lint

IMPLEMENTATION DETAILS
1. lint — runs on ubuntu-24.04; 3 steps
   - actions/checkout (https://github.com/actions/checkout)
   - Set up Python (https://github.com/actions/setup-python)
   - Run pre-commit

---

## Condition B

This CI/CD pipeline, defined as a GitHub Actions workflow named "Lint code," is designed to automatically check the code quality and style of your repository whenever changes are pushed or a pull request is opened.

Here's a breakdown of what each part does:

1.  **`name: Lint code`**
    *   This is the human-readable name for your workflow, which will appear in the GitHub Actions tab.

2.  **`on: [push, pull_request]`**
    *   This specifies when the workflow will be triggered.
    *   `push`: The workflow will run every time code is pushed to any branch in the repository.
    *   `pull_request`: The workflow will run every time a pull request is opened, synchronized (new commits added), or reopened.
    *   **Purpose:** Ensures that all new code or proposed changes are automatically checked for linting issues.

3.  **`permissions: contents: read`**
    *   This grants the workflow the minimum necessary permissions. `contents: read` allows the workflow to read the repository's code, which is essential for checking it out and running linting tools.

4.  **`jobs:`**
    *   This section defines one or more jobs that will run as part of the workflow.

5.  **`lint:`**
    *   This is the name of the single job in this workflow.

6.  **`runs-on: ubuntu-24.04`**
    *   This specifies the operating system and version of the virtual machine (runner) where the job will execute. In this case, it's a recent Ubuntu Linux environment.

7.  **`timeout-minutes: 10`**
    *   This sets a maximum execution time for the `lint` job. If the job takes longer than 10 minutes, it will be automatically canceled, preventing runaway jobs and wasting resources.

8.  **`steps:`**
    *   This defines a sequence of tasks that the `lint` job will perform.

    *   **`- uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0`**
        *   **Purpose:** This step uses the `checkout` action to clone your repository's code onto the runner machine. This is necessary so that the linting tools have access to the files they need to check.
        *   `with: persist-credentials: false`: This is a security best practice, ensuring that any Git credentials used for cloning are not persisted on the runner after the checkout is complete.

    *   **`- name: Set up Python`**
        *   **Purpose:** This step uses the `setup-python` action to install a Python environment on the runner.
        *   `with: python-version: "3.x"`: It specifies that any available version of Python 3 should be used (e.g., 3.9, 3.10, 3.11, etc., depending on what's available on the runner). This is crucial because the linting tool (`pre-commit`) is a Python package.

    *   **`- name: Run pre-commit`**
        *   **Purpose:** This is the core step where the actual linting and formatting checks happen.
        *   **`run: |`**: This indicates that the following lines are shell commands to be executed.
        *   **`python -m pip install pre-commit==4.6.0`**: This command installs the `pre-commit` framework using Python's package installer (`pip`). The version is pinned to `4.6.0` for reproducibility, ensuring the same version is used every time the workflow runs.
        *   **`pre-commit run --show-diff-on-failure --color=always --all-files`**: This command executes the `pre-commit` hooks.
            *   `pre-commit run`: Tells the `pre-commit` tool to execute the hooks defined in your repository's `.pre-commit-config.yaml` file (which is not shown here, but is a prerequisite for `pre-commit` to function).
            *   `--show-diff-on-failure`: If any hook makes changes to the files (e.g., auto-formatting) or fails, it will display the diff of those changes in the workflow logs, making it easier to see what went wrong.
            *   `--color=always`: Ensures that the output in the logs includes color, which can improve readability.
            *   `--all-files`: This is important for CI. It tells `pre-commit` to run its checks against *all* files in the repository, not just the ones that were changed in the current commit/PR. This ensures that the entire codebase adheres to the defined standards.

### In Summary:

This CI/CD pipeline automatically enforces code quality and style standards in your repository. Whenever new code is pushed or a pull request is created, it will:

1.  **Checkout** the latest code.
2.  **Set up** a Python environment.
3.  **Install** the `pre-commit` tool.
4.  **Run all configured `pre-commit` hooks** (e.g., linters, formatters like Black, Flake8, ESLint, etc., as defined in your `.pre-commit-config.yaml`) against the *entire codebase*.

If any of the `pre-commit` hooks fail (meaning there are linting errors, formatting issues, or other problems), the `lint` job will fail, and consequently, the entire workflow will fail. This typically prevents the problematic code from being merged into the main branch, ensuring a consistent and high-quality codebase.

---

## Condition C

# Lint code

<!-- llm-overview:start -->
## Overview

This GitHub Actions pipeline, named "Lint code", is configured to run automatically on every push to the repository and on every pull request. It requires `contents: read` permissions.

The pipeline contains a single, independent job named `lint`. This job executes on an `ubuntu-24.04` environment and performs three steps: it checks out the repository's code using `actions/checkout`, sets up Python using `actions/setup-python`, and then runs `pre-commit`.
<!-- llm-overview:end -->

```text
Pipeline: Lint code
Source: /home/user/what-is-my-pipeline-doing/evaluation/held_out_workflows/requests_lint.yml (GitHub Actions)
Permissions: contents: read

AT A GLANCE
This workflow runs on pushes and pull requests.
It contains 1 job, with no job dependencies, so GitHub may run them in parallel.

WHEN IT RUNS
- Runs on every push
- Runs on every pull request

EXECUTION SUMMARY
Independent jobs (no dependencies): lint

IMPLEMENTATION DETAILS
1. lint — runs on ubuntu-24.04; 3 steps
   - actions/checkout (https://github.com/actions/checkout)
   - Set up Python (https://github.com/actions/setup-python)
   - Run pre-commit
```

## Pipeline Diagram

All 1 job is independent — no job-dependency diagram is shown; see EXECUTION SUMMARY above.

---
