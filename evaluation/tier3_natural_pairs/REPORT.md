# Tier 3 — Natural-Pairs Comparison

Method 8 of `EVALUATION_PLAN.md` ("Natural-pairs comparison"): find repos that
already have human-written documentation describing their real CI setup, and
compare this tool's generated output against that documentation directly —
"real" documentation, written for actual developers, not written for the
purpose of this study. This directly satisfies the project brief's
"comparing... with documentation written by human developers" requirement,
without a recruitment dependency.

## Scope and candidate selection

Candidates were drawn from repos already used as dev fixtures or held-out
pipelines (workflow YAML already on hand, confirmed to parse cleanly) rather
than searched for blindly. Full investigation is in this conversation's prior
turn; summary: of 9 repos checked, 3 yielded genuine, verified CI-specific
documentation describing the *same* workflow file(s) already in this
project's fixtures — `scipy_linux`, `tox` (multi-fixture), `black`
(multi-fixture). The other 6 were ruled out, most instructively:
`vscode_pr`'s detailed docs describe Azure DevOps pipelines (a different CI
system — the same pitfall as the cpython buildbot case), `celery_python_package`'s
docs describe Travis CI/AppVeyor (stale, no longer the actual CI), and
`httpx_test_suite`'s docs describe a 3-separate-job CI shape that no longer
matches the current single-job `test-suite.yml` (doc/code drift, not a
different system, but the same disqualifying effect).

**Correction to the prior investigation turn**: that summary stated
`api.github.com` returns 403 in this environment. That was accurate for the
live call made in that turn. `evaluation/held_out_workflows/SOURCES.md`
separately documents a 400 from an earlier, unrelated session
("`api.github.com` returns 400 in this environment"). Both are genuine,
directly-observed results from their own point in time — this report doesn't
resolve them to one "correct" value, since they may simply reflect the
proxy's behavior varying across sessions or requests; the fresh observation
(403) is not overridden to match the older documented one (400).

**Read-only reuse, nothing modified**: `tests/fixtures/`, `tests/golden/`,
`evaluation/held_out_workflows/`, and existing Tier 4 material were read for
verification only. `scipy_linux`'s comparison reuses
`evaluation/tier4_scoring/scipy_linux.scoring.md`'s Condition A (= Condition
2, LLM-polished) and Condition C (= Condition 1, deterministic) verbatim,
already regenerated and current as of PR #57 (2026-08-22) — no new Gemini
call was needed for it. `tox` and `black` are Tool 2 (multi-pipeline) dev
fixtures with no existing LLM-polished output anywhere (their golden files
are deterministic-only, matching `check_repository`'s contract), so 2 new
live Gemini calls (`gemini-2.5-flash`, temperature 0.2) were made via
`tool2.multi_pipeline._build_documentation(path, use_llm=True)` — confirmed
identical deterministic output to the committed golden files first, then the
LLM-polished overview was generated fresh.

## Methodology

For each candidate, three comparison axes:

1. **Tool → human doc**: does the tool's output (deterministic and/or
   LLM-polished) correctly state what the human doc says, for facts both
   cover?
2. **Human doc → tool**: does the human doc contain real, verifiable facts
   the tool's output never surfaces? (Most such gaps are expected —
   behavioral/organizational knowledge not literally encoded in YAML
   structure isn't something this architecture claims to produce.)
3. **Contradictions**: does either source state something the other directly
   contradicts? This is the sharpest signal available in this tier —
   independently-authored ground truth, written by real maintainers for real
   purposes with no incentive to align with this project's schema, makes a
   contradiction found here a stronger validity signal than a hallucination
   caught against Tier 4's synthetic, self-authored checklists. Tier 4's
   checklists are pre-registered and bias-mitigated, but they were still
   written by this project's author specifically to be checkable against
   this tool's architecture; these human docs were written with no awareness
   this project would ever exist.

---

## Candidate 1 — `scipy_linux`

- **Human doc source**: scipy/scipy, `doc/source/dev/contributor/continuous_integration.rst`, saved verbatim at [`human_docs/scipy_linux.rst`](human_docs/scipy_linux.rst).
- **Tool output source**: `evaluation/tier4_scoring/scipy_linux.scoring.md`, Condition A (LLM-polished) and Condition C (deterministic) — reused verbatim, read-only.

### Tool's deterministic output (verbatim)

