# Variance results (Tier 1, Method 4)

This variance check answers the question raised by PR 2's readability results (evaluation/readability_results.md): are the per-fixture FKGL swings between deterministic and LLM-polished text real repeatable effects of each fixture's content, or run-to-run noise on a single call?

Scope: FKGL only (per-metric variance for Reading Ease/Gunning Fog is recoverable after the fact from each row's stored raw prose without spending fresh quota). Pure stochastic variance at the tool's production temperature (0.2) -- not a temperature sweep.

Interpretation rule (fixed, stated explicitly so the label isn't opaque):
  range < 1.0            -> essentially deterministic
  1.0 <= range < 3.0     -> moderate drift
  range >= 3.0           -> large drift

## Summary

| Fixture | Det. FKGL | LLM FKGL mean (N=10) | Std dev | Min | Max | Range | Interpretation | Notes |
|---|---|---|---|---|---|---|---|---|
| pytorch_lint.yml | 17.69 | 11.21 | 0.56 | 10.33 | 11.92 | 1.59 | moderate drift (range 1-3 grade levels) | 0 error(s) |
| setup_python_test.yml | 11.08 | 13.78 | 2.54 | 9.57 | 17.06 | 7.49 | large drift (range >= 3 grade levels) | 0 error(s) |
| rust_ci.yml | 10.37 | 12.07 | 0.75 | 10.29 | 12.96 | 2.67 | moderate drift (range 1-3 grade levels) | 0 error(s) |

## Per-fixture raw samples

### pytorch_lint.yml — PR 2 showed a 6.42-grade-level drop under LLM polish

Raw N=10 FKGL values (`fkgl` per repeat):
- 10.68
- 11.73
- 11.11
- 11.34
- 10.33
- 11.79
- 10.64
- 11.92
- 10.95
- 11.66

Stored raw prose per repeat (for later recomputation of other metrics without spending fresh quota):
<details><summary>repeat 1 (FKGL 10.68)</summary>

The Lint pipeline, defined in `tests\fixtures\pytorch_lint.yml` as a GitHub Actions workflow, operates with read-all permissions. It manages concurrency by grouping runs based on the workflow, pull request number or SHA, or run ID for manual triggers, canceling any in-progress runs within the same group. This pipeline is triggered on every pull request, excluding the `nightly` branch. It also runs on pushes to `main`, `release/*`, or `landchecks/*` branches, provided the push includes a tag matching `ciflow/pull/*` or `ciflow/trunk/*`. Additionally, the pipeline can be triggered manually.

The pipeline begins by delegating to `pytorch/pytorch/.github/workflows/_runner-determinator.yml@main` for `get-label-type` and to `./.github/workflows/_get-changed-files.yml` for `get-changed-files`. These initial jobs, along with most subsequent jobs, execute only if the repository owner is 'pytorch'. Following these, several linting jobs delegate to `./.github/workflows/_lint.yml`: `lintrunner-clang` runs if C/C++/CUDA/Metal files are changed or all files, `lintrunner-pyrefly` runs if Python files are changed or all files, and `lintrunner-noclang` runs unconditionally. All these linting jobs run after `get-label-type` and `get-changed-files`. Additional checks, `quick-checks`, `workflow-checks`, and `toc`, also delegate to `./.github/workflows/_lint.yml` and run after `get-label-type`.

Further specific checks are performed. The `pr-sanity-checks` job runs on `linux.24_04.4x` for pull requests (unless labeled 'skip-pr-sanity-checks') to checkout PyTorch and perform a PR size check. For the `pytorch/pytorch` repository, `test-tools` delegates to `./.github/workflows/_lint.yml` after `get-label-type`. Also for `pytorch/pytorch`, `test_run_test` runs on `linux.24_04.4x` to checkout PyTorch, set up Python 3.10, install dependencies, and execute `run_test.py`. The `test_collect_env` job runs across three matrix combinations to collect environment information. Finally, `link-check` delegates to `./.github/workflows/_link_check.yml` after `get-label-type`, and `doc-redirects-check` runs on `linux.24_04.4x` for pull requests to checkout PyTorch and perform a documentation redirects check.

</details>
<details><summary>repeat 2 (FKGL 11.73)</summary>

The Lint pipeline, defined in `tests\fixtures\pytorch_lint.yml` as a GitHub Actions workflow, operates with `read-all` permissions. It manages concurrency by grouping runs based on the workflow, pull request number or SHA, and run ID for manual triggers, canceling any in-progress runs within the same group. This pipeline is triggered on every pull request, excluding those targeting the `nightly` branch. It also runs on every push to `main`, `release/*`, or `landchecks/*` branches, provided the push includes a tag matching `ciflow/pull/*` or `ciflow/trunk/*`. Additionally, the pipeline can be triggered manually.

The pipeline begins with several jobs that primarily delegate to reusable workflows, typically under the condition that the repository owner is 'pytorch'. First, `get-label-type` delegates to `pytorch/pytorch/.github/workflows/_runner-determinator.yml@main`, followed by `get-changed-files` which delegates to `./.github/workflows/_get-changed-files.yml`. Subsequently, three linting jobs run after `get-label-type` and `get-changed-files`: `lintrunner-clang` checks C/C++/CUDA/Metal files, `lintrunner-pyrefly` checks Python files, and `lintrunner-noclang` performs other linting. These specific linting jobs only run if relevant file types have changed or if all files are considered changed.

Further checks include `quick-checks`, `workflow-checks`, `toc`, and `test-tools`, all of which delegate to `./.github/workflows/_lint.yml` after `get-label-type`, with `test-tools` specifically running for the `pytorch/pytorch` repository. The `pr-sanity-checks` job runs on `linux.24_04.4x` for pull requests, checking out PyTorch and performing a PR size check, unless the 'skip-pr-sanity-checks' label is present. For the `pytorch/pytorch` repository, `test_run_test` runs on `linux.24_04.4x` to checkout PyTorch, set up Python 3.10, install dependencies, and execute `run_test.py`. Also for `pytorch/pytorch`, `test_collect_env` runs across three matrix combinations to checkout PyTorch, set up Python versions, install torch, and run `collect_env.py`. Finally, `link-check` delegates to `./.github/workflows/_link_check.yml` after `get-label-type`, and `doc-redirects-check` runs on `linux.24_04.4x` for pull requests to checkout PyTorch and perform a documentation redirects check.

</details>
<details><summary>repeat 3 (FKGL 11.11)</summary>

The Lint pipeline, defined in `tests\fixtures\pytorch_lint.yml` as a GitHub Actions workflow, operates with read-all permissions. It manages concurrency by grouping runs based on the workflow, pull request number or SHA, and run ID for manual triggers, canceling any in-progress runs within the same group. This pipeline is triggered on every pull request, excluding those targeting the `nightly` branch. It also runs on every push to `main`, `release/*`, or `landchecks/*` branches, provided the push includes a tag matching `ciflow/pull/*` or `ciflow/trunk/*`. Additionally, the pipeline can be triggered manually.

The pipeline executes a series of jobs, many of which delegate to reusable workflows. It begins with `get-label-type`, which delegates to `pytorch/pytorch/.github/workflows/_runner-determinator.yml@main`, and `get-changed-files`, which delegates to `./.github/workflows/_get-changed-files.yml`. Both of these initial jobs run only if the repository owner is 'pytorch'. Following these, several linting jobs delegate to `./.github/workflows/_lint.yml`: `lintrunner-clang` runs if C/C++/CUDA/Metal files are changed or all files are changed, `lintrunner-pyrefly` runs if Python files are changed or all files are changed, and `lintrunner-noclang` runs unconditionally after the initial jobs. Other linting-related jobs, `quick-checks`, `workflow-checks`, and `toc`, also delegate to `./.github/workflows/_lint.yml` after `get-label-type`, all conditional on the repository owner being 'pytorch'.

Further checks and tests are performed. The `pr-sanity-checks` job runs on `linux.24_04.4x` for pull requests, checking out PyTorch and performing a PR size check, provided the `skip-pr-sanity-checks` label is not present and the repository owner is 'pytorch'. The `test-tools` job delegates to `./.github/workflows/_lint.yml` if the repository is `pytorch/pytorch`. The `test_run_test` job runs on `linux.24_04.4x` for `pytorch/pytorch`, checking out PyTorch, setting up Python 3.10, installing dependencies, and running `run_test.py`. The `test_collect_env` job runs on a matrix of three combinations for `pytorch/pytorch`, checking out PyTorch, setting up old and minimum Python versions, installing torch, and running `collect_env.py`. Finally, `link-check` delegates to `./.github/workflows/_link_check.yml` after `get-label-type` if the repository owner is 'pytorch', and `doc-redirects-check` runs on `linux.24_04.4x` for pull requests, checking out PyTorch and performing a doc redirects check, if the repository owner is 'pytorch'.

</details>
<details><summary>repeat 4 (FKGL 11.34)</summary>

The Lint pipeline, defined in `tests\fixtures\pytorch_lint.yml` for GitHub Actions, operates with `read-all` permissions. It manages concurrency by grouping runs based on the workflow, pull request number or SHA, and run ID for manual triggers, canceling any in-progress runs within the same group. This pipeline is triggered on every pull request, except those targeting the `nightly` branch. It also runs on every push to `main`, `release/*`, or `landchecks/*` branches, provided the push includes a tag matching `ciflow/pull/*` or `ciflow/trunk/*`. Additionally, the pipeline can be triggered manually.

The pipeline begins with the `get-label-type` job, which delegates to the `pytorch/pytorch/.github/workflows/_runner-determinator.yml@main` reusable workflow, and the `get-changed-files` job, which delegates to the `./.github/workflows/_get-changed-files.yml` reusable workflow. Both of these initial jobs run only if the repository owner is `pytorch`. Following these, several linting jobs delegate to the `./.github/workflows/_lint.yml` reusable workflow: `lintrunner-clang` runs if the repository owner is `pytorch` and C/C++/CUDA/Metal files are changed or all files are changed; `lintrunner-pyrefly` runs if the repository owner is `pytorch` and Python files are changed or all files are changed. Both `lintrunner-clang` and `lintrunner-pyrefly` depend on `get-label-type` and `get-changed-files`. The `lintrunner-noclang` job also delegates to `./.github/workflows/_lint.yml` after `get-label-type` and `get-changed-files`.

Further checks include `quick-checks`, `workflow-checks`, `toc`, and `test-tools`, all of which delegate to `./.github/workflows/_lint.yml` after `get-label-type` and run under specific `pytorch` repository conditions. A `pr-sanity-checks` job runs on `linux.24_04.4x` for pull requests, checking out PyTorch and performing a PR size check, unless the `skip-pr-sanity-checks` label is present, and only if the repository owner is `pytorch`. The `test_run_test` job runs on `linux.24_04.4x` to checkout PyTorch, set up Python 3.10, install dependencies, and run `run_test.py`, specifically for the `pytorch/pytorch` repository. Similarly, `test_collect_env` runs on a matrix of 3 runner combinations for `pytorch/pytorch`, checking out PyTorch, setting up Python versions, installing torch, and running `collect_env.py`. Finally, `link-check` delegates to `./.github/workflows/_link_check.yml` after `get-label-type` if the repository owner is `pytorch`, and `doc-redirects-check` runs on `linux.24_04.4x` for pull requests in the `pytorch` repository, checking out PyTorch and performing a doc redirects check.

</details>
<details><summary>repeat 5 (FKGL 10.33)</summary>

The Lint pipeline, defined in `tests\fixtures\pytorch_lint.yml` as a GitHub Actions workflow, operates with `read-all` permissions. It runs on every pull request except those targeting the `nightly` branch, and on every push to `main`, `release/*`, or `landchecks/*` branches when accompanied by a tag matching `ciflow/pull/*` or `ciflow/trunk/*`. This pipeline can also be triggered manually. Concurrency is managed by grouping runs based on the workflow, pull request number or SHA, and run ID for manual dispatches, canceling any in-progress runs within the same group.

The pipeline begins with `get-label-type`, which delegates to `pytorch/pytorch/.github/workflows/_runner-determinator.yml@main`, and `get-changed-files`, which delegates to `./.github/workflows/_get-changed-files.yml`. Both of these initial jobs run only if the repository owner is 'pytorch'. Following these, several linting jobs delegate to `./.github/workflows/_lint.yml`: `lintrunner-clang` runs if C/C++/CUDA/Metal files are changed or all files are changed, `lintrunner-pyrefly` runs if Python files are changed or all files are changed, and `lintrunner-noclang` runs unconditionally after the initial jobs. Additional checks, `quick-checks`, `workflow-checks`, and `toc`, also delegate to `./.github/workflows/_lint.yml` if the repository owner is 'pytorch'. The `test-tools` job also delegates to `./.github/workflows/_lint.yml` if the repository is 'pytorch/pytorch'.

Further jobs include `pr-sanity-checks`, which runs on `linux.24_04.4x` with two steps (Checkout PyTorch, PR size check (nonretryable)) for pull requests not labeled 'skip-pr-sanity-checks' and owned by 'pytorch'. The `test_run_test` job runs on `linux.24_04.4x` with four steps (Checkout PyTorch, Setup Python 3.10, Install dependencies, Run run_test.py (nonretryable)) if the repository is 'pytorch/pytorch'. `test_collect_env` runs on a matrix of three combinations with six steps (Checkout PyTorch, Get min python version, Setup Old Python version, Setup Min Python version, Install torch, Run collect_env.py (nonretryable)) under the same repository condition. Finally, `link-check` delegates to `./.github/workflows/_link_check.yml` if the repository owner is 'pytorch', and `doc-redirects-check` runs on `linux.24_04.4x` with two steps (Checkout PyTorch, Doc redirects check (nonretryable)) for pull requests owned by 'pytorch'.

</details>
<details><summary>repeat 6 (FKGL 11.79)</summary>

The Lint pipeline, defined in `tests\fixtures\pytorch_lint.yml` as a GitHub Actions workflow, operates with `read-all` permissions. It manages concurrency by grouping runs using the identifier `${{ github.workflow }}-${{ github.event.pull_request.number || github.sha }}-${{ github.event_name == 'workflow_dispatch' && github.run_id }}`, and cancels any in-progress runs within the same group. This pipeline is triggered on every pull request, except for those targeting the `nightly` branch. It also runs on pushes to `main`, `release/*`, or `landchecks/*` branches when accompanied by tags matching `ciflow/pull/*` or `ciflow/trunk/*`. Additionally, it can be triggered manually.

The pipeline begins with `get-label-type`, which delegates to the reusable workflow `pytorch/pytorch/.github/workflows/_runner-determinator.yml@main`, and `get-changed-files`, which delegates to `./.github/workflows/_get-changed-files.yml`. Both of these initial jobs run only if the repository owner is 'pytorch'. Following these, several linting jobs execute: `lintrunner-clang` checks C/C++/CUDA/Metal files (or all files) and `lintrunner-pyrefly` checks Python files (or all files), both delegating to `./.github/workflows/_lint.yml` after `get-label-type` and `get-changed-files`, and also conditional on the repository owner being 'pytorch'. The `lintrunner-noclang` job also delegates to `./.github/workflows/_lint.yml` after the same preceding jobs. Further checks include `quick-checks`, `workflow-checks`, and `toc`, all delegating to `./.github/workflows/_lint.yml` after `get-label-type` and conditional on the repository owner being 'pytorch'. The `test-tools` job also delegates to `./.github/workflows/_lint.yml` after `get-label-type`, specifically for the `pytorch/pytorch` repository.

The pipeline also includes `pr-sanity-checks`, which runs on `linux.24_04.4x` for pull requests (unless labeled 'skip-pr-sanity-checks' and if the repository owner is 'pytorch') to checkout PyTorch and perform a PR size check. For the `pytorch/pytorch` repository, `test_run_test` runs on `linux.24_04.4x` to checkout PyTorch, set up Python 3.10, install dependencies, and run `run_test.py`. The `test_collect_env` job runs across 3 matrix combinations to checkout PyTorch, set up Python versions, install torch, and run `collect_env.py`. Finally, `link-check` delegates to `./.github/workflows/_link_check.yml` after `get-label-type` if the repository owner is 'pytorch', and `doc-redirects-check` runs on `linux.24_04.4x` for pull requests if the repository owner is 'pytorch' to checkout PyTorch and perform a doc redirects check.

</details>
<details><summary>repeat 7 (FKGL 10.64)</summary>

The Lint pipeline, defined in `tests\fixtures\pytorch_lint.yml` as a GitHub Actions workflow, operates with `read-all` permissions. It manages concurrency by grouping runs based on the workflow, pull request number or SHA, and run ID for manual dispatches, canceling in-progress runs within the same group. This pipeline is triggered on every pull request, excluding those targeting the `nightly` branch. It also runs on every push to `main`, `release/*`, or `landchecks/*` branches, provided the push includes a tag matching `ciflow/pull/*` or `ciflow/trunk/*`. Additionally, the pipeline can be triggered manually.

The pipeline's jobs primarily execute if the repository owner is 'pytorch'. It starts with `get-label-type`, which delegates to the `pytorch/pytorch/.github/workflows/_runner-determinator.yml@main` reusable workflow. Next, `get-changed-files` delegates to the `./.github/workflows/_get-changed-files.yml` reusable workflow. Following both `get-label-type` and `get-changed-files`, three linting jobs run: `lintrunner-clang` delegates to `./.github/workflows/_lint.yml` if C/C++/CUDA/Metal files are changed or all files are changed; `lintrunner-pyrefly` delegates to `./.github/workflows/_lint.yml` if Python files are changed or all files are changed; and `lintrunner-noclang` also delegates to `./.github/workflows/_lint.yml`.

Several other checks run after `get-label-type` completes: `quick-checks`, `workflow-checks`, and `toc` all delegate to the `./.github/workflows/_lint.yml` reusable workflow. The `test-tools` job also delegates to `./.github/workflows/_lint.yml`, specifically if the repository is `pytorch/pytorch`. A `pr-sanity-checks` job runs on `linux.24_04.4x` with two steps—checking out PyTorch and performing a PR size check—specifically for pull requests and if the 'skip-pr-sanity-checks' label is not present. Further testing includes `test_run_test`, which runs on `linux.24_04.4x` with four steps (Checkout PyTorch, Setup Python 3.10, Install dependencies, Run run_test.py) if the repository is `pytorch/pytorch`. The `test_collect_env` job runs on a matrix of 3 combinations with six steps (Checkout PyTorch, Get min python version, Setup Old Python version, Setup Min Python version, Install torch, Run collect_env.py), also if the repository is `pytorch/pytorch`. Finally, `link-check` delegates to `./.github/workflows/_link_check.yml` after `get-label-type`, and `doc-redirects-check` runs on `linux.24_04.4x` with two steps (Checkout PyTorch, Doc redirects check) for pull requests.

</details>
<details><summary>repeat 8 (FKGL 11.92)</summary>

The Lint pipeline, defined in `tests\fixtures\pytorch_lint.yml` as a GitHub Actions workflow, operates with read-all permissions. It manages concurrency by grouping runs based on the workflow, pull request number or SHA, and run ID for manual dispatches, canceling any in-progress runs within the same group. This pipeline is triggered on every pull request, except for the `nightly` branch. It also runs on every push to `main`, `release/*`, or `landchecks/*` branches, provided the push has a tag matching `ciflow/pull/*` or `ciflow/trunk/*`. Additionally, it can be triggered manually.

The pipeline's initial jobs, all conditional on the repository owner being 'pytorch', include `get-label-type`, which uses a reusable workflow from `pytorch/pytorch`, and `get-changed-files`, which identifies modified files. Following these, several linting jobs execute: `lintrunner-clang` checks C/C++/CUDA/Metal files, `lintrunner-pyrefly` checks Python files, and `lintrunner-noclang` runs other lint checks. These linting jobs depend on both `get-label-type` and `get-changed-files`. Further lint-related checks, all delegating to a reusable lint workflow and depending on `get-label-type`, include `quick-checks`, `workflow-checks`, `toc`, and `test-tools`. The `test-tools` job specifically runs only if the repository is `pytorch/pytorch`.

Additional jobs perform specific validations. `pr-sanity-checks` runs on `linux.24_04.4x` for pull requests, unless the 'skip-pr-sanity-checks' label is present, and includes checking out PyTorch and a PR size check. `test_run_test` runs on `linux.24_04.4x` for the `pytorch/pytorch` repository, checking out PyTorch, setting up Python 3.10, installing dependencies, and running `run_test.py`. `test_collect_env` runs across three matrix combinations to collect environment information using `collect_env.py` after setting up Python versions and installing torch, also for the `pytorch/pytorch` repository. Finally, `link-check` delegates to a reusable workflow, and `doc-redirects-check` runs on `linux.24_04.4x` for pull requests, checking out PyTorch and performing a doc redirects check. All these jobs, except `test_run_test` and `test_collect_env`, are conditional on the repository owner being 'pytorch'.

</details>
<details><summary>repeat 9 (FKGL 10.95)</summary>

The "Lint" pipeline, defined in `tests\fixtures\pytorch_lint.yml` as a GitHub Actions workflow, operates with `read-all` permissions. It manages concurrency by canceling any in-progress runs within the same group, which is identified by the workflow, pull request number (if applicable), or run ID for manual dispatches. This pipeline is triggered on every pull request, excluding those targeting the `nightly` branch. It also runs on pushes to `main`, `release/*`, or `landchecks/*` branches when the push tag matches `ciflow/pull/*` or `ciflow/trunk/*`. Additionally, the pipeline can be triggered manually.

The pipeline begins with `get-label-type`, which delegates to `pytorch/pytorch/.github/workflows/_runner-determinator.yml@main`, and `get-changed-files`, which delegates to `./.github/workflows/_get-changed-files.yml`. Both of these jobs execute only if the repository owner is 'pytorch'. Following these, several linting jobs run, all delegating to `./.github/workflows/_lint.yml` after `get-label-type` and `get-changed-files`. Specifically, `lintrunner-clang` runs if C/C++/CUDA/Metal files are changed or all files are changed, while `lintrunner-pyrefly` runs if Python files are changed or all files are changed. `lintrunner-noclang` runs unconditionally after the initial jobs. `quick-checks`, `workflow-checks`, and `toc` also delegate to `./.github/workflows/_lint.yml` after `get-label-type` if the repository owner is 'pytorch'.

Further checks include `pr-sanity-checks`, which runs on `linux.24_04.4x` to checkout PyTorch and perform a PR size check, provided it's a pull request, the 'skip-pr-sanity-checks' label is not present, and the repository owner is 'pytorch'. The `test-tools` job delegates to `./.github/workflows/_lint.yml` after `get-label-type` if the repository is `pytorch/pytorch`. Two test jobs, `test_run_test` and `test_collect_env`, run if the repository is `pytorch/pytorch`. `test_run_test` runs on `linux.24_04.4x` to checkout PyTorch, set up Python 3.10, install dependencies, and run `run_test.py`. `test_collect_env` runs across three matrix combinations to checkout PyTorch, set up Python versions, install torch, and run `collect_env.py`. Finally, `link-check` delegates to `./.github/workflows/_link_check.yml` after `get-label-type`, and `doc-redirects-check` runs on `linux.24_04.4x` to checkout PyTorch and perform a doc redirects check, both if the repository owner is 'pytorch' and `doc-redirects-check` specifically for pull requests.

</details>
<details><summary>repeat 10 (FKGL 11.66)</summary>

The Lint pipeline, defined in `tests\fixtures\pytorch_lint.yml` and operating with `read-all` permissions, triggers on every pull request except those targeting the `nightly` branch. It also runs on pushes to `main`, `release/*`, or `landchecks/*` branches when accompanied by a tag matching `ciflow/pull/*` or `ciflow/trunk/*`. Manual triggering is also supported. Concurrency is managed by grouping runs based on the workflow, pull request number or SHA, and run ID for manual dispatches, canceling any in-progress runs within the same group.

The pipeline's initial jobs, `get-label-type` and `get-changed-files`, delegate to `_runner-determinator.yml@main` and `_get-changed-files.yml` respectively, both running only if the repository owner is 'pytorch'. Following these, several linting jobs execute, all delegating to `_lint.yml` and also conditional on the repository owner being 'pytorch'. These include `lintrunner-clang` for C/C++/CUDA/Metal/Objective-C++ files, `lintrunner-pyrefly` for Python files, and `lintrunner-noclang` for other files. These specific linting jobs run after both `get-label-type` and `get-changed-files`.

Additional checks include `quick-checks`, `workflow-checks`, and `toc`, which also delegate to `_lint.yml` and run after `get-label-type` if the repository owner is 'pytorch'. The `test-tools` job, also delegating to `_lint.yml`, runs after `get-label-type` specifically for the `pytorch/pytorch` repository. A `pr-sanity-checks` job runs on `linux.24_04.4x` for pull requests, checking out PyTorch and performing a PR size check, unless the 'skip-pr-sanity-checks' label is present, and only if the repository owner is 'pytorch'.

The pipeline also executes `test_run_test` on `linux.24_04.4x` for the `pytorch/pytorch` repository, which checks out PyTorch, sets up Python 3.10, installs dependencies, and runs `run_test.py`. The `test_collect_env` job runs across three matrix combinations for the `pytorch/pytorch` repository, checking out PyTorch, setting up Python versions, installing torch, and running `collect_env.py`. Finally, `link-check` delegates to `_link_check.yml` after `get-label-type`, and `doc-redirects-check` runs on `linux.24_04.4x` for pull requests, checking out PyTorch and performing a doc redirects check, both conditional on the repository owner being 'pytorch'.

</details>

### setup_python_test.yml — PR 2 showed a 4.12-grade-level rise

Raw N=10 FKGL values (`fkgl` per repeat):
- 15.63
- 11.17
- 17.06
- 15.94
- 14.43
- 11.18
- 9.57
- 12.66
- 16.32
- 13.79

Stored raw prose per repeat (for later recomputation of other metrics without spending fresh quota):
<details><summary>repeat 1 (FKGL 15.63)</summary>

The "Validate Python e2e" pipeline, defined in `tests\fixtures\setup_python_test.yml` as a GitHub Actions workflow, runs automatically on every push to the `main` branch and on every pull request, excluding changes to markdown files. It also executes on a daily schedule at 03:30 UTC and can be triggered manually.

This pipeline consists of 14 sequential jobs, each running across a matrix of operating system and Python version combinations. The initial jobs, `setup-versions-from-manifest`, `setup-versions-from-file`, `setup-versions-from-file-without-parameter`, `setup-versions-from-standard-pyproject-file`, `setup-versions-from-poetry-pyproject-file`, `setup-versions-from-pipfile-with-python_version`, and `setup-versions-from-pipfile-with-python_full_version`, all involve checking out the repository, building or setting up a Python version, checking its path, validating the version, and running simple code. These jobs vary in how the Python version is specified or obtained, with most running across 35 or 28 combinations of OS and Python.

Following these, the `setup-versions-from-tool-versions-file` job sets up Python using a `.tool-versions` file across up to 28 combinations, with one excluded. Three jobs, `setup-pre-release-version-from-manifest`, `setup-dev-version`, and `setup-prerelease-version`, focus on setting up specific Python versions like `3.14.0-alpha.6`, `3.14-dev`, and `3.14` respectively, each running across 7 OS combinations. The `setup-versions-noenv` job sets up Python and runs simple code without environment variables across 35 combinations. Finally, the `check-latest` job and `setup-python-multiple-python-versions` job both use `actions/checkout@v6`, set up Python, and validate the version, with `check-latest` running across 35 OS and Python version combinations, and `setup-python-multiple-python-versions` across 7 OS combinations.

</details>
<details><summary>repeat 2 (FKGL 11.17)</summary>

The "Validate Python e2e" pipeline, sourced from `tests\fixtures\setup_python_test.yml` in GitHub Actions, is designed to validate end-to-end Python setups. It is triggered on every push to the main branch, excluding markdown files, and on every pull request, also excluding markdown files. Additionally, the pipeline runs on a daily schedule at 03:30 UTC and can be triggered manually.

This pipeline comprises 14 sequential jobs, many of which execute across a matrix of operating systems and Python versions. The primary goal of these jobs is to set up and validate Python environments under various conditions. Common steps across many jobs include checking out the repository, setting up a specified Python version, verifying the Python path, validating the installed version, and running simple code.

Specific jobs test different methods of Python version management. These include setting up versions from a manifest, from a version file (with or without parameters), from standard and Poetry `pyproject.toml` files, from `.tool-versions` files, and from Pipfiles (using either `python_version` or `python_full_version`). The pipeline also validates pre-release versions (e.g., `3.14.0-alpha.6`), development versions (`3.14-dev`), and general pre-release versions (`3.14`). Further jobs test Python setup without environment variables, check for the latest Python versions, and handle scenarios involving multiple Python versions.

</details>
<details><summary>repeat 3 (FKGL 17.06)</summary>

The "Validate Python e2e" pipeline, defined in `tests\fixtures\setup_python_test.yml` as a GitHub Actions workflow, runs automatically on every push and pull request to the `main` branch, excluding changes to markdown files. It also executes on a daily schedule (30 3 * * *) and can be triggered manually.

This pipeline comprises 14 sequential jobs, primarily designed to set up and validate various Python versions across different operating systems. Many jobs follow a pattern of checking out the repository, building or setting up a specific Python version, checking its path, validating the version, and running simple code. For instance, the first five jobs (`setup-versions-from-manifest`, `setup-versions-from-file`, `setup-versions-from-file-without-parameter`, `setup-versions-from-standard-pyproject-file`, `setup-versions-from-poetry-pyproject-file`) each run with 35 combinations of OS and Python.

Further jobs test specific scenarios: `setup-versions-from-tool-versions-file` uses a `.tool-versions` file, while `setup-versions-from-pipfile-with-python_version` and `setup-versions-from-pipfile-with-python_full_version` handle Pipfile-based versioning. Dedicated jobs like `setup-pre-release-version-from-manifest`, `setup-dev-version`, and `setup-prerelease-version` validate pre-release and development Python versions, each running with 7 OS combinations.

The `setup-versions-noenv` job checks Python setup without environment variables, running with 35 combinations. The pipeline concludes with `check-latest` and `setup-python-multiple-python-versions` jobs, which set up Python and validate the latest version, using `actions/checkout@v6`. `check-latest` runs with 35 combinations, and `setup-python-multiple-python-versions` runs with 7 combinations.

</details>
<details><summary>repeat 4 (FKGL 15.94)</summary>

The "Validate Python e2e" pipeline, sourced from `tests\fixtures\setup_python_test.yml` in GitHub Actions, is triggered by pushes to the `main` branch and pull requests, with both excluding changes to markdown files. It also runs on a daily schedule at 03:30 UTC and can be initiated manually.

This pipeline executes 14 sequential jobs. Many of these jobs run across a matrix of operating system and Python version combinations, with the number of combinations varying from 7 to 35 depending on the job. The initial jobs, `setup-versions-from-manifest`, `setup-versions-from-file`, `setup-versions-from-file-without-parameter`, `setup-versions-from-standard-pyproject-file`, `setup-versions-from-poetry-pyproject-file`, `setup-versions-from-pipfile-with-python_version`, and `setup-versions-from-pipfile-with-python_full_version`, are designed to set up and validate Python versions using various configuration sources. These jobs typically involve checking out the repository, potentially building a version file, setting up Python, checking the Python path, validating the version, and running simple code. The `setup-versions-from-tool-versions-file` job specifically uses a `.tool-versions` file for Python setup.

The pipeline also includes jobs to test specific Python version scenarios. `setup-pre-release-version-from-manifest`, `setup-dev-version`, and `setup-prerelease-version` focus on setting up pre-release or development Python versions. The `setup-versions-noenv` job sets up Python without environment variables. Finally, `check-latest` sets up Python and verifies the latest version, while `setup-python-multiple-python-versions` handles scenarios involving multiple Python versions. All these jobs involve checking out the repository and performing Python setup, validation, and simple code execution steps.

</details>
<details><summary>repeat 5 (FKGL 14.43)</summary>

The "Validate Python e2e" pipeline, defined in `tests\fixtures\setup_python_test.yml` as a GitHub Actions workflow, runs automatically on every push to the main branch and every pull request, excluding changes to markdown files. It also runs on a daily schedule at 03:30 UTC and can be triggered manually.

This pipeline executes a series of jobs designed to set up and validate Python environments under various configurations. The initial jobs, `setup-versions-from-manifest`, `setup-versions-from-file`, `setup-versions-from-file-without-parameter`, `setup-versions-from-standard-pyproject-file`, `setup-versions-from-poetry-pyproject-file`, `setup-versions-from-pipfile-with-python_version`, and `setup-versions-from-pipfile-with-python_full_version`, each check out the repository, build a version file (where applicable), set up a specified Python version, check its path, validate the version, and run simple code. These jobs run across a matrix of 35 or 28 combinations of operating systems and Python versions.

Further jobs include `setup-versions-from-tool-versions-file`, which builds a `.tool-versions` file and sets up Python using it across up to 28 OS and Python combinations. Specific pre-release and development versions are tested by `setup-pre-release-version-from-manifest` (3.14.0-alpha.6), `setup-dev-version` (3.14-dev), and `setup-prerelease-version` (3.14), each running across 7 OS combinations. The `setup-versions-noenv` job sets up Python, checks its version, and runs simple code for 35 OS and Python combinations. Finally, `check-latest` and `setup-python-multiple-python-versions` jobs check out the repository, set up Python, and validate the version, running across 35 or 7 OS and Python combinations respectively.

</details>
<details><summary>repeat 6 (FKGL 11.18)</summary>

The "Validate Python e2e" pipeline is a GitHub Actions workflow sourced from `tests\fixtures\setup_python_test.yml`. It is triggered by every push to the `main` branch, excluding paths ending in `.md`, and by every pull request, also excluding paths ending in `.md`. It additionally runs on a schedule (30 3 * * *) and can be triggered manually.

This pipeline executes 14 sequential jobs, all focused on setting up and validating various Python environments. Most jobs run across a matrix of operating systems and Python versions, with up to 35 combinations. The jobs test different methods of Python version management, including setting up versions from a manifest, from a version file (with and without parameters), from standard and Poetry `pyproject.toml` files, from a `.tool-versions` file, and from `Pipfile`s using `python_version` or `python_full_version`.

Further jobs validate specific Python versions such as pre-release, dev, and prerelease versions. The pipeline also includes jobs to check setups without environment variables, verify the latest Python versions, and test scenarios with multiple Python versions. Many of these jobs involve steps like checking out the repository, setting up Python, checking the Python path, validating the version, and running simple code.

</details>
<details><summary>repeat 7 (FKGL 9.57)</summary>

The "Validate Python e2e" pipeline, sourced from tests\fixtures\setup_python_test.yml as a GitHub Actions workflow, is designed to validate Python end-to-end setups. It is triggered by pushes to the main branch, excluding markdown files, and by pull requests, also excluding markdown files. Additionally, it runs on a daily schedule at 03:30 UTC and can be triggered manually.

This pipeline consists of 14 sequential jobs, many of which execute across a matrix of operating systems and Python versions. The common steps across these jobs include checking out the repository, setting up a Python environment, verifying the Python path, validating the installed version, and running simple code.

The jobs specifically test various methods of Python version management. These include setting up versions from a manifest, from a version file (with or without a parameter), from standard pyproject.toml, from poetry pyproject.toml, from a .tool-versions file, and from a Pipfile using either `python_version` or `python_full_version`. Other jobs focus on setting up specific versions such as `3.14.0-alpha.6`, `3.14-dev`, or `3.14`, or test setups without environment variables. The pipeline also includes jobs to check for the latest Python version and to set up multiple Python versions.

</details>
<details><summary>repeat 8 (FKGL 12.66)</summary>

The "Validate Python e2e" pipeline, defined in `tests\fixtures\setup_python_test.yml` for GitHub Actions, runs automatically on every push to the main branch and every pull request, excluding changes to markdown files. It also runs on a schedule (at 03:30 UTC daily) and can be triggered manually.

This pipeline consists of 14 sequential jobs designed to set up and validate Python environments under various conditions. Most jobs execute across a matrix of operating systems and Python versions, with many involving steps to checkout code, set up Python, check the Python path, validate the installed version, and run simple code.

The jobs specifically test different methods of defining Python versions, including those specified in a manifest, various version files (with and without parameters), standard `pyproject.toml`, Poetry `pyproject.toml`, `.tool-versions` files, and Pipfile (using both `python_version` and `python_full_version`). Additionally, the pipeline validates the setup of pre-release, development, and specific Python versions like 3.14. It also includes jobs to test Python setup without environment variables, to check the latest available Python version, and to set up multiple Python versions.

</details>
<details><summary>repeat 9 (FKGL 16.32)</summary>

The 'Validate Python e2e' pipeline, defined in `tests\fixtures\setup_python_test.yml` as a GitHub Actions workflow, is designed to run under several conditions. It triggers on every push to the `main` branch, excluding changes to markdown files, and also on every pull request, similarly excluding markdown file paths. Additionally, it runs on a schedule at 03:30 UTC daily and can be triggered manually.

The pipeline executes a series of jobs in a defined order, primarily focused on setting up and validating Python environments. The initial jobs, `setup-versions-from-manifest`, `setup-versions-from-file`, `setup-versions-from-file-without-parameter`, `setup-versions-from-standard-pyproject-file`, `setup-versions-from-poetry-pyproject-file`, `setup-versions-from-tool-versions-file`, `setup-versions-from-pipfile-with-python_version`, and `setup-versions-from-pipfile-with-python_full_version`, each run on a matrix of operating systems and Python versions, with 28 to 35 combinations. These jobs typically involve checking out the repository, building or setting up a version file, setting up Python, checking the Python path, validating the version, and running simple code.

Following these, the pipeline includes jobs to specifically test pre-release and development Python versions: `setup-pre-release-version-from-manifest` (for 3.14.0-alpha.6), `setup-dev-version` (for 3.14-dev), and `setup-prerelease-version` (for 3.14). These jobs run on a matrix of 7 operating system combinations, performing similar checkout, setup, and validation steps. Further jobs include `setup-versions-noenv`, which sets up Python and runs simple code without environment variables across 35 OS and Python combinations, and `check-latest`, which sets up and validates the latest Python version across 35 OS and Python-version combinations. Finally, `setup-python-multiple-python-versions` checks out, sets up, and validates multiple Python versions across 7 operating system combinations.

</details>
<details><summary>repeat 10 (FKGL 13.79)</summary>

The "Validate Python e2e" pipeline, defined in `tests\fixtures\setup_python_test.yml` as a GitHub Actions workflow, is designed to validate Python end-to-end setups. This pipeline runs automatically on every push to the `main` branch and on every pull request, excluding changes to markdown files. It also executes on a daily schedule at 03:30 UTC and can be triggered manually.

The pipeline consists of 14 sequential jobs. The initial jobs, `setup-versions-from-manifest`, `setup-versions-from-file`, `setup-versions-from-file-without-parameter`, `setup-versions-from-standard-pyproject-file`, `setup-versions-from-poetry-pyproject-file`, `setup-versions-from-pipfile-with-python_version`, and `setup-versions-from-pipfile-with-python_full_version`, all run on `matrix.os` across 28 or 35 combinations of operating systems and Python versions. These jobs typically involve checking out the repository, building or setting up a version file, running `setup-python` with the specified `matrix.python` version, checking the Python path, validating the version, and executing simple code. The `setup-versions-from-tool-versions-file` job similarly checks out, builds a tool versions file, and runs `setup-python` using `.tool-versions` for up to 28 combinations, with one combination excluded.

Further jobs focus on specific Python versions or configurations. `setup-pre-release-version-from-manifest`, `setup-dev-version`, and `setup-prerelease-version` each run on `matrix.os` for 7 combinations, checking out the repository, setting up Python with specific versions like `3.14.0-alpha.6`, `3.14-dev`, or `3.14`, then checking the Python path, validating the version, and running simple code. The `setup-versions-noenv` job, running for 35 combinations, checks out, sets up Python, reports the Python version, and runs simple code.

Finally, the `check-latest` job, running for 35 combinations of operating systems and Python versions, uses `actions/checkout@v6`, sets up Python, checks for the latest version, and validates it. Similarly, the `setup-python-multiple-python-versions` job, for 7 combinations, also uses `actions/checkout@v6`, sets up Python, checks for the latest version, and validates it.

</details>

### rust_ci.yml — PR 2 showed a 0.31, essentially flat, control

Raw N=10 FKGL values (`fkgl` per repeat):
- 10.29
- 11.95
- 12.53
- 12.31
- 12.01
- 12.51
- 12.96
- 11.47
- 12.55
- 12.19

Stored raw prose per repeat (for later recomputation of other metrics without spending fresh quota):
<details><summary>repeat 1 (FKGL 10.29)</summary>

This CI pipeline, defined in `tests\fixtures\rust_ci.yml` as a GitHub Actions workflow, has permissions to read repository contents and write packages. It uses a concurrency group named `${{ github.workflow }}-${{ ((github.ref == 'refs/heads/try-perf' || github.ref == 'refs/heads/automation/bors/try') && github.sha) || github.ref }}` and cancels any in-progress runs within this group. The pipeline triggers on every push to the `automation/bors/auto`, `automation/bors/try`, or `try-perf` branches, and also on every pull request targeting any branch.

The pipeline executes three jobs in sequence. The first job, `calculate_matrix`, runs on `ubuntu-24.04-arm` and involves three steps: checking out the source code, testing `citool`, and calculating the CI job matrix. Following this, the `job` job runs on `${{ matrix.os }}` with matrix combinations determined at runtime. This job has 33 steps, including installing Cargo in AWS CodeBuild, disabling Git CRLF conversion, checking out the source code, freeing up disk space, printing disk usage, configuring the pull request for error messages, adding extra environment variables, ensuring the channel matches the target branch, collecting CPU statistics, showing the current environment, and 23 additional steps. Its deployment environment is `bors` when the repository is `rust-lang/rust` and the branch is `try-perf`, `automation/bors/try`, or `automation/bors/auto`.

The final job, `outcome`, runs on `ubuntu-24.04` after both `calculate_matrix` and `job` have completed. This job executes only if the condition `${{ needs.calculate_matrix.outputs.run_type == 'auto' }}` is met. It has two steps: checking out the source code and publishing toolstate. Its deployment environment is `bors` when the repository is `rust-lang/rust`. The pipeline requires several secrets: `TOOLSTATE_REPO_ACCESS_TOKEN`, `GITHUB_TOKEN` (used in the `job` job), `CACHES_AWS_ACCESS_KEY_ID` and `CACHES_AWS_SECRET_ACCESS_KEY` (both used in the `job` job's "run the build" step), `ARTIFACTS_AWS_ACCESS_KEY_ID` and `ARTIFACTS_AWS_SECRET_ACCESS_KEY` (both used in the `job` job's "upload artifacts to S3" step), and `DATADOG_API_KEY` (used in the `job` job's "upload job metrics to DataDog" step).

</details>
<details><summary>repeat 2 (FKGL 11.95)</summary>

This CI pipeline, defined in `tests\fixtures\rust_ci.yml` as a GitHub Actions workflow, operates with `contents: read` and `packages: write` permissions. It runs on every push to the `automation/bors/auto`, `automation/bors/try`, or `try-perf` branches, and on every pull request targeting any branch. The pipeline manages concurrency by grouping runs under a specific name derived from the workflow, ref, and SHA, canceling any in-progress runs within that same group.

The pipeline consists of three jobs. First, `calculate_matrix` runs on `ubuntu-24.04-arm` to checkout the source code, test `citool`, and calculate the CI job matrix. Following this, the main `job` executes on an OS determined by the matrix at runtime, comprising 33 steps. These steps include installing cargo in AWS CodeBuild, disabling git crlf conversion, checking out the source code, freeing up disk space, printing disk usage, configuring the PR for error messages, adding extra environment variables, ensuring the channel matches the target branch, collecting CPU statistics, and showing the current environment, along with 23 additional steps. Its deployment environment is `bors` if the repository is `rust-lang/rust` and the branch is `try-perf`, `automation/bors/try`, or `automation/bors/auto`; otherwise, it is empty.

Finally, the `outcome` job runs on `ubuntu-24.04` after both `calculate_matrix` and `job` have completed, but only if the `run_type` output from `calculate_matrix` is 'auto'. This job checks out the source code and publishes toolstate. Its deployment environment is `bors` if the repository is `rust-lang/rust`; otherwise, it is empty. The pipeline requires several secrets: `TOOLSTATE_REPO_ACCESS_TOKEN`, `GITHUB_TOKEN` (used in the `job` job), `CACHES_AWS_ACCESS_KEY_ID` and `CACHES_AWS_SECRET_ACCESS_KEY` (both used in the `job` job's "run the build" step), `ARTIFACTS_AWS_ACCESS_KEY_ID` and `ARTIFACTS_AWS_SECRET_ACCESS_KEY` (both used in the `job` job's "upload artifacts to S3" step), and `DATADOG_API_KEY` (used in the `job` job's "upload job metrics to DataDog" step).

</details>
<details><summary>repeat 3 (FKGL 12.53)</summary>

This CI pipeline, defined in `tests\fixtures\rust_ci.yml` as a GitHub Actions workflow, operates with `contents: read` and `packages: write` permissions. It triggers on every push to the `automation/bors/auto`, `automation/bors/try`, or `try-perf` branches, and on every pull request targeting any branch. Concurrency is managed by grouping runs based on the workflow and a dynamic reference/SHA, canceling any in-progress runs within the same group.

The pipeline begins with the `calculate_matrix` job, which runs on `ubuntu-24.04-arm`. This job performs three steps: checking out the source code, testing `citool`, and calculating the CI job matrix. Following this, the `job` job executes on an OS determined by the runtime matrix, consisting of 33 steps. This job's deployment environment is `bors` when the repository is `rust-lang/rust` and the branch is `try-perf`, `automation/bors/try`, or `automation/bors/auto`. Its steps include installing cargo in AWS CodeBuild, disabling git crlf conversion, checking out the source code, freeing up and printing disk usage, configuring the PR for error messages, adding extra environment variables, ensuring the channel matches the target branch, collecting CPU statistics, and showing the current environment, along with 23 additional steps.

Finally, the `outcome` job runs on `ubuntu-24.04` after both `calculate_matrix` and `job` have completed. This job executes only if the `run_type` output from `calculate_matrix` is `auto`, and its deployment environment is `bors` if the repository is `rust-lang/rust`. It involves two steps: checking out the source code and publishing toolstate. The pipeline requires several secrets: `TOOLSTATE_REPO_ACCESS_TOKEN`, `GITHUB_TOKEN` (used in the `job` job), `CACHES_AWS_ACCESS_KEY_ID` and `CACHES_AWS_SECRET_ACCESS_KEY` (used in the `job` job's "run the build" step), `ARTIFACTS_AWS_ACCESS_KEY_ID` and `ARTIFACTS_AWS_SECRET_ACCESS_KEY` (used in the `job` job's "upload artifacts to S3" step), and `DATADOG_API_KEY` (used in the `job` job's "upload job metrics to DataDog" step).

</details>
<details><summary>repeat 4 (FKGL 12.31)</summary>

This CI pipeline, defined in `tests\fixtures\rust_ci.yml` as a GitHub Actions workflow, operates with `contents: read` and `packages: write` permissions. It manages concurrency by grouping runs based on the workflow, ref, and SHA, canceling in-progress runs within the same group. The pipeline is triggered by pushes to the `automation/bors/auto`, `automation/bors/try`, or `try-perf` branches, and also by any pull request targeting any branch.

The pipeline begins with the `calculate_matrix` job, which executes on `ubuntu-24.04-arm`. This job performs three steps: checking out the source code, testing `citool`, and calculating the CI job matrix. Following this, the main `job` runs on an operating system determined by the runtime matrix, comprising 33 steps. This job's deployment environment is set to `bors` under specific conditions related to the repository and branch. Its steps include installing cargo in AWS CodeBuild, disabling git crlf conversion, checking out the source code, freeing up disk space, printing disk usage, configuring the PR for error messages, adding extra environment variables, ensuring the channel matches the target branch, collecting CPU statistics, showing the current environment, and 23 additional steps.

Finally, the `outcome` job runs on `ubuntu-24.04` after both `calculate_matrix` and `job` have completed, but only if the `run_type` output from `calculate_matrix` is 'auto'. Its deployment environment is `bors` if the repository is `rust-lang/rust`. This job involves two steps: checking out the source code and publishing toolstate. The pipeline requires several secrets: `TOOLSTATE_REPO_ACCESS_TOKEN`, `GITHUB_TOKEN` (used in the `job` job), `CACHES_AWS_ACCESS_KEY_ID` and `CACHES_AWS_SECRET_ACCESS_KEY` (used in the `run the build` step of the `job` job), `ARTIFACTS_AWS_ACCESS_KEY_ID` and `ARTIFACTS_AWS_SECRET_ACCESS_KEY` (used in the `upload artifacts to S3` step of the `job` job), and `DATADOG_API_KEY` (used in the `upload job metrics to DataDog` step of the `job` job).

</details>
<details><summary>repeat 5 (FKGL 12.01)</summary>

This CI pipeline, defined in `tests\fixtures\rust_ci.yml` as a GitHub Actions workflow, operates with `contents: read` and `packages: write` permissions. It manages concurrency by grouping runs based on the workflow, reference, and SHA, canceling any in-progress runs within the same group. The pipeline is triggered by every push to the `automation/bors/auto`, `automation/bors/try`, or `try-perf` branches, and also by every pull request targeting any branch.

The pipeline executes three jobs in sequence. First, the `calculate_matrix` job runs on `ubuntu-24.04-arm` and includes three steps: checking out the source code, testing `citool`, and calculating the CI job matrix. Next, the `job` job runs on an operating system determined at runtime by the matrix, after `calculate_matrix` completes. This job has 33 steps, and its deployment environment is `bors` if the repository is `rust-lang/rust` and the branch is `try-perf`, `automation/bors/try`, or `automation/bors/auto`. Its steps include installing cargo in AWS CodeBuild, disabling git crlf conversion, checking out the source code, freeing up disk space, printing disk usage, configuring the pull request for error messages, adding extra environment variables, ensuring the channel matches the target branch, collecting CPU statistics, showing the current environment, and 23 more steps.

Finally, the `outcome` job runs on `ubuntu-24.04` after both `calculate_matrix` and `job` have finished. This job only proceeds if the `run_type` output from `calculate_matrix` is `auto`, and its deployment environment is `bors` if the repository is `rust-lang/rust`. It performs two steps: checking out the source code and publishing toolstate. The pipeline requires several secrets: `TOOLSTATE_REPO_ACCESS_TOKEN`, `GITHUB_TOKEN` (used in the `job` job), `CACHES_AWS_ACCESS_KEY_ID` and `CACHES_AWS_SECRET_ACCESS_KEY` (both used in the `job` job's "run the build" step), `ARTIFACTS_AWS_ACCESS_KEY_ID` and `ARTIFACTS_AWS_SECRET_ACCESS_KEY` (both used in the `job` job's "upload artifacts to S3" step), and `DATADOG_API_KEY` (used in the `job` job's "upload job metrics to DataDog" step).

</details>
<details><summary>repeat 6 (FKGL 12.51)</summary>

The CI pipeline, defined in `tests\fixtures\rust_ci.yml` as a GitHub Actions workflow, operates with `contents: read` and `packages: write` permissions. It manages concurrency by grouping runs based on the workflow, ref, and SHA, canceling any in-progress runs within the same group. This pipeline is triggered by every push to the `automation/bors/auto`, `automation/bors/try`, or `try-perf` branches, and also by every pull request targeting any branch.

The pipeline begins with the `calculate_matrix` job, which runs on `ubuntu-24.04-arm`. This job performs three steps: checking out the source code, testing `citool`, and calculating the CI job matrix. Following this, the `job` job executes on an OS determined by the runtime matrix, consisting of 33 steps. This job runs after `calculate_matrix`, and its deployment environment is `bors` if the repository is `rust-lang/rust` and the branch is `try-perf`, `automation/bors/try`, or `automation/bors/auto`. Its steps include installing cargo in AWS CodeBuild, disabling git crlf conversion, checking out the source code, freeing up disk space, printing disk usage, configuring the PR for error messages, adding extra environment variables, ensuring the channel matches the target branch, collecting CPU statistics, and showing the current environment, along with 23 additional steps.

Finally, the `outcome` job runs on `ubuntu-24.04` after both `calculate_matrix` and `job` have completed, but only if the `run_type` output from `calculate_matrix` is 'auto'. Its deployment environment is `bors` if the repository is `rust-lang/rust`. This job has two steps: checking out the source code and publishing toolstate. The pipeline requires several secrets: `TOOLSTATE_REPO_ACCESS_TOKEN`, `GITHUB_TOKEN` (used in the `job` job), `CACHES_AWS_ACCESS_KEY_ID` and `CACHES_AWS_SECRET_ACCESS_KEY` (both used in the `run the build` step of the `job` job), `ARTIFACTS_AWS_ACCESS_KEY_ID` and `ARTIFACTS_AWS_SECRET_ACCESS_KEY` (both used in the `upload artifacts to S3` step of the `job` job), and `DATADOG_API_KEY` (used in the `upload job metrics to DataDog` step of the `job` job).

</details>
<details><summary>repeat 7 (FKGL 12.96)</summary>

This CI pipeline, defined in `tests\fixtures\rust_ci.yml` as a GitHub Actions workflow, operates with `contents: read` and `packages: write` permissions. It manages concurrency by grouping runs based on the workflow, ref, and SHA, canceling any in-progress runs within the same group. The pipeline is triggered by every push to the `automation/bors/auto`, `automation/bors/try`, or `try-perf` branches, and by every pull request targeting any branch.

The pipeline starts with the `calculate_matrix` job, which runs on `ubuntu-24.04-arm`. This job performs three steps: checking out the source code, testing `citool`, and calculating the CI job matrix. Following this, the `job` job executes on an operating system determined by the runtime matrix, performing 33 steps. These steps include installing cargo in AWS CodeBuild, disabling git crlf conversion, checking out the source code, freeing up and printing disk usage, configuring the pull request for error messages, adding extra environment variables, ensuring the channel matches the target branch, collecting CPU statistics, and showing the current environment, among 23 other steps. Its deployment environment is `bors` when the repository is `rust-lang/rust` and the branch is `try-perf`, `automation/bors/try`, or `automation/bors/auto`.

Finally, the `outcome` job runs on `ubuntu-24.04` after both `calculate_matrix` and `job` have completed, but only if the `run_type` output from `calculate_matrix` is 'auto'. This job checks out the source code and publishes toolstate, with its deployment environment being `bors` if the repository is `rust-lang/rust`. The pipeline requires several secrets: `TOOLSTATE_REPO_ACCESS_TOKEN`, `GITHUB_TOKEN` (used by the `job` job), `CACHES_AWS_ACCESS_KEY_ID` and `CACHES_AWS_SECRET_ACCESS_KEY` (both used in the `run the build` step of the `job` job), `ARTIFACTS_AWS_ACCESS_KEY_ID` and `ARTIFACTS_AWS_SECRET_ACCESS_KEY` (both used in the `upload artifacts to S3` step of the `job` job), and `DATADOG_API_KEY` (used in the `upload job metrics to DataDog` step of the `job` job).

</details>
<details><summary>repeat 8 (FKGL 11.47)</summary>

This CI pipeline, defined in `tests\fixtures\rust_ci.yml` as a GitHub Actions workflow, operates with `contents: read` and `packages: write` permissions. It triggers on every push to the `automation/bors/auto`, `automation/bors/try`, or `try-perf` branches, and on every pull request targeting any branch. Concurrency is managed by grouping runs based on the workflow, ref, and SHA, canceling any in-progress runs within the same group.

This pipeline executes three jobs in sequence. The first job, `calculate_matrix`, runs on `ubuntu-24.04-arm` and involves three steps: checking out the source code, testing `citool`, and calculating the CI job matrix. Following this, the `job` job runs on an operating system determined by the runtime matrix. This job has 33 steps, including installing cargo in AWS CodeBuild, disabling git crlf conversion, checking out the source code, freeing up and printing disk usage, configuring the PR for error messages, adding extra environment variables, ensuring the channel matches the target branch, collecting CPU statistics, showing the current environment, and 23 additional steps. The deployment environment for this job is 'bors' when specific repository and branch conditions are met.

The final job, `outcome`, runs on `ubuntu-24.04` after both `calculate_matrix` and `job` have completed, but only if `needs.calculate_matrix.outputs.run_type` is 'auto'. It performs two steps: checking out the source code and publishing toolstate. Its deployment environment is 'bors' under specific repository conditions. The pipeline requires several secrets: `TOOLSTATE_REPO_ACCESS_TOKEN`, `GITHUB_TOKEN` (used in the `job` job), `CACHES_AWS_ACCESS_KEY_ID` and `CACHES_AWS_SECRET_ACCESS_KEY` (used in the `job` job's "run the build" step), `ARTIFACTS_AWS_ACCESS_KEY_ID` and `ARTIFACTS_AWS_SECRET_ACCESS_KEY` (used in the `job` job's "upload artifacts to S3" step), and `DATADOG_API_KEY` (used in the `job` job's "upload job metrics to DataDog" step).

</details>
<details><summary>repeat 9 (FKGL 12.55)</summary>

This CI pipeline, defined in `tests\fixtures\rust_ci.yml` for GitHub Actions, has permissions to read repository contents and write packages. It manages concurrency by grouping runs based on the workflow, ref, and SHA, canceling in-progress runs within the same group. The pipeline is triggered by every push to the `automation/bors/auto`, `automation/bors/try`, or `try-perf` branches, and also by every pull request targeting any branch.

The pipeline executes three jobs in sequence. First, `calculate_matrix` runs on `ubuntu-24.04-arm` and involves three steps: checking out the source code, testing `citool`, and calculating the CI job matrix. Following this, the `job` job runs on an operating system determined by the runtime matrix, after `calculate_matrix`. This job consists of 33 steps, including installing cargo in AWS CodeBuild, disabling git crlf conversion, checking out the source code, freeing up and printing disk usage, configuring the pull request for error messages, adding extra environment variables, ensuring the channel matches the target branch, collecting CPU statistics, showing the current environment, and 23 additional steps. This job runs in a `bors` deployment environment if the repository is `rust-lang/rust` and the branch is `try-perf`, `automation/bors/try`, or `automation/bors/auto`; otherwise, the environment is empty.

Finally, the `outcome` job runs on `ubuntu-24.04` after both `calculate_matrix` and `job`, but only if the `run_type` output from `calculate_matrix` is 'auto'. This job has two steps: checking out the source code and publishing toolstate. It also runs in a `bors` deployment environment if the repository is `rust-lang/rust`; otherwise, the environment is empty. The pipeline requires several secrets: `TOOLSTATE_REPO_ACCESS_TOKEN`, `GITHUB_TOKEN` (used in the `job` job), `CACHES_AWS_ACCESS_KEY_ID` and `CACHES_AWS_SECRET_ACCESS_KEY` (both used in the `run the build` step of the `job` job), `ARTIFACTS_AWS_ACCESS_KEY_ID` and `ARTIFACTS_AWS_SECRET_ACCESS_KEY` (both used in the `upload artifacts to S3` step of the `job` job), and `DATADOG_API_KEY` (used in the `upload job metrics to DataDog` step of the `job` job).

</details>
<details><summary>repeat 10 (FKGL 12.19)</summary>

This CI pipeline, defined in `tests\fixtures\rust_ci.yml` as a GitHub Actions workflow, operates with `contents: read` and `packages: write` permissions. It manages concurrency by grouping runs using a key derived from the workflow, reference, and SHA, and cancels in-progress runs within that group. The pipeline is triggered by every push to the `automation/bors/auto`, `automation/bors/try`, or `try-perf` branches, and also by every pull request targeting any branch.

The pipeline begins with the `calculate_matrix` job, which runs on `ubuntu-24.04-arm`. This job checks out the source code, tests `citool`, and calculates the CI job matrix. Following this, the main `job` runs on an operating system determined by the runtime matrix, executing 33 steps after `calculate_matrix` completes. This job's deployment environment is `bors` if the repository is `rust-lang/rust` and the branch is `try-perf`, `automation/bors/try`, or `automation/bors/auto`. Key steps include installing Cargo in AWS CodeBuild, disabling Git CRLF conversion, checking out the source code, freeing up disk space, printing disk usage, configuring the PR for error messages, adding extra environment variables, ensuring the channel matches the target branch, collecting CPU statistics, and showing the current environment, along with 23 additional steps.

Finally, the `outcome` job runs on `ubuntu-24.04` after both `calculate_matrix` and `job` have completed. This job executes only if the `run_type` output from `calculate_matrix` is `auto`. Its deployment environment is `bors` if the repository is `rust-lang/rust`. The `outcome` job checks out the source code and publishes toolstate. To function, the pipeline requires several secrets: `TOOLSTATE_REPO_ACCESS_TOKEN`, `GITHUB_TOKEN` (used in the `job` job), `CACHES_AWS_ACCESS_KEY_ID` and `CACHES_AWS_SECRET_ACCESS_KEY` (both used in the `job` job's "run the build" step), `ARTIFACTS_AWS_ACCESS_KEY_ID` and `ARTIFACTS_AWS_SECRET_ACCESS_KEY` (both used in the `job` job's "upload artifacts to S3" step), and `DATADOG_API_KEY` (used in the `job` job's "upload job metrics to DataDog" step).

</details>
