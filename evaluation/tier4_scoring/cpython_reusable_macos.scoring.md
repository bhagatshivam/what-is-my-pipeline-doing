# Tier 4 scoring — cpython_reusable_macos

Pre-registered checklist: `evaluation/tier4_checklists/cpython_reusable_macos.checklist.yml` (open separately -- not duplicated here).

Score each condition fact-by-fact against the checklist: present / missing / false (hallucination). Presentation order below is randomized per EVALUATION_PLAN.md's Method 9 bias mitigation -- the mapping back to conditions 1/2/3 is in `cpython_reusable_macos.answer_key.md`, intentionally kept out of this file.

---

## Condition A

This CI/CD pipeline, named "Reusable macOS," is a **reusable GitHub Actions workflow** designed to **build and test the CPython interpreter on various macOS environments**, with a specific focus on testing both standard (GIL-enabled) and "free-threading" (GIL-disabled) builds, and performing rigorous compiler warning checks.

Here's a breakdown of what it does:

### 1. Reusability and Trigger

*   **`on: workflow_call`**: This is a reusable workflow. It means this pipeline cannot be run directly by events like pushes or pull requests. Instead, it must be explicitly called by another workflow (e.g., a matrix job in a main workflow that iterates through different OS versions or configurations). This promotes modularity and reduces duplication.

### 2. Inputs

The calling workflow provides two inputs:

*   **`free-threading` (boolean, default: `false`)**:
    *   If `true`, it instructs the CPython build process to disable the Global Interpreter Lock (GIL), enabling "free-threading" mode (a significant feature in newer Python versions like 3.13+).
    *   If `false` (default), CPython is built with the standard GIL enabled.
*   **`os` (string, required)**:
    *   Specifies the exact macOS runner environment to use (e.g., `macos-latest`, `macos-14`, `macos-26-intel`). This allows the calling workflow to test on different macOS versions and architectures.

### 3. Permissions and Environment

*   **`permissions: contents: read`**: Grants read-only access to the repository's contents, which is necessary for checking out the code.
*   **`env: FORCE_COLOR: 1`**: Forces colored output in the terminal logs, making them easier to read.

### 4. The `build-macos` Job

This is the single job in the workflow, responsible for the actual build and test process.

*   **`name: build and test (${{ inputs.os }})`**: A descriptive name that includes the target OS for clarity in the GitHub Actions UI.
*   **`runs-on: ${{ inputs.os }}`**: The job runs on the macOS runner specified by the `os` input.
*   **`timeout-minutes: 60`**: The job will automatically cancel if it runs for longer than 60 minutes.
*   **Job-level Environment Variables**:
    *   `HOMEBREW_NO_ANALYTICS`, `HOMEBREW_NO_AUTO_UPDATE`, `HOMEBREW_NO_INSTALL_CLEANUP`, `HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK`: These disable various Homebrew features that are typically undesirable in a CI environment (e.g., analytics, automatic updates, cleanup, dependency checks) to ensure consistent and faster builds.
    *   `PYTHONSTRICTEXTENSIONBUILD: 1`: Likely enables stricter checks during the build of Python extensions.
    *   `TERM: linux`: Sets the terminal type, which can sometimes be necessary for certain build tools.

### 5. Steps in Detail

1.  **`actions/checkout@v7.0.0`**:
    *   Clones the repository containing the CPython source code onto the runner.
    *   `persist-credentials: false` is a security measure, preventing credentials from being stored.

2.  **`Runner image version`**:
    *   Logs the specific macOS image version being used (e.g., `macOS-14-arm64`) to the console and sets it as an environment variable (`IMAGE_OS_VERSION`) for potential later use.

3.  **`Install Homebrew dependencies`**:
    *   `brew bundle --file=Misc/Brewfile`: Installs all dependencies listed in the `Misc/Brewfile` using Homebrew. This is a common way to manage project dependencies on macOS.
    *   `brew install make`: Ensures `make` (specifically GNU make, often aliased as `gmake` on macOS) is installed.

4.  **`Configure CPython`**:
    *   This step prepares the CPython source code for compilation.
    *   `MACOSX_DEPLOYMENT_TARGET=10.15`: Sets the minimum macOS version that the compiled Python will support.
    *   `GDBM_CFLAGS`, `GDBM_LIBS`: Specifies the include and library paths for the `gdbm` library, a common dependency for Python.
    *   `./configure`: Runs the standard CPython configuration script with several options:
        *   `--config-cache`: Caches configuration results.
        *   `--with-pydebug`: Enables a debug build of Python.
        *   `--enable-slower-safety`, `--enable-safety`: Enables various runtime safety checks, potentially impacting performance.
        *   **`${{ inputs.free-threading && '--disable-gil' || '' }}`**: This is the key conditional part. If the `free-threading` input is `true`, it adds the `--disable-gil` flag, which builds CPython without the Global Interpreter Lock. Otherwise, this flag is omitted.
        *   `--prefix=/opt/python-dev`: Specifies the installation directory for the built Python.
        *   `--with-openssl="$(brew --prefix openssl@3.5)"`: Links against the OpenSSL 3.5 library installed via Homebrew.

5.  **`Build CPython`**:
    *   **Conditional execution**: This step runs *only if* `free-threading` is enabled OR if the `os` is *not* `macos-26-intel`.
    *   `gmake -j8`: Compiles CPython using `gmake` with 8 parallel jobs for faster compilation.

