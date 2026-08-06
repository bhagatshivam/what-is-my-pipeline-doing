# starlette (unified CI documentation)

<!-- llm-overview:start -->
## Overview

This GitHub Actions workflow, named `starlette (unified CI documentation)`, is located at `tests/fixtures/multi/starlette/.github/workflows`. It triggers on pushes to the `main` branch, pull requests targeting `main` or `**` branches, pushes with any tag, and can also be triggered manually. The pipeline consists of 8 jobs, with one job using a build matrix to define 5 different Python version combinations.

Four jobs run independently: `main_yml__tests`, `main_yml__docs-cloudflare-preview`, `publish_yml__build`, and `zizmor_yml__zizmor`. The `main_yml__tests` job checks out code, installs dependencies, runs linting, builds the package and docs, executes tests, and enforces coverage across 5 Python versions. The `main_yml__docs-cloudflare-preview` job, which requires `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`, builds documentation and comments a preview URL for pull requests from the same repository. The `publish_yml__build` job checks out code, installs dependencies, builds the package and docs, and uploads package distributions and documentation. The `zizmor_yml__zizmor` job checks out the repository and runs `zizmor 🌈`.

The remaining four jobs have dependencies. `main_yml__check` runs after `main_yml__tests` to decide job success or failure. After `publish_yml__build`, three jobs execute: `publish_yml__pypi-publish` publishes the distribution to PyPI if the build succeeds and the ref is a tag; `publish_yml__docs-publish` deploys documentation to GitHub Pages; and `publish_yml__docs-cloudflare` uses `cloudflare/wrangler-action` after checking out code and downloading artifacts, requiring `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
<!-- llm-overview:end -->

```text
Pipeline: starlette (unified CI documentation)
Source: tests/fixtures/multi/starlette/.github/workflows (GitHub Actions)

AT A GLANCE
This workflow runs on pushes to `main`, pull requests, pushes, and manual dispatch.
It contains 8 jobs: 4 with no declared dependencies, 4 depending on other jobs.
1 of 8 jobs use a build matrix; together these define 5 configured combinations.

WHEN IT RUNS
- Runs on every push to main branch
- Runs on every pull request targeting main branch
- Runs on every push with tag matching *
- Can be triggered manually
- Runs on every push to main branch
- Runs on every pull request targeting ** branch

EXECUTION SUMMARY
Independent jobs (no dependencies): main_yml__tests, main_yml__docs-cloudflare-preview, publish_yml__build, zizmor_yml__zizmor
main_yml__check runs after main_yml__tests
publish_yml__pypi-publish runs after publish_yml__build
publish_yml__docs-publish runs after publish_yml__build
publish_yml__docs-cloudflare runs after publish_yml__build

IMPLEMENTATION DETAILS
1. main_yml__tests — runs on ubuntu-latest; 7 steps; matrix: 5 combinations (python-version)
   - actions/checkout
   - Install uv
   - Install dependencies
   - Run linting checks
   - Build package & docs
   - Run tests
   - Enforce coverage
2. main_yml__check — runs on ubuntu-latest; 1 step; after main_yml__tests; condition: always()
   - Decide whether the needed jobs succeeded or failed
3. main_yml__docs-cloudflare-preview — runs on ubuntu-latest; 6 steps; condition: github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository; permissions: contents: read, pull-requests: write
   - actions/checkout
   - Install uv
   - Install dependencies
   - Build docs
   - cloudflare/wrangler-action
   - Comment preview URL
4. publish_yml__build — runs on ubuntu-latest; 6 steps
   - actions/checkout
   - Install uv
   - Install dependencies
   - Build package & docs
   - Upload package distributions
   - Upload documentation
5. publish_yml__pypi-publish — runs on ubuntu-latest; 2 steps; after publish_yml__build; condition: success() && startsWith(github.ref, 'refs/tags/'); permissions: id-token: write
   - Download artifacts
   - Publish distribution 📦 to PyPI
6. publish_yml__docs-publish — runs on ubuntu-latest; 4 steps; after publish_yml__build; permissions: contents: read, pages: write, id-token: write
   - Configure GitHub Pages
   - Download artifacts
   - Upload Pages artifact
   - Deploy to GitHub Pages
7. publish_yml__docs-cloudflare — runs on ubuntu-latest; 3 steps; after publish_yml__build
   - actions/checkout
   - Download artifacts
   - cloudflare/wrangler-action
8. zizmor_yml__zizmor — runs on ubuntu-latest; 2 steps; permissions: security-events: write
   - Checkout repository
   - Run zizmor 🌈

SECRETS REQUIRED
- CLOUDFLARE_API_TOKEN (used in job: main_yml__docs-cloudflare-preview)
- CLOUDFLARE_API_TOKEN (used in job: main_yml__docs-cloudflare-preview, step: cloudflare/wrangler-action)
- CLOUDFLARE_ACCOUNT_ID (used in job: main_yml__docs-cloudflare-preview, step: cloudflare/wrangler-action)
- CLOUDFLARE_API_TOKEN (used in job: publish_yml__docs-cloudflare, step: cloudflare/wrangler-action)
- CLOUDFLARE_ACCOUNT_ID (used in job: publish_yml__docs-cloudflare, step: cloudflare/wrangler-action)
```

## Pipeline Diagram

```mermaid
flowchart LR
    main_yml__tests["main_yml__tests [matrix: 5 combinations (python-version)]"]
    main_yml__check["main_yml__check [if: always()]"]
    main_yml__docs-cloudflare-preview["main_yml__docs-cloudflare-preview [if: github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_...]"]
    publish_yml__build["publish_yml__build"]
    publish_yml__pypi-publish["publish_yml__pypi-publish [if: success() && startsWith(github.ref, 'refs/tags/')]"]
    publish_yml__docs-publish["publish_yml__docs-publish"]
    publish_yml__docs-cloudflare["publish_yml__docs-cloudflare"]
    zizmor_yml__zizmor["zizmor_yml__zizmor"]
    main_yml__tests --> main_yml__check
    publish_yml__build --> publish_yml__pypi-publish
    publish_yml__build --> publish_yml__docs-publish
    publish_yml__build --> publish_yml__docs-cloudflare
```

## Workflow Relationships

| Workflow file | Runs when | Job behaviour | Relationship |
| --- | --- | --- | --- |
| main_yml | pushes to `main` and pull requests | 3 jobs, 2 independent | independent |
| publish_yml | pushes and manual dispatch | 4 jobs, 1 independent | independent |
| zizmor_yml | pushes to `main` and pull requests | 1 job, 1 independent | independent |

Some workflow files share the exact same trigger. GitHub Actions gives no ordering between separately-triggered workflow runs — these run independently of each other, not in sequence, even though they fire on the same event:

- pushes to `main`: main_yml, zizmor_yml

