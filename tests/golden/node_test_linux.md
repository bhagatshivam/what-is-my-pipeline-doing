# Test Linux

```text
Pipeline: Test Linux
Source: tests/fixtures/node_test_linux.yml (GitHub Actions)

TRIGGERS
- Runs on every pull request excluding paths .mailmap or README.md or vcbuild.bat or tools/actions/** or tools/clang-format/** or tools/dep_updaters/** or test/internet/** or **.nix or .github/** or !.github/workflows/test-linux.yml
- Runs on every push to main or canary or v[0-9]+.x-staging or v[0-9]+.x branches; excluding paths .mailmap or README.md or vcbuild.bat or tools/actions/** or tools/clang-format/** or tools/dep_updaters/** or test/internet/** or **.nix or .github/** or !.github/workflows/test-linux.yml

JOBS (in order)
1. test-linux — runs on ${{ matrix.os }}; 9 steps; matrix: 2 combinations (os); condition: github.event.pull_request.draft == false
```

## Pipeline Diagram

```mermaid
flowchart LR
    trigger_0(["Pull request"])
    trigger_1(["Push"])
    test-linux["test-linux [matrix: 2 combinations (os), if: github.event.pull_request.draft == false]"]
    trigger_0 --> test-linux
    trigger_1 --> test-linux
```
