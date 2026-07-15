# Unit Tests

```text
Pipeline: Unit Tests
Source: tests/fixtures/pandas_unit_tests.yml (GitHub Actions)

TRIGGERS
- Runs on every push to main or 3.0.x branches
- Runs on every pull request targeting main or 3.0.x branches; excluding paths doc/** or web/**

JOBS (in order)
1. ubuntu — runs on ${{ matrix.platform }}; 8 steps; matrix: 8 base combinations (platform, environment, pytest_marker_expression, pandas_future_infer_string, pandas_future_python_scalars) + 10 via include
2. macos-windows — runs on ${{ matrix.os }}; 5 steps; matrix: 12 combinations (os, environment)
3. Linux-32-bit — runs on ubuntu-24.04; 3 steps
4. Linux-Musl — runs on ubuntu-24.04; 4 steps
5. Windows-MinGW — runs on windows-2025; 3 steps
6. Linux-Sanitizers — runs on ubuntu-24.04; 5 steps
7. python-dev — runs on ${{ matrix.os }}; 4 steps; matrix: 4 combinations (os); condition: false
8. emscripten — runs on ubuntu-24.04; 8 steps

SECRETS REQUIRED
- CODECOV_TOKEN (used in job: ubuntu.7)
```

## Pipeline Diagram

```mermaid
flowchart LR
    trigger_0(["Push"])
    trigger_1(["Pull request"])
    ubuntu["ubuntu [matrix: 8 base combinations (platform, environment, pytest_marker_expression, pandas_future_infer_string, pandas_future_python_scalars) + 10 via include]"]
    macos-windows["macos-windows [matrix: 12 combinations (os, environment)]"]
    Linux-32-bit["Linux-32-bit"]
    Linux-Musl["Linux-Musl"]
    Windows-MinGW["Windows-MinGW"]
    Linux-Sanitizers["Linux-Sanitizers"]
    python-dev["python-dev [matrix: 4 combinations (os), if: false]"]
    emscripten["emscripten"]
    trigger_0 --> ubuntu
    trigger_0 --> macos-windows
    trigger_0 --> Linux-32-bit
    trigger_0 --> Linux-Musl
    trigger_0 --> Windows-MinGW
    trigger_0 --> Linux-Sanitizers
    trigger_0 --> python-dev
    trigger_0 --> emscripten
    trigger_1 --> ubuntu
    trigger_1 --> macos-windows
    trigger_1 --> Linux-32-bit
    trigger_1 --> Linux-Musl
    trigger_1 --> Windows-MinGW
    trigger_1 --> Linux-Sanitizers
    trigger_1 --> python-dev
    trigger_1 --> emscripten
```
