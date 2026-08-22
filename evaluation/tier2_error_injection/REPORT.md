# Tier 2 — Error Injection / Stress Test

Method 6 of `EVALUATION_PLAN.md` ("Deliberately break test pipelines ... does
the tool flag the problem, or silently produce plausible-but-wrong
documentation?"). This is a qualitative stress test of hallucination risk in
the LLM layer, not a pre-registered/blinded comparison like Tier 4 — it does
not need that level of protocol rigor, and this report presents raw,
quotable evidence rather than a scored rubric.

## Scope and how this differs from the existing `evaluation/error_injection/`

`evaluation/error_injection/` (pre-existing, untouched by this work) already
runs 8 synthetic malformed workflows through the CLI as a subprocess and
classifies the exit code — including a dangling-dependency fixture and a
dependency-cycle fixture, both pre-registered and confirmed
`rejects_correctly` (exit 3). That work answers "does validation catch this
class of error" for the cases it covers.

This exercise asks a different, narrower question for the two categories that
turned out **not** to be covered by that mechanism at all: once a broken
pipeline gets past validation with zero errors or warnings, what does the
LLM beautification layer actually do with it? It runs each mutation through
the real pipeline — `GitHubActionsParser().parse()` → `validate_pipeline()`
→ `generate_text()` → `GeminiProvider.beautify()` — using the live Gemini
API (`gemini-2.5-flash`, temperature 0.2, one real call per mutation that
reaches that layer), and reads the actual polished output for the specific
failure mode this tier exists to catch: fluent, confident prose that papers
over a break rather than reflecting that something is actually wrong.

**Pre-investigation finding (confirms what `cli.py`/`tool1/single_pipeline.py`
actually do):** `tool1/single_pipeline.py`'s `_build_documentation` calls
`validate_or_raise`, not `validate_pipeline`. Any **error**-severity
`ValidationIssue` raises `IRValidationError` *before* `generate_text()` or
`beautify()` ever run — `cli.py` catches it and exits 3. Warning-severity
issues are printed to stderr but generation proceeds. This is the reason
Mutation A below produces no generated output of any kind: it never reaches
the LLM, or even the deterministic generator.

## Mutation A — dangling dependency (contrast case)

Copy of `tests/fixtures/checkout_check_dist.yml` with one change:
[`fixtures/dangling_dependency.yml`](fixtures/dangling_dependency.yml)

```diff
   check-dist:
     runs-on: ubuntu-latest
+    needs: publish-release
```

**Validation result** — one error, exactly as `_check_job_dependencies_exist`
(`ir/validate.py`) is designed to produce:

```
[ERROR] jobs[0].dependencies: Job 'check-dist' depends on 'publish-release', which does not exist in this pipeline.
```

**Generation outcome:** blocked. `validate_or_raise` raises `IRValidationError`
before `generate_text()` is called. No deterministic output, no LLM call —
there is nothing for a hallucination to attach to, because nothing is
generated at all. Confirms the Step 1 finding directly: for this category
the tool fails **safe and loud**, not silently. (This duplicates, at the
Python-API level, what `evaluation/error_injection/dangling_dependency.yml`
already established at the CLI-exit-code level — included here only for a
complete three-category contrast, not as a new finding.)

## Mutation B — malformed `if:` condition

Copy of `tests/fixtures/checkout_check_dist.yml` with one change: the
upload-artifact step's `if:` has its `==` comparison left with no
right-hand operand.
[`fixtures/malformed_if_condition.yml`](fixtures/malformed_if_condition.yml)

```diff
       - uses: actions/upload-artifact@v7
-        if: ${{ failure() && steps.diff.conclusion == 'failure' }}
+        if: ${{ failure() && steps.diff.conclusion == }}
```

**Validation result:** zero issues, as predicted — `_check_conditions` only
requires a non-empty `expression`; it never inspects syntactic validity.

**Generation outcome:** proceeded fully. Deterministic output:

```text
Pipeline: Check dist
Source: evaluation/tier2_error_injection/fixtures/malformed_if_condition.yml (GitHub Actions)

AT A GLANCE
This workflow runs on pushes to `main`, pull requests, and manual dispatch.
It contains 1 job, with no job dependencies, so GitHub may run them in parallel.

WHEN IT RUNS
- Runs on every push to main branch; excluding paths **.md
- Runs on every pull request excluding paths **.md
- Can be triggered manually

EXECUTION SUMMARY
Independent jobs (no dependencies): check-dist

IMPLEMENTATION DETAILS
1. check-dist — runs on ubuntu-latest; 6 steps
   - actions/checkout@v7 (https://github.com/actions/checkout)
   - Set Node.js 24.x (https://github.com/actions/setup-node)
   - Install dependencies
   - Rebuild the index.js file
   - Compare the expected and actual dist/ directories
   - actions/upload-artifact@v7 (https://github.com/actions/upload-artifact)
```

**LLM-polished output** (Gemini 2.5 Flash, temperature 0.2, 479 input /
206 output tokens, ~5.1s):

> The "Check dist" pipeline is a GitHub Actions workflow defined at
> `evaluation/tier2_error_injection/fixtures/malformed_if_condition.yml`.
> This workflow runs on every push to the `main` branch, excluding changes
> to `.md` files. It also runs on every pull request, similarly excluding
> `.md` file paths, and can be triggered manually.
>
> The pipeline contains a single job named `check-dist`. There are no job
> dependencies, so GitHub may run jobs in parallel if there were multiple.
>
> The `check-dist` job executes on `ubuntu-latest` and consists of six
> steps. It first checks out the repository using `actions/checkout@v7`,
> then sets up Node.js 24.x with `actions/setup-node`. Following this, it
> installs dependencies, rebuilds the `index.js` file, and compares the
> expected and actual `dist/` directories. Finally, it uses
> `actions/upload-artifact@v7`.

### Critical reading

Neither of the two outcomes the question anticipated actually happened.
**The broken condition doesn't appear anywhere in either output — not
narrated as coherent, not flagged as opaque, not mentioned at all.**
`actions/upload-artifact@v7` is described flatly as if it always runs, no
different from `actions/checkout@v7` in the same list.

The reason is upstream of the LLM entirely: `generate_text()`'s `_step_lines`
(`generators/text_generator.py:273-293`) is documented, by design, to render
only `Step.name` (plus an external-action link) — "no other step-level
detail is projected (no with_args/env/raw_extras, **no step-level
Condition**)". Step-level `if:` conditions are out of scope for the
deterministic fact sheet entirely, regardless of whether they're
well-formed or garbled. `Pipeline.jobs[0].steps[5].condition.expression`
correctly holds the literal broken string
`"${{ failure() && steps.diff.conclusion == }}"` in the IR — but nothing
downstream of the parser ever reads it, so it can neither be flagged nor
hallucinated about. (Job-level `if:` conditions *are* rendered, via
`_job_line_body`'s `condition:` clause — this fixture's condition happens to
be step-level, so that path isn't exercised here.)

**This is a real, if narrow, finding worth stating plainly:** the tool
"fails safe" on this specific mutation, but not because anything detected
or handled the brokenness — because the information carrying it was already
excluded from what the LLM (or the reader) ever sees. A step-level
condition, broken or not, is invisible in the generated documentation today.
That is a coverage gap already implicitly acknowledged elsewhere in the
project (`generators/text_generator.py`'s own docstring calls this out as
scope, not a bug), not a new defect — but this exercise is the first time
it's been shown to also mean "a step gated on a condition that could never
evaluate to true is documented identically to a step that always runs,"
which is a materially misleading omission a reader could act on, distinct
from the narrower "we don't show step conditions" framing the codebase
docstring uses. Whether that's worth fixing is a separate, follow-up
decision — not made here.

## Mutation C — malformed secret reference (`secret.` vs `secrets.`)

Copy of `tests/fixtures/checkout_check_dist.yml` with one change: an `env:`
block referencing `secret.DEPLOY_TOKEN` (typo of `secrets.DEPLOY_TOKEN`).
[`fixtures/secret_typo.yml`](fixtures/secret_typo.yml)

```diff
   check-dist:
     runs-on: ubuntu-latest
+    env:
+      DEPLOY_TOKEN: ${{ secret.DEPLOY_TOKEN }}
 
     steps:
```

**Validation result:** zero issues, as predicted. `_SECRET_REF_RE`
(`parsers/github_actions.py:316`, `r"secrets\.([A-Za-z0-9_]+)"`) requires the
literal plural `secrets.`; the singular typo simply never matches, so no
`Secret` object is created at all — there is nothing for
`_check_secret_and_env_scopes` to flag, because from the IR's point of view
this secret reference doesn't exist. The value is instead captured as an
ordinary `EnvironmentVariable` (env-var parsing has no secret-awareness).

**Generation outcome:** proceeded fully. Deterministic output:

```text
Pipeline: Check dist
Source: evaluation/tier2_error_injection/fixtures/secret_typo.yml (GitHub Actions)

AT A GLANCE
This workflow runs on pushes to `main`, pull requests, and manual dispatch.
It contains 1 job, with no job dependencies, so GitHub may run them in parallel.

WHEN IT RUNS
- Runs on every push to main branch; excluding paths **.md
- Runs on every pull request excluding paths **.md
- Can be triggered manually

EXECUTION SUMMARY
Independent jobs (no dependencies): check-dist

IMPLEMENTATION DETAILS
1. check-dist — runs on ubuntu-latest; 6 steps
   - actions/checkout@v7 (https://github.com/actions/checkout)
   - Set Node.js 24.x (https://github.com/actions/setup-node)
   - Install dependencies
   - Rebuild the index.js file
   - Compare the expected and actual dist/ directories
   - actions/upload-artifact@v7 (https://github.com/actions/upload-artifact)

ENVIRONMENT VARIABLES
- DEPLOY_TOKEN: ${{ secret.DEPLOY_TOKEN }} (used in job: check-dist)
```

Note what the deterministic layer does correctly: it shows the raw,
unresolved `${{ secret.DEPLOY_TOKEN }}` expression verbatim, under
**ENVIRONMENT VARIABLES**, not under a `SECRETS REQUIRED` heading (which
doesn't even appear, since `pipeline.secrets` is empty). A careful reader
who reads closely enough to notice the singular "secret." could catch the
typo themselves — the ground truth needed to catch this is present in the
text, just not flagged.

**LLM-polished output** (Gemini 2.5 Flash, temperature 0.2, 503 input /
161 output tokens, ~3.5s):

> The "Check dist" pipeline is a GitHub Actions workflow defined in
> `evaluation/tier2_error_injection/fixtures/secret_typo.yml`. This
> workflow runs automatically on pushes to the `main` branch and on pull
> requests, excluding changes to `.md` files in both scenarios. It can also
> be triggered manually.
>
> The pipeline consists of one independent job named `check-dist`, which
> executes on `ubuntu-latest`. This job performs six steps: it checks out
> the repository, sets up Node.js 24.x, installs dependencies, rebuilds the
> `index.js` file, compares the expected and actual `dist/` directories,
> and then uploads an artifact.
>
> **The `check-dist` job requires and uses the `DEPLOY_TOKEN` secret.**

### Critical reading

**This is the hallucination this tier exists to catch.** The deterministic
fact sheet never asserts that `DEPLOY_TOKEN` is a secret — quite the
opposite, its own IR-level classification put it under `ENVIRONMENT
VARIABLES`, specifically because the parser's secret-detection regex did
*not* recognize it as one. The LLM's rewrite discards the raw
`${{ secret.DEPLOY_TOKEN }}` expression (the only textual evidence that
something is broken) and asserts, flatly and with no hedge, "the
`check-dist` job **requires and uses** the `DEPLOY_TOKEN` secret" — stating
as settled fact something the tool's own extraction logic explicitly did
not establish. A reader trusting this sentence would believe the pipeline
correctly consumes a repo secret named `DEPLOY_TOKEN`; in reality, the
YAML's `secret.DEPLOY_TOKEN` typo means GitHub Actions would leave that
env var literally set to the empty string at runtime, silently, with no
error from GitHub either — the exact "silently produce plausible-but-wrong
documentation" failure mode this method was designed to surface.

It's worth noting the system prompt (`llm/gemini_provider.py:39-58`)
explicitly instructs: *"Do not add any fact, number, name, condition, or
claim that is not already present in the fact sheet below," and "Do not
omit a ... secret listed in the fact sheet."* The most plausible mechanism
here is that the model pattern-matched on the literal substring `secret` inside
the raw expression value and, primed by "don't omit a secret," promoted an
environment variable into "the DEPLOY_TOKEN secret" — which is itself an
inferential leap ("uses" implies successful, working consumption) beyond
what the fact sheet's own ENVIRONMENT VARIABLES/SECRETS REQUIRED
distinction supports. This is not a prompt bug to be patched here (out of
scope for this exercise, per the task's own instruction not to propose
fixes) — it's the finding itself.

## Synthesis

Three categories, three different outcomes, none of them what a simple
"catches errors / doesn't catch errors" framing would predict:

- **Dangling dependency (A):** caught and hard-blocked before generation.
  No output exists, so no hallucination is possible. The safest outcome,
  and already independently confirmed by the pre-existing
  `evaluation/error_injection/` fixture.
- **Malformed `if:` (B):** not caught, not flagged, not hallucinated about
  either — the broken condition is simply invisible in both the
  deterministic and LLM output, because step-level conditions are out of
  scope for `generate_text()` entirely, by design, independent of validity.
  A clean-looking result, but for a reason unrelated to correctness
  detection — worth stating honestly rather than claiming the tool "handled"
  this case.
- **Malformed secret reference (C):** not caught by validation, and **the
  LLM layer actively converts a silently-dropped, broken reference into a
  confident, false assertion that a working secret is used.** This is a
  real, demonstrated hallucination-risk finding, not a hypothetical one:
  Python-extraction-then-LLM is supposed to prevent exactly this
  (`PROJECT_PLAN.md`'s central architectural claim), and it did not, in
  this case, because the extraction layer silently misclassified the input
  before the LLM ever ran — the LLM then confidently overstated what that
  misclassified fact actually supported.

Neither result should be overstated: B's clean outcome is an artifact of
missing coverage, not of correct handling, and C's hallucination is a
single documented instance on one fixture, not a general characterization
of the LLM layer's reliability. Both are exactly the kind of concrete,
quotable, honestly-reported evidence this tier is meant to produce for the
Reflection section — one real gap (C) and one near-miss that turned out to
be a different gap in disguise (B).

## Not fixed here

Per the task instructions for this exercise, no code changes are proposed
or made in response to these findings. Two things surfaced that look like
real, fixable gaps rather than accepted scope:

1. **Mutation C** — a secret reference is silently reclassified as an
   ordinary environment variable on a single-character context-name typo,
   with zero validation warning, and the LLM layer then asserts it works.
2. **Mutation B** — a step-level `if:` condition (valid or broken) is never
   surfaced in generated documentation at all, which can make a
   conditionally-skipped step look unconditional to a reader.

Both are reported here as observations for the dissertation's Reflection
section. Any decision to fix either needs its own separate plan-first
round, same as any other code change to this project.
