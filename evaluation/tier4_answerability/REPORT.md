# Tier 4 — Answerability Audit (Method 9, second half)

This report covers the second half of `EVALUATION_PLAN.md` Method 9: for
each of the 10 held-out pipelines, five ground-truth questions derived
directly from the pipeline's YAML were checked for whether they're
answerable from Tool 1's output (deterministic + LLM-polished — scored
together as "Tool" below, since Tier 4's fact-checklist scoring already
established they're fact-for-fact identical on this set) and separately
from the naive baseline's output, using the same
`evaluation/tier4_scoring/*.scoring.md` materials and per-pipeline
`.answer_key.md` condition mapping as the fact-checklist scoring in
`evaluation/tier4_findings/REPORT.md`. This is a usability lens — can a
reader actually get the answer out of the document — rather than a
fact-coverage lens; see the Synthesis section for how the two relate.

## Questions

1. **When does it run?** (triggers)
2. **Which jobs run in parallel?**
3. **What must finish before deployment / the "main" gate job?**
4. **Which workflows are explicitly connected to this one?**
5. **Which secrets or external actions are required?**

Each is scored **Yes** (answerable), **Partial** (partially answerable —
the mechanism is described but not fully, e.g. missing a count or a
specific name), **No** (not answerable, the document doesn't address it),
or **N/A** (the pipeline genuinely lacks that structural element — e.g. a
single-job pipeline has no "which jobs run in parallel" question to answer
at all). N/A is a property of the pipeline, not either output, so it's
identical for both columns whenever it applies.

## Results

| Pipeline | Q1 (when) | Q2 (parallel jobs) | Q3 (deploy gate) | Q4 (linked workflows) | Q5 (secrets/actions) |
|---|---|---|---|---|---|
| pre_commit_main | Yes / Yes | Yes / Partial | N/A / N/A | Yes / Yes | Partial / Partial |
| httpie_code_style | Yes / Yes | N/A / N/A | N/A / N/A | N/A / N/A | Yes / Yes |
| httpx_test_suite | Yes / Yes | N/A(+matrix) / Partial-plus | N/A / N/A | N/A / N/A | Yes / Yes |
| requests_lint | Yes / Yes | N/A / N/A | N/A / N/A | N/A / N/A | Yes / Yes |
| cpython_reusable_macos | Yes / Yes | N/A / N/A | N/A / N/A | N/A / N/A | Partial / **Yes (mischaracterized)** |
| urllib3_ci | Yes / Yes | Yes / Partial | Yes / Yes | N/A / N/A | Yes / Yes |
| celery_python_package | Yes / Yes | Yes / Yes | Yes / Yes | Yes / Yes | Yes / **No** |
| vscode_pr | Yes / Yes | Yes / Partial | N/A / N/A | Yes / Partial | Yes / Partial |
| scipy_linux | Yes / Yes | Yes / Partial | Yes / Partial | Yes / Yes | N/A / N/A |
| nextjs_build_and_test | Yes (incomplete — types) / Yes | Yes / Partial | Yes / **No** | Yes / Partial | Yes / **No** |

Each cell reads Tool / Naive baseline. 150 answers total (10 pipelines × 5
questions × 2 columns compared, with Tool 1's deterministic and LLM-polished
conditions collapsed into one column since Tier 4's fact-checklist scoring
already established they never diverge on this held-out set).

## Verification notes

Three cells were spot-checked directly against the underlying
`evaluation/tier4_scoring/*.scoring.md` text before accepting this table,
following the same standard applied to the fact-checklist corrections in
`evaluation/tier4_findings/REPORT.md`:

- **`celery_python_package` Q5, naive baseline = No.** Confirmed: the naive
  baseline's Condition B text mentions "Codecov" three times (uploading
  coverage, uploading test results, "integrating... Codecov for coverage
  and test result reporting") but never once names the `CODECOV_TOKEN`
  secret the tool's output identifies twice. It describes *what* the
  pipeline does with Codecov without ever surfacing *that a secret is
  required* to do it.
- **`nextjs_build_and_test` Q5, naive baseline = No.** Confirmed: zero
  secret or token mentions anywhere in the naive baseline's Condition B
  text. The tool's output names `GITHUB_TOKEN`, `KV_REST_API_URL`, and
  `KV_REST_API_TOKEN` explicitly, each tied to its specific job and step.
- **`cpython_reusable_macos` Q5, naive baseline = Yes (mischaracterized).**
  Confirmed, and directly explained by an already-established finding: the
  naive baseline does name an external action (`actions/checkout@v7.0.0`),
  but states it as pinned to the tag `v7.0.0` — the same tag-vs-SHA-pin
  misstatement already documented in `evaluation/tier4_findings/REPORT.md`
  as `cpython_reusable_macos.job.1`, this evaluation's one genuine False
  fact. The naive baseline technically answers the question here, but with
  the same confidently wrong claim already on record elsewhere — worth
  scoring as answered-but-wrong, not simply "answered."

**One correction applied before writing this table:** `nextjs_build_and_test`
Q3's naive-baseline "No" is scored on **completeness** grounds, not
accuracy grounds. Per the reframing in `evaluation/tier4_findings/REPORT.md`
(the `dependency.115-144` correction), the currently committed naive-baseline
text for the `tests-pass` gate job is vague and unenumerated, not factually
wrong — a reader still can't recover the actual list of ~29 gating jobs from
either generation's wording, which is what makes this question unanswerable
from that text, not any incorrect claim within it.

The `httpx_test_suite` Q2 annotations reflect a genuine structural edge
case, not an inconsistency: the pipeline has exactly one named job, so
"which jobs run in parallel" is N/A at the job level for both columns: —
but that one job has a 5-combination Python-version matrix, so there's
still real parallelism to describe. The tool's deterministic output states
the combination count directly ("5 configured combinations"); the naive
baseline conveys the same mechanism narratively ("this job will run
multiple times... named dynamically") without the count, credited as
Partial-plus rather than flatly N/A alongside it.

## Synthesis

**Q5 (secrets/external actions) is the naive baseline's weakest question,
by a clear margin.** It is the only question where the naive baseline
scores an outright No anywhere (2 of 10 applicable pipelines — celery,
nextjs), and its one nominal "Yes" outside those (cpython) is answered
*wrong* rather than right, tying back to this evaluation's single
confirmed False fact. Across the other four questions, the naive baseline's
failures are uniformly softer — Partial, not No: it degrades gracefully on
"which jobs run in parallel" (Partial in 6 of 7 applicable cases) and "what
must finish before deployment" (Partial or No only on the two largest,
most job-dense pipelines), but it never flatly fails to address them the
way it does with secrets. **Both of the naive baseline's outright Q5
failures are specifically credential/token omissions** — `CODECOV_TOKEN`
and `GITHUB_TOKEN`/`KV_REST_API_*` — not a coincidence of which two
pipelines happened to be complex: the naive baseline's unconstrained "explain
this pipeline" framing invites it to narrate *what a pipeline does*
(upload coverage, check out code, call an action) without ever surfacing
*what credential that requires*, since the credential is incidental to the
narrative rather than a fact the prompt directs it to inventory. The tool's
fact-driven `SECRETS REQUIRED` section has no equivalent gap — it enumerates
required secrets structurally rather than narrating around them, and scores
Yes on Q5 in every applicable case except two Partials (`pre_commit_main`,
`cpython_reusable_macos`), neither of which is a full miss.

**This complements, and adds real nuance to, the corrected 46.3%-Missing /
0.5%-False fact-coverage framing in `evaluation/tier4_findings/REPORT.md`.**
That report's headline claim — the naive baseline's primary weakness is
completeness, not confident fabrication — holds up under this different,
usability-shaped lens too: most of the answerability gaps here are Partial
softenings of the same completeness problem, not new instances of
fabrication. But Q5 shows the completeness gap isn't evenly distributed:
it concentrates specifically on credentials and external-action attribution,
the one category where an incomplete narrative summary is most likely to
leave a reader with an actively misleading impression of what a pipeline
needs to run securely (silence on a required secret, or — in cpython's
case — a wrong claim about how a dependency is pinned). A reader who takes
the naive baseline's account of *what a pipeline does* as also a complete
account of *what it requires* is exactly the population this specific
weakness would mislead, even though the aggregate fact-level error rate
stays at 0.5%.

## Threats to validity

The same caveats as `evaluation/tier4_findings/REPORT.md` apply: scoring
was performed by this project's sole author, not blind reviewers, and this
table's source scoring conversation is itself external to this repository
(recorded here as a citable, committed artifact for the first time). The
three spot-checks above independently confirm the table's most load-bearing
claims (the Q5 pattern this synthesis rests on) against this repository's
own primary sources; the remaining cells were not independently
re-verified fact-by-fact against `evaluation/tier4_scoring/*.scoring.md`
line by line, the way the 201-fact checklist scoring was.