```text
Pipeline: Linux tests
Source: /home/user/what-is-my-pipeline-doing/evaluation/held_out_workflows/scipy_linux.yml (GitHub Actions)
Permissions: contents: read
Concurrency: group ${{ github.workflow }}-${{ github.head_ref || github.run_id }}; cancels in-progress runs

AT A GLANCE
This workflow runs on pushes to `main`, `maintenance/**` and pull requests.
It contains 12 jobs: 1 with no declared dependencies, 11 depending on other jobs.
3 of 12 jobs use a build matrix; 2 of them define 3 configured combinations between them (1 more job's matrix size not reflected in that total).

WHEN IT RUNS
- Runs on every push to main or maintenance/** branches
- Runs on every pull request targeting main or maintenance/** branches

EXECUTION SUMMARY
Independent jobs (no dependencies): get_commit_message
test_meson runs after get_commit_message
test_venv_install runs after get_commit_message
python_debug runs after get_commit_message
gcc10 runs after get_commit_message
prerelease_deps_coverage_64bit_blas runs after get_commit_message
linux_32bit runs after get_commit_message
distro_multiple_pythons runs after get_commit_message
meson_global_install runs after get_commit_message
free-threaded runs after get_commit_message
clang-22-build-only runs after get_commit_message
test_aarch64 runs after get_commit_message

IMPLEMENTATION DETAILS
1. get_commit_message — delegates to reusable workflow ./.github/workflows/commit_message.yml
2. test_meson — runs on ubuntu-22.04; 15 steps; matrix: up to 2 combinations (python-version, maintenance-branch), 1 excluded; after get_commit_message; condition: needs.get_commit_message.outputs.message == 1 && (github.repository == 'scipy/scipy' || github.repository == '')
   [... 5 more steps than shown, capped per _STEP_LIST_CAP ...]
3-12. [test_venv_install, python_debug, gcc10, prerelease_deps_coverage_64bit_blas, linux_32bit,
   distro_multiple_pythons, meson_global_install, free-threaded, clang-22-build-only, test_aarch64 —
   full step lists in evaluation/tier4_scoring/scipy_linux.scoring.md, condition string identical
   across all 11 dependent jobs]

LINKED WORKFLOWS
- calls ./.github/workflows/commit_message.yml

ENVIRONMENT VARIABLES
- CCACHE_DIR: ${{ github.workspace }}/.ccache
- CCACHE_MAXSIZE: 250M
- CCACHE_COMPILERCHECK: content
```

*(Full, unabridged text — all 12 jobs' complete step lists — is in
`evaluation/tier4_scoring/scipy_linux.scoring.md`, lines 346–479; condensed
here for readability since all 11 dependent jobs share the identical
condition string already shown in full once.)*

### Tool's LLM-polished output (verbatim, Condition A's Overview)

> The "Linux tests" pipeline is a GitHub Actions workflow defined in
> `scipy_linux.yml`. It operates with `contents: read` permissions and uses a
> concurrency group that cancels any in-progress runs for the same workflow
> and head reference or run ID. This pipeline runs automatically on every
> push to the `main` or `maintenance/**` branches, and on every pull request
> targeting these branches.
>
> The pipeline consists of 12 jobs. The `get_commit_message` job runs
> independently and delegates to the reusable workflow
> `./.github/workflows/commit_message.yml`. All other 11 jobs depend on
> `get_commit_message` and execute only if its output message is `1` and the
> repository is `scipy/scipy` or empty. Three of these jobs utilize a build
> matrix, with two of them defining a total of three configured
> combinations.
>
> The dependent jobs include `test_meson` (ubuntu-22.04), which sets up
> Python, installs dependencies, builds and installs SciPy, and checks
> installed files and symbol hiding. `test_venv_install` (ubuntu-24.04)
> creates virtual environments for SciPy installation and basic tests.
> `python_debug` (ubuntu-24.04) configures the test environment, builds, and
> tests SciPy. `gcc10` (ubuntu-22.04) sets up Python and system
> dependencies, builds a wheel, installs it, and runs tests.
> `prerelease_deps_coverage_64bit_blas` (ubuntu-latest) builds and installs
> SciPy, tests it, and includes a step to downgrade NumPy. `linux_32bit`
> (ubuntu-latest) builds and tests within an `i686` container.
> `distro_multiple_pythons` (ubuntu-24.04) sets up dependencies, builds a
> wheel, installs it, and runs tests. `meson_global_install` (ubuntu-latest)
> installs global Meson, sets up Python, builds a wheel, installs it, and
> runs tests. `free-threaded` (ubuntu-latest) runs full and fast tests.
> `clang-22-build-only` (ubuntu-24.04-arm) builds a wheel and checks for
> compiler warnings. Finally, `test_aarch64` (ubuntu-24.04-arm) tests SciPy.
> The pipeline also defines environment variables `CCACHE_DIR`,
> `CCACHE_MAXSIZE`, and `CCACHE_COMPILERCHECK`.

### Comparison

| # | Human doc fact | Tool → human doc | Human doc → tool | Contradiction? |
|---|---|---|---|---|
| 1 | "`Linux Tests`: test suite runs for Linux" is one of 20+ GH Actions workflows | Tool correctly documents this single workflow (named "Linux tests" in the YAML) in full | Tool has no visibility into the other ~19 sibling workflows — Tool 1 documents one file at a time by design, not a gap | No |
| 2 | "A PR must pass all these checks before it can be merged" | Tool's triggers show `push` (main/maintenance) + `pull_request` (main/maintenance) exactly | — | No |
| 3 | Skip-CI commit-message convention (`[skip actions]`, `[skip ci]`, etc.) | Tool shows the raw gating expression verbatim on all 11 dependent jobs: `needs.get_commit_message.outputs.message == 1 && (...)` — the mechanism is traceable in the output, but never named or explained as "the skip-CI convention" | Human doc supplies the *semantic meaning* (what commit-message text produces this) that the tool's literal, never-guess rendering doesn't attempt | No — not contradictory, just two different levels of interpretation of the same underlying fact. Plausible, not confirmed: `commit_message.yml`'s internal logic isn't in this project's fixtures, so the exact mapping from `[skip actions]` text → `message == 1` couldn't be independently verified byte-for-byte, only inferred from naming and structure. |
| 4 | `--fail-slow` test-duration thresholds (1s/5s) | Not present in tool output | Genuine scope gap — this is pytest-plugin configuration inside `run:` script bodies, which `_step_lines` never renders (step names only, by design) | No — expected, documented scope boundary |
| 5 | "Wheel builds" section (triggers, artifact upload, PyPI staging) | Not present in tool output | Describes a **different workflow file** (`wheels.yml`), correctly out of scope for this comparison | N/A — not the same workflow |
| 6 | LLM overview's restatement of the gating condition | Matches the raw IR condition string faithfully, adds no invented interpretation of what triggers it | — | No |

**Result: zero contradictions.** All human-doc facts not captured by the tool
fall into already-understood scope boundaries (single-file documentation
scope, step-script-body opacity, a genuinely different workflow file) rather
than tool error.

---

## Candidate 2 — `tox` (multi-fixture)

- **Human doc source**: tox-dev/tox, `docs/development.rst` ("Automated testing" + "Creating a new release" sections), saved verbatim at [`human_docs/tox_development.rst`](human_docs/tox_development.rst).
- **Tool output source**: fresh run of `tool2.multi_pipeline._build_documentation("tests/fixtures/multi/tox", use_llm=True)` — deterministic text confirmed byte-identical to the committed `tests/golden/multi/tox.md` before the LLM call was made; LLM-polished Overview is a new live Gemini call (`gemini-2.5-flash`, temperature 0.2).

### Tool's deterministic output (verbatim — confirmed identical to `tests/golden/multi/tox.md`)

```text
Pipeline: tox (unified CI documentation)
Source: tests/fixtures/multi/tox/.github/workflows (GitHub Actions)

AT A GLANCE
This workflow runs on manual dispatch, pushes to `main`, pull requests, a scheduled run (cron `0 8 * * *`), and pushes.
It contains 6 jobs: 5 with no declared dependencies, 1 depending on other jobs.
2 of 6 jobs use a build matrix; 1 of them define 18 configured combinations between them (1 more job's matrix size not reflected in that total).

WHEN IT RUNS
- Can be triggered manually
- Runs on every push to main branch; excluding tags matching **
- Runs on every pull request
- Runs on a schedule (0 8 * * *)
- Can be triggered manually — inputs: bump
- Runs on every push with tag matching *
- Runs on every push with tag matching *

EXECUTION SUMMARY
Independent jobs (no dependencies): check_yaml__test, check_yaml__check, prepare_release_yaml__prepare-release, release_yaml__build, update_schemastore_yaml__update-schemastore
release_yaml__release runs after release_yaml__build

IMPLEMENTATION DETAILS
1. check_yaml__test — runs on ${{ matrix.os.image }}; 7 steps; matrix: 18 combinations (py, os)
   - actions/checkout (https://github.com/actions/checkout)
   - Install the latest version of uv (https://github.com/astral-sh/setup-uv)
   - Cache wheel downloads (https://github.com/actions/cache)
   - Add .local/bin to Windows PATH
   - Install tox@self
   - Setup test suite
   - Run test suite
2. check_yaml__check — runs on ${{ matrix.os.image }}; 8 steps; matrix: up to 10 combinations (tox_env, os), 1 excluded
   - actions/checkout (https://github.com/actions/checkout)
   - Install the latest version of uv (https://github.com/astral-sh/setup-uv)
   - Cache wheel downloads (https://github.com/actions/cache)
   - Add .local/bin to Windows PATH
   - Install tox@self
   - Install Python 3.10 for type-min
   - Setup check suite
   - Run check for ${{ matrix.tox_env }}
3. prepare_release_yaml__prepare-release — runs on ubuntu-24.04; 8 steps; permissions: contents: write; deployment environment: release-auth
   - actions/checkout (https://github.com/actions/checkout)
   - Install the latest version of uv (https://github.com/astral-sh/setup-uv)
   - Configure git
   - Set up remote tracking
   - Calculate next version
   - Install tox
   - Run release process
   - Display completion message
4. release_yaml__build — runs on ubuntu-24.04; 4 steps
   - actions/checkout (https://github.com/actions/checkout)
   - Install the latest version of uv (https://github.com/astral-sh/setup-uv)
   - Build package
   - Store the distribution packages (https://github.com/actions/upload-artifact)
5. release_yaml__release — runs on ubuntu-24.04; 2 steps; after release_yaml__build; permissions: id-token: write
   - Download all the dists (https://github.com/actions/download-artifact)
   - Publish to PyPI (https://github.com/pypa/gh-action-pypi-publish)
6. update_schemastore_yaml__update-schemastore — runs on ubuntu-24.04; 7 steps; deployment environment: schemastore
   - actions/checkout (https://github.com/actions/checkout)
   - Fork and clone SchemaStore
   - Sync fork's master with upstream
   - Create or reset branch from synced fork
   - Update schema and check for changes
   - Commit and push
   - Create or update pull request

ENVIRONMENT VARIABLES
- FORCE_COLOR: 1
- PYTEST_ADDOPTS: -vv --durations=20 (used in job: check_yaml__test, step: Run test suite)
- DIFF_AGAINST: HEAD (used in job: check_yaml__test, step: Run test suite)
- PYTEST_XDIST_AUTO_NUM_WORKERS: 0 (used in job: check_yaml__test, step: Run test suite)
- FORCE_COLOR: 1
- GH_TOKEN: ${{ secrets.RELEASE_PAT }} (used in job: prepare_release_yaml__prepare-release, step: Run release process)
- STEPS_VERSION_OUTPUTS_VERSION: ${{ steps.version.outputs.version }} (used in job: prepare_release_yaml__prepare-release, step: Run release process)
- STEPS_VERSION_OUTPUTS_VERSION: ${{ steps.version.outputs.version }} (used in job: prepare_release_yaml__prepare-release, step: Display completion message)
- dists-artifact-name: python-package-distributions
- FORCE_COLOR: 1
- GH_TOKEN: ${{ secrets.SCHEMASTORE_TOKEN }} (used in job: update_schemastore_yaml__update-schemastore)
- BRANCH: update-tox-schema (used in job: update_schemastore_yaml__update-schemastore)

SECRETS REQUIRED
- GITHUB_TOKEN (used in job: check_yaml__test, step: Install the latest version of uv)
- GITHUB_TOKEN (used in job: check_yaml__check, step: Install the latest version of uv)
- RELEASE_PAT (used in job: prepare_release_yaml__prepare-release, step: actions/checkout)
- GITHUB_TOKEN (used in job: prepare_release_yaml__prepare-release, step: Install the latest version of uv)
- RELEASE_PAT (used in job: prepare_release_yaml__prepare-release, step: Run release process)
- GITHUB_TOKEN (used in job: release_yaml__build, step: Install the latest version of uv)
- SCHEMASTORE_TOKEN (used in job: update_schemastore_yaml__update-schemastore)
```

### Tool's LLM-polished output (verbatim, live call)

> The "tox" pipeline, a GitHub Actions workflow for unified CI documentation,
> can be triggered manually (with a 'bump' input), on pushes to the `main`
> branch (excluding tags), on pull requests, on a daily schedule at 8 AM
> UTC, and on any push with a tag. It consists of six jobs, two of which
> utilize build matrices, with one defining 18 combinations.
>
> Five jobs run independently: `check_yaml__test`, `check_yaml__check`,
> `prepare_release_yaml__prepare-release`, `release_yaml__build`, and
> `update_schemastore_yaml__update-schemastore`. The `check_yaml__test` job
> runs tests across various OS and Python versions, while
> `check_yaml__check` performs checks across different `tox_env` and OS
> combinations. Both use `uv` and require `GITHUB_TOKEN`. The
> `prepare_release_yaml__prepare-release` job, running on `ubuntu-24.04` in
> the `release-auth` environment, prepares a release, calculates the next
> version, and runs a release process, requiring `RELEASE_PAT` and
> `GITHUB_TOKEN` with `contents: write` permissions. The
> `release_yaml__build` job builds a package on `ubuntu-24.04` and stores
> distribution packages, requiring `GITHUB_TOKEN`. The
> `update_schemastore_yaml__update-schemastore` job, running on
> `ubuntu-24.04` in the `schemastore` environment, forks and syncs
> SchemaStore, updates the schema, commits changes, and creates or updates a
> pull request, requiring `SCHEMASTORE_TOKEN`.
>
> The `release_yaml__release` job runs on `ubuntu-24.04` after
> `release_yaml__build`. It downloads the distribution packages and
> publishes them to PyPI, requiring `id-token: write` permissions. The
> pipeline uses `GITHUB_TOKEN`, `RELEASE_PAT`, and `SCHEMASTORE_TOKEN` as
> secrets.

### Comparison

| # | Human doc fact | Tool → human doc | Human doc → tool | Contradiction? |
|---|---|---|---|---|
| 1 | "All pull requests and merges to the main branch are tested... configured by `check.yaml`" | Tool's triggers for the check.yaml-derived jobs show exactly `workflow_dispatch` + `push` (main, tags excluded) + `pull_request` + `schedule` — matches | — | No |
| 2 | "Navigate to Actions > Prepare Release... Choose the version bump type: `auto` (default) / `major` / `minor` / `patch`" | Tool correctly shows the manual-dispatch trigger exists with a `bump` input (`Can be triggered manually — inputs: bump`) | Tool doesn't enumerate the actual enum choices (`auto`/`major`/`minor`/`patch`) — `_step_lines`/trigger rendering shows input *names*, not `type: choice` value lists | No — under-specifies, doesn't misstate |
| 3 | "The tag push automatically triggers `release.yaml` which: 1. Builds Python packages (sdist + wheel). 2. Publishes to PyPI via trusted publishing" | Tool's `release_yaml__build` (checkout, install uv, build package, store dist) → `release_yaml__release` (download dists, publish to PyPI) structurally matches the doc's 2-step description exactly | — | No |
| 4 | "Method 1: Local release (requires git access)" — a non-CI, local `tox r -e release` git workflow | Not present in tool output | Not applicable to the tool's domain at all — this is a local dev command, not a GitHub Actions workflow; not a gap, out of scope by definition | N/A |
| 5 | "`RELEASE_PAT` secret must be configured" | Tool's SECRETS REQUIRED list shows `RELEASE_PAT` twice, scoped to exactly the `prepare_release_yaml__prepare-release` job's checkout and release-run steps | — | No |
| 6 | LLM overview's job-by-job restatement | Matches doc's release-process description faithfully; no invented facts | — | No |

**Result: zero contradictions.**

---

## Candidate 3 — `black` (multi-fixture)

- **Human doc source**: psf/black, `docs/contributing/gauging_changes.md`, saved verbatim in full at [`human_docs/black_gauging_changes.md`](human_docs/black_gauging_changes.md).
- **Tool output source**: fresh run of `tool2.multi_pipeline._build_documentation("tests/fixtures/multi/black", use_llm=True)` — deterministic text confirmed byte-identical to the committed `tests/golden/multi/black.md` before the LLM call was made; LLM-polished Overview is a new live Gemini call.

### Tool's deterministic output (verbatim — confirmed identical to `tests/golden/multi/black.md`)

```text
Pipeline: black (unified CI documentation)
Source: tests/fixtures/multi/black/.github/workflows (GitHub Actions)

AT A GLANCE
This workflow runs on pushes to `main`, pull requests, completion of `diff-shades`, and pushes.
It contains 6 jobs: 3 with no declared dependencies, 3 depending on other jobs.
3 of 6 jobs use a build matrix.

WHEN IT RUNS
- Runs on every push to main branch; touching path src/** or pyproject.toml or scripts/diff_shades_gha_helper.py or .github/workflows/diff_shades.yml or .github/workflows/diff_shades_comment.yml
- Runs on every pull request touching path src/** or pyproject.toml or scripts/diff_shades_gha_helper.py or .github/workflows/diff_shades.yml or .github/workflows/diff_shades_comment.yml
- Runs after the 'diff-shades' workflow completes
- Runs on every push
- Runs on every pull request

EXECUTION SUMMARY
Independent jobs (no dependencies): diff_shades_yml__configure, diff_shades_comment_yml__comment, lint_yml__lint
diff_shades_yml__analysis-base runs after diff_shades_yml__configure
diff_shades_yml__analysis-target runs after diff_shades_yml__configure
diff_shades_yml__compare runs after diff_shades_yml__configure, diff_shades_yml__analysis-base, diff_shades_yml__analysis-target

IMPLEMENTATION DETAILS
1. diff_shades_yml__configure — runs on ubuntu-latest; 3 steps
   - actions/checkout (https://github.com/actions/checkout)
   - Set up Python (https://github.com/actions/setup-python)
   - Calculate run configuration & metadata
2. diff_shades_yml__analysis-base — runs on ubuntu-latest; 7 steps; matrix: combinations determined at runtime; after diff_shades_yml__configure
   - Checkout this repository (full clone) (https://github.com/actions/checkout)
   - Set up Python (https://github.com/actions/setup-python)
   - Configure git
   - Attempt to use cached baseline analysis (https://github.com/actions/cache)
   - Build and install baseline revision
   - Analyze baseline revision
   - Upload baseline analysis (https://github.com/actions/upload-artifact)
3. diff_shades_yml__analysis-target — runs on ubuntu-latest; 9 steps; matrix: combinations determined at runtime; after diff_shades_yml__configure
   - Checkout this repository (full clone) (https://github.com/actions/checkout)
   - Set up Python (https://github.com/actions/setup-python)
   - Configure git
   - Build and install target revision
   - Attempt to find baseline analysis (https://github.com/actions/cache)
   - Analyze target revision (with repeated projects)
   - Analyze target revision (without repeated projects)
   - Upload target analysis (https://github.com/actions/upload-artifact)
   - Check for failed files for target revision
4. diff_shades_yml__compare — runs on ubuntu-latest; 8 steps; matrix: combinations determined at runtime; after diff_shades_yml__configure, diff_shades_yml__analysis-base, diff_shades_yml__analysis-target; condition: not cancelled()
   - actions/checkout (https://github.com/actions/checkout)
   - actions/download-artifact (https://github.com/actions/download-artifact)
   - Set up Python (https://github.com/actions/setup-python)
   - Generate HTML diff report
   - Upload diff report (https://github.com/actions/upload-artifact)
   - Generate summary file (PR only)
   - Upload summary file (PR only) (https://github.com/actions/upload-artifact)
   - Verify zero changes (PR only)
5. diff_shades_comment_yml__comment — runs on ubuntu-latest; 8 steps; condition: github.event.workflow_run.event == 'pull_request' && contains(fromJSON('["success", "failure"]'), github.event.workflow_run.conclusion); permissions: pull-requests: write
   - actions/checkout (https://github.com/actions/checkout)
   - actions/download-artifact (https://github.com/actions/download-artifact)
   - Validate downloaded comment artifacts
   - Set up Python (https://github.com/actions/setup-python)
   - Get PR number
   - Get details from initial workflow run
   - Try to find pre-existing PR comment (https://github.com/peter-evans/find-comment)
   - Create or update PR comment (https://github.com/peter-evans/create-or-update-comment)
6. lint_yml__lint — runs on ubuntu-latest; 6 steps; condition: github.event_name == 'push' || github.event.pull_request.head.repo.full_name != github.repository
   - actions/checkout (https://github.com/actions/checkout)
   - Assert PR target is main
   - Set up Python (https://github.com/actions/setup-python)
   - Run pre-commit hooks (https://github.com/pre-commit/action)
   - Format ourselves
   - Regenerate schema

LINKED WORKFLOWS
- triggered_by diff-shades

ENVIRONMENT VARIABLES
- HATCH_BUILD_HOOKS_ENABLE: 1
- CC: clang-18
- GITHUB_TOKEN: ${{ github.token }} (used in job: diff_shades_yml__configure, step: Calculate run configuration & metadata)
- GITHUB_TOKEN: ${{ github.token }} (used in job: diff_shades_yml__analysis-base, step: Build and install baseline revision)
- GITHUB_TOKEN: ${{ github.token }} (used in job: diff_shades_yml__analysis-target, step: Build and install target revision)
- GITHUB_TOKEN: ${{ github.token }} (used in job: diff_shades_yml__compare, step: Generate summary file (PR only))
- GITHUB_TOKEN: ${{ github.token }} (used in job: diff_shades_comment_yml__comment, step: Get PR number)
- sha: ${{ github.event.workflow_run.head_sha }} (used in job: diff_shades_comment_yml__comment, step: Get PR number)
- GITHUB_TOKEN: ${{ github.token }} (used in job: diff_shades_comment_yml__comment, step: Get details from initial workflow run)
- pr: ${{ steps.pr.outputs.pr }} (used in job: diff_shades_comment_yml__comment, step: Get details from initial workflow run)
- run_id: ${{ github.event.workflow_run.id }} (used in job: diff_shades_comment_yml__comment, step: Get details from initial workflow run)
- preview_artifact: ${{ steps.comment-artifacts.outputs.preview }} (used in job: diff_shades_comment_yml__comment, step: Get details from initial workflow run)
- stable_artifact: ${{ steps.comment-artifacts.outputs.stable }} (used in job: diff_shades_comment_yml__comment, step: Get details from initial workflow run)
```

### Tool's LLM-polished output (verbatim, live call)

> The "black" pipeline, located in
> `tests/fixtures/multi/black/.github/workflows`, serves as unified CI
> documentation. This GitHub Actions workflow runs on every push to the
> `main` branch, specifically when paths like `src/**`, `pyproject.toml`,
> `scripts/diff_shades_gha_helper.py`, `.github/workflows/diff_shades.yml`,
> or `.github/workflows/diff_shades_comment.yml` are touched. It also runs
> on pull requests affecting these same paths, after the 'diff-shades'
> workflow completes, and on every general push and pull request.
>
> This pipeline consists of six jobs, all running on `ubuntu-latest`. Three
> jobs have no declared dependencies, while the other three depend on other
> jobs. Three of these six jobs utilize a build matrix. The independent jobs
> are `diff_shades_yml__configure`, which checks out the repository, sets up
> Python, and calculates run configuration and metadata using
> `GITHUB_TOKEN`; `diff_shades_comment_yml__comment`, which runs only if the
> triggering workflow run was a pull request with a 'success' or 'failure'
> conclusion, downloads artifacts, gets PR details, and creates or updates a
> PR comment with `pull-requests: write` permissions and several environment
> variables including `GITHUB_TOKEN`, `sha`, `pr`, `run_id`,
> `preview_artifact`, and `stable_artifact`; and `lint_yml__lint`, which runs
> on pushes or if the PR head repository differs from the current one,
> asserts the PR target is `main`, sets up Python, runs pre-commit hooks,
> formats itself, and regenerates the schema, using
> `HATCH_BUILD_HOOKS_ENABLE` and `CC`.
>
> The dependent jobs include `diff_shades_yml__analysis-base`, which runs
> after `diff_shades_yml__configure` and uses a build matrix to checkout,
> set up Python, configure git, attempt cached baseline analysis, build and
> install the baseline revision, analyze it, and upload the analysis using
> `GITHUB_TOKEN`. `diff_shades_yml__analysis-target` also runs after
> `diff_shades_yml__configure` and uses a build matrix to checkout, set up
> Python, configure git, build and install the target revision, attempt to
> find baseline analysis, analyze the target revision (with and without
> repeated projects), upload the analysis, and check for failed files using
> `GITHUB_TOKEN`. Finally, `diff_shades_yml__compare` runs after
> `diff_shades_yml__configure`, `diff_shades_yml__analysis-base`, and
> `diff_shades_yml__analysis-target`, provided it is not cancelled. This job
> uses a build matrix to checkout, download artifacts, set up Python,
> generate and upload an HTML diff report, generate and upload a summary
> file (PR only), and verify zero changes (PR only) using `GITHUB_TOKEN`.
> This pipeline is also triggered by the `diff-shades` workflow.

### Comparison

| # | Human doc fact | Tool → human doc | Human doc → tool | Contradiction? |
|---|---|---|---|---|
| 1 | "GitHub Actions workflow that analyzes and compares two revisions... On PRs / On pushes (main only)" | Tool's triggers show exactly `push` (main, path-filtered) + `pull_request` (same paths) — matches the doc's two trigger rows | — | No |
| 2 | "diff-shades is also the tool behind the ... comments on PRs" (`diff_shades_comment.yml`, `workflow_run`) | Tool's `Runs after the 'diff-shades' workflow completes` line + `diff_shades_comment_yml__comment` job description match exactly | — | No |
| 3 | "For pushes to main... one analysis job named `preview-new-changes`. For PRs... one more analysis job: `assert-no-changes`" | Tool correctly shows the `compare` job's matrix as **"combinations determined at runtime"** rather than inventing the actual mode names — a deliberate, documented "never guess" behavior for dynamic (`fromJson(...)`) matrices | Human doc supplies the actual runtime mode names (`preview-new-changes`, `assert-no-changes`) that the tool correctly declines to fabricate | No — and worth stating positively: this is the tool's dynamic-matrix caution working as designed, not a failure to extract |
| 4 | The `assert-no-changes` mode name literally appears in `diff_shades.yml`'s step-level `if: matrix.mode == 'assert-no-changes'` (the "Verify zero changes (PR only)" step) | **Not surfaced anywhere in tool output** — this is a step-level condition, and per `generators/text_generator.py`'s documented scope, step-level conditions are never rendered, full stop | Human doc is the only source that surfaces this fact | No (not a contradiction — an omission), but **notable**: this is a third, independent confirmation of the step-level-condition gap already found via Tier 4 held-out scoring (`vscode_pr`, `cpython_reusable_macos`) and Tier 2 error injection (Mutation B). Three unrelated evaluation methods — synthetic checklist scoring, deliberate error injection, and now an incidental natural-pairs comparison — have now independently hit the exact same boundary. |
| 5 | Artifact list (HTML diffs, raw JSON analyses, `.preview`/`.stable.pr-comment.md`) | Tool's step names (`Upload diff report`, `Upload summary file (PR only)`, etc.) structurally match the existence of these artifacts | Tool doesn't show artifact filenames/formats — `with:` parameters aren't rendered, a known, already-documented scope boundary (`_step_lines` shows step names only) | No |
| 6 | LLM overview's description of `diff_shades_comment_yml__comment`'s gating condition | Faithful restatement of the job-level condition (which *is* rendered, unlike the step-level one) — the LLM doesn't independently know about `assert-no-changes` either, since it was never in its input | — | No — LLM neither fabricates nor flags what it was never given, consistent with Tier 2's finding |

**Result: zero contradictions**, plus one materially useful re-confirmation
of a previously-known gap via an independent method.

---

## Cross-candidate synthesis

**Zero contradictions found across all three candidates**, scored fact-by-fact
against documentation written by real, independent maintainers with no
awareness this evaluation would ever happen. This is a meaningfully stronger
validity signal than Tier 4's synthetic-checklist hallucination count: Tier
4's checklists are pre-registered and bias-mitigated, but they were still
authored by this project's own developer, working from the same YAML the
tool parses, specifically to be checkable against this tool's architecture.
These three human docs were written independently, for entirely different
purposes (onboarding contributors, explaining a release process, documenting
a niche tool's CI integration), by people with no stake in this project's
correctness claims. A tool output that survives contact with that kind of
ground truth without a single contradiction is better evidence for the
"Python-extraction-then-LLM doesn't hallucinate" claim than a clean run
against a self-authored checklist could be on its own — not a replacement
for Tier 4, but a complementary, harder-to-game check.

Every gap found between the tool's output and the human docs falls into one
of three already-understood categories, none of them new tool defects:

1. **Out-of-scope by architecture** (single-file documentation scope not
   covering sibling workflows; a described workflow file that's genuinely
   different from the one in this project's fixtures, like scipy's
   `wheels.yml` or tox's local `tox r -e release` path).
2. **Deliberately not fabricated** (dynamic matrix values in black's
   `compare` job — the tool correctly declines to invent
   `preview-new-changes`/`assert-no-changes` rather than guessing, exactly
   the "never guess" principle `generators/text_generator.py` is built
   around).
3. **The step-level-condition gap** — re-confirmed for a third time,
   independently, in `black`'s case. Three unrelated evaluation methods
   (Tier 4 held-out scoring, Tier 2 deliberate error injection, and this
   tier's incidental natural-pairs comparison) converging on the same
   specific finding is a stronger case for treating it as a real,
   worth-fixing gap than any one of the three would be alone — though per
   this task's scope, no fix is proposed here either.

No live Gemini call was needed for `scipy_linux` (reused already-current
Tier 4 material); 2 live calls were made for `tox` and `black`
(`gemini-2.5-flash`, temperature 0.2, via `tool2.multi_pipeline._build_documentation`),
both confirmed to reuse byte-identical deterministic output to the committed
golden files before the LLM-polished half was generated fresh.
