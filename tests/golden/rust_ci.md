# CI

```text
Pipeline: CI
Source: tests/fixtures/rust_ci.yml (GitHub Actions)
Permissions: contents: read, packages: write
Concurrency: group ${{ github.workflow }}-${{ ((github.ref == 'refs/heads/try-perf' || github.ref == 'refs/heads/automation/bors/try') && github.sha) || github.ref }}; cancels in-progress runs

TRIGGERS
- Runs on every push to automation/bors/auto or automation/bors/try or try-perf branches
- Runs on every pull request targeting ** branch

JOBS (in order)
1. calculate_matrix — runs on ubuntu-24.04-arm; 3 steps
   - Checkout the source code
   - Test citool
   - Calculate the CI job matrix
2. job — runs on ${{ matrix.os }}; 33 steps; matrix: combinations determined at runtime; after calculate_matrix; deployment environment: ${{ ((github.repository == 'rust-lang/rust' && (github.ref == 'refs/heads/try-perf' || github.ref == 'refs/heads/automation/bors/try' || github.ref == 'refs/heads/automation/bors/auto')) && 'bors') || '' }}
   - Install cargo in AWS CodeBuild
   - disable git crlf conversion
   - checkout the source code
   - free up disk space
   - print disk usage
   - configure the PR in which the error message will be posted
   - add extra environment variables
   - ensure the channel matches the target branch
   - collect CPU statistics
   - show the current environment
   - ... and 23 more steps
3. outcome — runs on ubuntu-24.04; 2 steps; after calculate_matrix, job; condition: ${{ needs.calculate_matrix.outputs.run_type == 'auto' }}; deployment environment: ${{ (github.repository == 'rust-lang/rust' && 'bors') || '' }}
   - checkout the source code
   - publish toolstate

SECRETS REQUIRED
- TOOLSTATE_REPO_ACCESS_TOKEN
- GITHUB_TOKEN (used in job: job)
- CACHES_AWS_ACCESS_KEY_ID (used in job: job, step: run the build)
- CACHES_AWS_SECRET_ACCESS_KEY (used in job: job, step: run the build)
- ARTIFACTS_AWS_ACCESS_KEY_ID (used in job: job, step: upload artifacts to S3)
- ARTIFACTS_AWS_SECRET_ACCESS_KEY (used in job: job, step: upload artifacts to S3)
- DATADOG_API_KEY (used in job: job, step: upload job metrics to DataDog)
```

## Pipeline Diagram

```mermaid
flowchart LR
    trigger_0(["Push"])
    trigger_1(["Pull request"])
    calculate_matrix["calculate_matrix"]
    job["job [matrix: combinations determined at runtime]"]
    outcome["outcome [if: ${{ needs.calculate_matrix.outputs.run_type == 'auto' }}]"]
    trigger_0 --> calculate_matrix
    trigger_1 --> calculate_matrix
    calculate_matrix --> job
    calculate_matrix --> outcome
    job --> outcome
```
