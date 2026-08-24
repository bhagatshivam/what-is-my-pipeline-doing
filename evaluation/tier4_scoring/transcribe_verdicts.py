"""
evaluation.tier4_scoring.transcribe_verdicts -- one-shot, line-based
transcription of the Tier 4 Method 9 fact-by-fact scoring verdicts into
`evaluation/tier4_checklists/*.checklist.yml`.

Deliberately NOT a PyYAML load-modify-dump round trip: these files carry a
header comment block and hand-formatted single-quoted description strings
(some containing escaped `''` for embedded quotes) that a generic YAML
dumper is not guaranteed to reproduce byte-for-byte. Instead this walks each
file line-by-line, tracks the current `fact_id` and which
`condition_N_*:` sub-block it's in, and rewrites only the `outcome: null`
and `detail: ''` lines within a targeted (fact_id, condition) pair --
every other line, including all comments and descriptions, is left
byte-identical.

Default: every fact scores `present` in both condition_1_deterministic and
condition_2_llm_polished (the tool), and `present` in
condition_3_naive_baseline, EXCEPT the explicit exceptions below -- see
PR description / evaluation/tier4_findings/REPORT.md for how these were
derived and independently verified against evaluation/tier4_scoring/*.scoring.md.

Run via: `python3 -m evaluation.tier4_scoring.transcribe_verdicts` (from repo root).
Idempotent-unsafe by design: running twice on already-transcribed files
will no-op (no remaining `outcome: null` lines to match) -- not intended
to be run more than once against a given checklist state.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKLIST_DIR = REPO_ROOT / "evaluation" / "tier4_checklists"

CONDITIONS = ("condition_1_deterministic", "condition_2_llm_polished", "condition_3_naive_baseline")

# ---------------------------------------------------------------------------
# TOOL exceptions -- same verdict in condition_1 and condition_2 (9 Missing)
# ---------------------------------------------------------------------------

_STEP_LEVEL_CONDITION_REASON = (
    "Missing -- a step-level `if:` condition; step-level conditions are never "
    "rendered in either the deterministic or LLM-polished output "
    "(generators/text_generator.py's _step_lines has no step-level Condition "
    "path -- see LIMITATIONS.md's step-level-condition entry)."
)

TOOL_EXCEPTIONS: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("cpython_reusable_macos.trigger.1", "both"): (
        "missing",
        "Missing -- the deterministic/LLM-polished text names both inputs "
        "(`free-threading`, `os`: 'Can be called by other workflows as a "
        "reusable workflow — inputs: free-threading, os') but never states "
        "their types (boolean/string), required/optional status, or default "
        "value. Verified against evaluation/tier4_scoring/"
        "cpython_reusable_macos.scoring.md, Conditions B/C.",
    ),
    ("cpython_reusable_macos.job.1", "both"): (
        "missing",
        "Missing -- job existence, runner, and step count (9) are stated, "
        "but the dynamic job-level `name:` expression, `timeout-minutes: 60`, "
        "and the count of steps carrying an `if:` condition are never stated "
        "anywhere in the output. Verified against evaluation/tier4_scoring/"
        "cpython_reusable_macos.scoring.md, Conditions B/C.",
    ),
    ("cpython_reusable_macos.step.2", "both"): (
        "missing",
        "Missing -- the step name 'Check compiler warnings' is stated, but "
        "its gating `if:` condition is never surfaced (step-level conditions "
        "are out of scope for _step_lines). Verified against evaluation/"
        "tier4_scoring/cpython_reusable_macos.scoring.md, Conditions B/C.",
    ),
    ("cpython_reusable_macos.condition.1", "both"): ("missing", _STEP_LEVEL_CONDITION_REASON),
    ("vscode_pr.condition.1", "both"): ("missing", _STEP_LEVEL_CONDITION_REASON),
    ("vscode_pr.condition.2", "both"): ("missing", _STEP_LEVEL_CONDITION_REASON),
    ("vscode_pr.job.17", "both"): (
        "missing",
        "Missing -- runner and job-level permissions are stated, but the "
        "18-step list is capped at 10 (_STEP_LIST_CAP) with '... and 8 more "
        "steps'; the specific always()-conditioned artifact-upload step "
        "falls beyond the cap and is never named. Verified against "
        "evaluation/tier4_scoring/vscode_pr.scoring.md, Conditions A/B.",
    ),
    ("vscode_pr.step.1", "both"): (
        "missing",
        "Missing -- the 'compile' job's 12-step list is capped at 10 "
        "(_STEP_LIST_CAP) with '... and 2 more steps'; 'Check cyclic "
        "dependencies' falls beyond the cap and is never named. Verified "
        "against evaluation/tier4_scoring/vscode_pr.scoring.md, Conditions A/B.",
    ),
    ("nextjs_build_and_test.trigger.2", "both"): (
        "missing",
        "Missing -- shared, upstream fact-sheet limitation: the PR "
        "event-type restriction (opened/synchronize) is absent from "
        "generate_text()'s own WHEN IT RUNS section ('Runs on every pull "
        "request'), so no candidate/condition can state it without adding "
        "a fact not in the fact sheet. Already documented in "
        "evaluation/rewrite_experiment/REPORT.md.",
    ),
}

# ---------------------------------------------------------------------------
# NAIVE BASELINE exceptions -- condition_3 only
# ---------------------------------------------------------------------------

_NEVER_NAMED = "Missing -- naive baseline (condition 3, raw YAML -> LLM) never names this {kind} individually."

NAIVE_MISSING_DETAIL: Dict[str, str] = {}
NAIVE_FALSE_DETAIL: Dict[str, str] = {}

# celery_python_package
NAIVE_MISSING_DETAIL["celery_python_package.secret.1"] = _NEVER_NAMED.format(kind="secret")

# scipy_linux: dependency.1-11 + condition.1
for i in range(1, 12):
    NAIVE_MISSING_DETAIL[f"scipy_linux.dependency.{i}"] = _NEVER_NAMED.format(kind="dependency edge")
NAIVE_MISSING_DETAIL["scipy_linux.condition.1"] = _NEVER_NAMED.format(kind="condition")

# vscode_pr: job.1-14, job.16-18, secret.2-4
for i in list(range(1, 15)) + [16, 17, 18]:
    NAIVE_MISSING_DETAIL[f"vscode_pr.job.{i}"] = _NEVER_NAMED.format(kind="job")
for i in (2, 3, 4):
    NAIVE_MISSING_DETAIL[f"vscode_pr.secret.{i}"] = _NEVER_NAMED.format(kind="secret")

# nextjs_build_and_test: job.8,10,11,13,22,23,30,33,34,37
for i in (8, 10, 11, 13, 22, 23, 30, 33, 34, 37):
    NAIVE_MISSING_DETAIL[f"nextjs_build_and_test.job.{i}"] = _NEVER_NAMED.format(kind="job")

# nextjs_build_and_test: dependency.3,8,9,46-50,72-74,85-87,89-91,102-104
_nextjs_missing_dep_ids = (
    [3, 8, 9]
    + list(range(46, 51))
    + list(range(72, 75))
    + list(range(85, 88))
    + list(range(89, 92))
    + list(range(102, 105))
)
for i in _nextjs_missing_dep_ids:
    NAIVE_MISSING_DETAIL[f"nextjs_build_and_test.dependency.{i}"] = _NEVER_NAMED.format(kind="dependency edge")

# nextjs_build_and_test: dependency.115-144 -- the tests-pass block.
# CORRECTED to Missing (not False): the naive baseline's only mention of
# tests-pass's dependencies is "This job explicitly lists all critical
# build, lint, and test jobs as dependencies" (evaluation/tier4_scoring/
# nextjs_build_and_test.scoring.md, Condition B) -- confirmed by exhaustive
# search of the full naive-baseline section, no individual job name is ever
# stated as a tests-pass dependency anywhere in that text. An earlier draft
# scored this block False against a misquoted version of that sentence
# ("lists all other jobs") that does not match what the text actually says.
_TESTS_PASS_DETAIL = (
    "Missing -- naive baseline's only mention of tests-pass's dependencies "
    "is the vague blanket statement \"This job explicitly lists all "
    "critical build, lint, and test jobs as dependencies\" "
    "(evaluation/tier4_scoring/nextjs_build_and_test.scoring.md, Condition "
    "B). No individual job name is ever stated as a tests-pass dependency "
    "anywhere in the naive-baseline text, confirmed by exhaustive search. "
    "Same vague-blanket-statement pattern already scored Missing for "
    "scipy_linux's dependency facts under this project's established "
    "individually-named-edge convention."
)
for i in range(115, 145):
    NAIVE_MISSING_DETAIL[f"nextjs_build_and_test.dependency.{i}"] = _TESTS_PASS_DETAIL

# cpython_reusable_macos.job.1 -- the one real naive-baseline False.
NAIVE_FALSE_DETAIL["cpython_reusable_macos.job.1"] = (
    "False -- the naive baseline (evaluation/tier4_scoring/"
    "cpython_reusable_macos.scoring.md, Condition A) states the checkout "
    "step is pinned as `actions/checkout@v7.0.0`, misrepresenting a tag "
    "pin. The real YAML pins `actions/checkout` to a full commit SHA with "
    "a trailing `# v7.0.0` version comment, not to the tag `v7.0.0` "
    "itself -- a concrete misstatement, not just an omission."
)

assert len(NAIVE_MISSING_DETAIL) == 93, f"expected 93 naive-baseline Missing, got {len(NAIVE_MISSING_DETAIL)}"
assert len(NAIVE_FALSE_DETAIL) == 1, f"expected 1 naive-baseline False, got {len(NAIVE_FALSE_DETAIL)}"

FACT_ID_RE = re.compile(r"^- fact_id: (\S+)\s*$")
CONDITION_RE = re.compile(r"^  (condition_[123]_\w+):\s*$")
OUTCOME_RE = re.compile(r"^(\s+)outcome: null\s*$")
DETAIL_RE = re.compile(r"^(\s+)detail: ''\s*$")


def _yaml_single_quote(text: str) -> str:
    """Escape a string for a YAML single-quoted scalar (double any embedded ')."""
    return text.replace("'", "''")


def transcribe_file(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out = []
    current_fact_id = None
    current_condition = None
    changed = 0

    for line in lines:
        fact_match = FACT_ID_RE.match(line)
        if fact_match:
            current_fact_id = fact_match.group(1)
            current_condition = None
            out.append(line)
            continue

        cond_match = CONDITION_RE.match(line)
        if cond_match:
            current_condition = cond_match.group(1)
            out.append(line)
            continue

        if current_fact_id and current_condition:
            outcome_match = OUTCOME_RE.match(line)
            if outcome_match:
                indent = outcome_match.group(1)
                outcome, _ = _resolve(current_fact_id, current_condition)
                # Quote the scalar: bare `false`/`true`/`null` are YAML 1.1
                # reserved words and would parse back as booleans, not the
                # string outcome value, silently breaking downstream counts.
                out.append(f"{indent}outcome: '{outcome}'\n")
                changed += 1
                continue

            detail_match = DETAIL_RE.match(line)
            if detail_match:
                indent = detail_match.group(1)
                _, detail = _resolve(current_fact_id, current_condition)
                if detail:
                    out.append(f"{indent}detail: '{_yaml_single_quote(detail)}'\n")
                else:
                    out.append(line)
                changed += 1
                continue

        out.append(line)

    path.write_text("".join(out), encoding="utf-8")
    return changed


def _resolve(fact_id: str, condition: str) -> Tuple[str, str]:
    """Return (outcome, detail) for a given fact_id/condition, applying exceptions."""
    if condition in ("condition_1_deterministic", "condition_2_llm_polished"):
        key = (fact_id, "both")
        if key in TOOL_EXCEPTIONS:
            return TOOL_EXCEPTIONS[key]
        return "present", ""

    # condition_3_naive_baseline
    if fact_id in NAIVE_FALSE_DETAIL:
        return "false", NAIVE_FALSE_DETAIL[fact_id]
    if fact_id in NAIVE_MISSING_DETAIL:
        return "missing", NAIVE_MISSING_DETAIL[fact_id]
    return "present", ""


def main() -> None:
    total_changed = 0
    for path in sorted(CHECKLIST_DIR.glob("*.checklist.yml")):
        changed = transcribe_file(path)
        print(f"{path.name}: {changed} outcome/detail lines rewritten")
        total_changed += changed
    print(f"Total: {total_changed} lines rewritten across {len(list(CHECKLIST_DIR.glob('*.checklist.yml')))} files")


if __name__ == "__main__":
    main()
