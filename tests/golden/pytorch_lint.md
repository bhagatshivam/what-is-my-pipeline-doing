# Lint

```text
Pipeline: Lint
Source: tests/fixtures/pytorch_lint.yml (GitHub Actions)
Permissions: read-all
Concurrency: group ${{ github.workflow }}-${{ github.event.pull_request.number || github.sha }}-${{ github.event_name == 'workflow_dispatch' && github.run_id }}; cancels in-progress runs

AT A GLANCE
This workflow runs on pull requests, pushes to `main`, `release/*`, `landchecks/*`, and manual dispatch.
It contains 14 jobs: 6 with no declared dependencies, 8 depending on other jobs.
1 of 14 jobs use a build matrix; together these define 3 configured combinations.

WHEN IT RUNS
- Runs on every pull request except branch nightly
- Runs on every push to main or release/* or landchecks/* branches; with tag matching ciflow/pull/* or ciflow/trunk/*
- Can be triggered manually

EXECUTION SUMMARY
Independent jobs (no dependencies): get-label-type, get-changed-files, pr-sanity-checks, test_run_test, test_collect_env, doc-redirects-check
lintrunner-clang runs after get-label-type, get-changed-files
lintrunner-pyrefly runs after get-label-type, get-changed-files
lintrunner-noclang runs after get-label-type, get-changed-files
quick-checks runs after get-label-type
workflow-checks runs after get-label-type
toc runs after get-label-type
test-tools runs after get-label-type
link-check runs after get-label-type

IMPLEMENTATION DETAILS
1. get-label-type — delegates to reusable workflow pytorch/pytorch/.github/workflows/_runner-determinator.yml@main; condition: github.repository_owner == 'pytorch'
2. get-changed-files — delegates to reusable workflow ./.github/workflows/_get-changed-files.yml; condition: github.repository_owner == 'pytorch'
3. lintrunner-clang — delegates to reusable workflow ./.github/workflows/_lint.yml; after get-label-type, get-changed-files; condition: github.repository_owner == 'pytorch' && (
  needs.get-changed-files.outputs.changed-files == '*' ||
  contains(needs.get-changed-files.outputs.changed-files, '.h') ||
  contains(needs.get-changed-files.outputs.changed-files, '.cpp') ||
  contains(needs.get-changed-files.outputs.changed-files, '.cc') ||
  contains(needs.get-changed-files.outputs.changed-files, '.cxx') ||
  contains(needs.get-changed-files.outputs.changed-files, '.hpp') ||
  contains(needs.get-changed-files.outputs.changed-files, '.hxx') ||
  contains(needs.get-changed-files.outputs.changed-files, '.cu') ||
  contains(needs.get-changed-files.outputs.changed-files, '.cuh') ||
  contains(needs.get-changed-files.outputs.changed-files, '.mm') ||
  contains(needs.get-changed-files.outputs.changed-files, '.metal')
)

4. lintrunner-pyrefly — delegates to reusable workflow ./.github/workflows/_lint.yml; after get-label-type, get-changed-files; condition: github.repository_owner == 'pytorch' && (
  needs.get-changed-files.outputs.changed-files == '*' ||
  contains(needs.get-changed-files.outputs.changed-files, '.py') ||
  contains(needs.get-changed-files.outputs.changed-files, '.pyi')
)

5. lintrunner-noclang — delegates to reusable workflow ./.github/workflows/_lint.yml; after get-label-type, get-changed-files
6. quick-checks — delegates to reusable workflow ./.github/workflows/_lint.yml; after get-label-type; condition: github.repository_owner == 'pytorch'
7. pr-sanity-checks — runs on linux.24_04.4x; 2 steps; condition: ${{ github.event_name == 'pull_request' && !contains(github.event.pull_request.labels.*.name, 'skip-pr-sanity-checks') && github.repository_owner == 'pytorch' }}
   - Checkout PyTorch
   - PR size check (nonretryable)
8. workflow-checks — delegates to reusable workflow ./.github/workflows/_lint.yml; after get-label-type; condition: github.repository_owner == 'pytorch'
9. toc — delegates to reusable workflow ./.github/workflows/_lint.yml; after get-label-type; condition: github.repository_owner == 'pytorch'
10. test-tools — delegates to reusable workflow ./.github/workflows/_lint.yml; after get-label-type; condition: ${{ github.repository == 'pytorch/pytorch' }}
11. test_run_test — runs on linux.24_04.4x; 4 steps; condition: ${{ github.repository == 'pytorch/pytorch' }}
   - Checkout PyTorch
   - Setup Python 3.10
   - Install dependencies
   - Run run_test.py (nonretryable)
12. test_collect_env — runs on ${{ matrix.runner }}; 6 steps; matrix: 3 combinations (via include); condition: ${{ github.repository == 'pytorch/pytorch' }}
   - Checkout PyTorch
   - Get min python version
   - Setup Old Python version
   - Setup Min Python version
   - Install torch
   - Run collect_env.py (nonretryable)
13. link-check — delegates to reusable workflow ./.github/workflows/_link_check.yml; after get-label-type; condition: github.repository_owner == 'pytorch'
14. doc-redirects-check — runs on linux.24_04.4x; 2 steps; condition: github.event_name == 'pull_request' && github.repository_owner == 'pytorch'
   - Checkout PyTorch
   - Doc redirects check (nonretryable)

LINKED WORKFLOWS
- calls pytorch/pytorch/.github/workflows/_runner-determinator.yml@main
- calls ./.github/workflows/_get-changed-files.yml
- calls ./.github/workflows/_lint.yml
- calls ./.github/workflows/_link_check.yml
```

## Pipeline Diagram

```mermaid
flowchart LR
    get-label-type["get-label-type [if: github.repository_owner == 'pytorch']"]
    get-changed-files["get-changed-files [if: github.repository_owner == 'pytorch']"]
    lintrunner-clang["lintrunner-clang [if: github.repository_owner == 'pytorch' && (...]"]
    lintrunner-pyrefly["lintrunner-pyrefly [if: github.repository_owner == 'pytorch' && (...]"]
    lintrunner-noclang["lintrunner-noclang"]
    quick-checks["quick-checks [if: github.repository_owner == 'pytorch']"]
    pr-sanity-checks["pr-sanity-checks [if: ${{ github.event_name == 'pull_request' && !contains(github.event.pull_request.l...]"]
    workflow-checks["workflow-checks [if: github.repository_owner == 'pytorch']"]
    toc["toc [if: github.repository_owner == 'pytorch']"]
    test-tools["test-tools [if: ${{ github.repository == 'pytorch/pytorch' }}]"]
    test_run_test["test_run_test [if: ${{ github.repository == 'pytorch/pytorch' }}]"]
    test_collect_env["test_collect_env [matrix: 3 combinations (via include), if: ${{ github.repository == 'pytorch/pytorch' }}]"]
    link-check["link-check [if: github.repository_owner == 'pytorch']"]
    doc-redirects-check["doc-redirects-check [if: github.event_name == 'pull_request' && github.repository_owner == 'pytorch']"]
    get-label-type --> lintrunner-clang
    get-changed-files --> lintrunner-clang
    get-label-type --> lintrunner-pyrefly
    get-changed-files --> lintrunner-pyrefly
    get-label-type --> lintrunner-noclang
    get-changed-files --> lintrunner-noclang
    get-label-type --> quick-checks
    get-label-type --> workflow-checks
    get-label-type --> toc
    get-label-type --> test-tools
    get-label-type --> link-check
```
