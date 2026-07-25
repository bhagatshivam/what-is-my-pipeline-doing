"""
evaluation._path_guard — Phase 7 Step 1: enforced boundary between Tier 1/2
evaluation code and evaluation/held_out_workflows/.

Tier 1/2 methods (golden-file, coverage, diagram-structure, variance,
readability, error injection) are scoped to run against tests/fixtures/
only. evaluation/held_out_workflows/ is reserved for the pre-registered
Tier 4 fact-checklist protocol (EVALUATION_PLAN.md Method 9), whose
validity depends on that set's output staying unseen until that protocol
runs. A coverage or diagram-diff failure printed to a terminal or CI log
would expose exactly the content that protocol needs unseen.

assert_not_held_out() is called as the first line of every Tier 1/2
evaluation entry point that accepts a workflow/fixture path, before any
file I/O. It is not a lint rule or a convention: it raises. Scope note —
this guards the Tier 1/2 evaluation entry points specifically (the ones
listed above); it is not a filesystem-level access control on
evaluation/held_out_workflows/, and does not intercept lower-level calls
such as generators/text_generator.py's generate_text() or
generators/mermaid_generator.py's generate_mermaid() invoked directly.

evaluation/coverage_check.py and evaluation/diagram_diff.py (E2/E3) are
deliberately NOT wired to this guard — they keep their existing Tier
3/4-foundation role (non-circular ground truth scoring against
evaluation/held_out_workflows/, already run once for Round 2), which is
Decision 1's approved reason they "stay untouched" in Phase 7 Step 1.
"""

from __future__ import annotations

from pathlib import Path

HELD_OUT_ROOT = (Path(__file__).parent / "held_out_workflows").resolve()


def assert_not_held_out(path) -> None:
    """Raise ValueError if `path` resolves inside evaluation/held_out_workflows/."""
    resolved = Path(path).resolve()
    if resolved == HELD_OUT_ROOT or HELD_OUT_ROOT in resolved.parents:
        raise ValueError(
            f"Refusing to run Tier 1/2 evaluation against held-out path: {path}"
        )