6.  **`Build CPython for compiler warning check`**:
    *   **Conditional execution**: This step runs *only if* `free-threading` is `false` AND the `os` is `macos-26-intel`. This suggests a specific environment and configuration is targeted for detailed warning analysis.
    *   `set -o pipefail; gmake -j8 --output-sync 2>&1 | tee compiler_output_macos.txt`:
        *   `set -o pipefail`: Ensures that if any command in the pipeline fails, the entire pipeline fails.
        *   `gmake -j8 --output-sync`: Builds CPython with 8 parallel jobs, synchronizing output.
        *   `2>&1 | tee compiler_output_macos.txt`: Redirects both standard output and standard error to `tee`, which simultaneously prints the build output to the console and saves it to a file named `compiler_output_macos.txt`. This file is crucial for the next step.

7.  **`Display build info`**:
    *   `make pythoninfo`: Executes a `make` target that displays detailed information about the just-built CPython interpreter (e.g., version, configuration flags, compiler used).

8.  **`Check compiler warnings`**:
    *   **Conditional execution**: This step runs *only if* `free-threading` is `false` AND the `os` is `macos-26-intel` (i.e., after the special build that captured output).
    *   `python3 Tools/build/check_warnings.py ...`: Executes a Python script to analyze the `compiler_output_macos.txt` file.
        *   `--warning-ignore-file-path=Tools/build/.warningignore_macos`: Specifies a file containing a list of known, acceptable warnings to ignore.
        *   `--compiler-output-type=clang`: Indicates that the compiler output is from Clang (the default compiler on macOS).
        *   `--fail-on-regression`: The script will fail if any *new* compiler warnings are introduced.
        *   `--fail-on-improvement`: The script will also fail if an *existing ignored warning disappears*. This is a strict check to ensure the `.warningignore_macos` file is kept up-to-date and doesn't contain stale entries.
    *   **Purpose**: This step is critical for maintaining code quality by preventing the introduction of new compiler warnings and ensuring that the list of ignored warnings is actively managed.

9.  **`Tests`**:
    *   `make ci`: Executes the CPython test suite (likely a comprehensive set of unit and integration tests) as defined by the `ci` target in the project's Makefile.

### In Summary:

This reusable macOS CI/CD pipeline is a sophisticated testing mechanism for CPython development. It allows other workflows to:

*   **Build CPython on various macOS versions/architectures.**
*   **Test both standard (GIL-enabled) and experimental (GIL-disabled/free-threading) builds.**
*   **Perform a dedicated, strict compiler warning check** on a specific macOS Intel environment for the standard build, ensuring code quality and preventing warning regressions.
*   **Run the full test suite** against the built interpreter.

It's a robust setup for ensuring the stability and quality of the CPython interpreter across different macOS configurations and experimental features.

---

## Condition B

# Reusable macOS

<!-- llm-overview:start -->
## Overview

The "Reusable macOS" GitHub Actions workflow is designed to be called by other workflows, accepting `free-threading` and `os` as inputs. This pipeline operates with `contents: read` permissions.

It consists of a single job, `build-macos`, which executes on the operating system specified by the `os` input. This job performs nine steps: checking out the repository, displaying the runner image version, installing Homebrew dependencies, configuring CPython, building CPython, building CPython again for a compiler warning check, displaying build information, checking for compiler warnings, and running tests.
<!-- llm-overview:end -->

```text
Pipeline: Reusable macOS
Source: /home/user/what-is-my-pipeline-doing/evaluation/held_out_workflows/cpython_reusable_macos.yml (GitHub Actions)
Permissions: contents: read

AT A GLANCE
This workflow runs on being called by another workflow.
It contains 1 job, with no job dependencies, so GitHub may run them in parallel.

WHEN IT RUNS
- Can be called by other workflows as a reusable workflow — inputs: free-threading, os

EXECUTION SUMMARY
Independent jobs (no dependencies): build-macos

IMPLEMENTATION DETAILS
1. build-macos — runs on ${{ inputs.os }}; 9 steps
   - actions/checkout (https://github.com/actions/checkout)
   - Runner image version
   - Install Homebrew dependencies
   - Configure CPython
   - Build CPython
   - Build CPython for compiler warning check
   - Display build info
   - Check compiler warnings
   - Tests
```

## Pipeline Diagram

All 1 job is independent — no job-dependency diagram is shown; see EXECUTION SUMMARY above.

---

## Condition C

Pipeline: Reusable macOS
Source: /home/user/what-is-my-pipeline-doing/evaluation/held_out_workflows/cpython_reusable_macos.yml (GitHub Actions)
Permissions: contents: read

AT A GLANCE
This workflow runs on being called by another workflow.
It contains 1 job, with no job dependencies, so GitHub may run them in parallel.

WHEN IT RUNS
- Can be called by other workflows as a reusable workflow — inputs: free-threading, os

EXECUTION SUMMARY
Independent jobs (no dependencies): build-macos

IMPLEMENTATION DETAILS
1. build-macos — runs on ${{ inputs.os }}; 9 steps
   - actions/checkout (https://github.com/actions/checkout)
   - Runner image version
   - Install Homebrew dependencies
   - Configure CPython
   - Build CPython
   - Build CPython for compiler warning check
   - Display build info
   - Check compiler warnings
   - Tests

---
