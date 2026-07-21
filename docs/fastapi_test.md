# Test

```text
Pipeline: Test
Source: tests/fixtures/fastapi_test.yml (GitHub Actions)

TRIGGERS
- Runs on every push to master branch
- Runs on every pull request
- Runs on a schedule (0 0 * * 1)

JOBS (in order)
1. changes — runs on ubuntu-latest; 2 steps
   - actions/checkout
   - dorny/paths-filter
2. test — runs on ${{ matrix.os }}; 13 steps; matrix: 8 base combinations (os, python-version, deprecated-tests, uv-resolution, starlette-src) + 7 via include; after changes; condition: needs.changes.outputs.src == 'true' || github.ref == 'refs/heads/master'
   - Dump GitHub context
   - actions/checkout
   - Set up Python
   - Setup uv
   - Install Dependencies
   - Ensure that we have the lowest supported Pydantic version
   - Install Starlette from source
   - Install deprecated libraries just for testing
   - Uninstall httpx2 to run tests with httpx
   - Reinstall SQLAlchemy without Cython extensions
   - ... and 3 more steps
3. benchmark — runs on ubuntu-latest; 6 steps; after changes; condition: needs.changes.outputs.src == 'true' || github.ref == 'refs/heads/master'
   - Dump GitHub context
   - actions/checkout
   - Set up Python
   - Setup uv
   - Install Dependencies
   - CodSpeed benchmarks
4. coverage-combine — runs on ubuntu-latest; 11 steps; after test
   - Dump GitHub context
   - actions/checkout
   - actions/setup-python
   - Setup uv
   - Install Dependencies
   - Get coverage files
   - ls -la coverage
   - uv run coverage combine coverage
   - uv run coverage html --title "Coverage for ${{ github.sha }}"
   - Store coverage HTML
   - ... and 1 more step
5. test-alls-green — runs on ubuntu-latest; 2 steps; after test, coverage-combine, benchmark; condition: always()
   - Dump GitHub context
   - Decide whether the needed jobs succeeded or failed
```

## Pipeline Diagram

```mermaid
flowchart LR
    trigger_0(["Push"])
    trigger_1(["Pull request"])
    trigger_2(["Schedule"])
    changes["changes"]
    test["test [matrix: 8 base combinations (os, python-version, deprecated-tests, uv-resolution, starlette-src) + 7 via include, if: needs.changes.outputs.src == 'true' || github.ref == 'refs/heads/master']"]
    benchmark["benchmark [if: needs.changes.outputs.src == 'true' || github.ref == 'refs/heads/master']"]
    coverage-combine["coverage-combine"]
    test-alls-green["test-alls-green [if: always()]"]
    trigger_0 --> changes
    trigger_1 --> changes
    trigger_2 --> changes
    changes --> test
    changes --> benchmark
    test --> coverage-combine
    test --> test-alls-green
    coverage-combine --> test-alls-green
    benchmark --> test-alls-green
```
