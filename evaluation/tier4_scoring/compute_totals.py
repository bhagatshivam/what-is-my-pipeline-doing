"""
evaluation.tier4_scoring.compute_totals -- reads all 10
evaluation/tier4_checklists/*.checklist.yml files directly and sums
Present/Missing/False per condition across every fact, programmatically.
No hand arithmetic: this is the authoritative source for Tier 4's headline
numbers, run fresh whenever the checklists change.

Run via: `python3 -m evaluation.tier4_scoring.compute_totals` (from repo root).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKLIST_DIR = REPO_ROOT / "evaluation" / "tier4_checklists"

CONDITIONS = ("condition_1_deterministic", "condition_2_llm_polished", "condition_3_naive_baseline")


def main() -> None:
    totals = {c: Counter() for c in CONDITIONS}
    per_pipeline = {}
    total_facts = 0

    for path in sorted(CHECKLIST_DIR.glob("*.checklist.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        facts = data["facts"]
        total_facts += len(facts)
        pipeline_counts = {c: Counter() for c in CONDITIONS}
        for fact in facts:
            for c in CONDITIONS:
                outcome = fact[c]["outcome"]
                if outcome is None:
                    outcome = "null"
                totals[c][outcome] += 1
                pipeline_counts[c][outcome] += 1
        per_pipeline[data["workflow_id"]] = (len(facts), pipeline_counts)

    print(f"Total facts across {len(per_pipeline)} pipelines: {total_facts}\n")

    print("Per-pipeline fact counts:")
    for name, (n, _) in per_pipeline.items():
        print(f"  {name}: {n}")
    print()

    for c in CONDITIONS:
        counts = totals[c]
        present = counts.get("present", 0)
        missing = counts.get("missing", 0)
        false = counts.get("false", 0)
        null = counts.get("null", 0)
        print(f"{c}:")
        print(f"  present={present} missing={missing} false={false}"
              + (f" null={null}" if null else ""))
        print(f"  {present}/{missing}/{false}"
              f"  ({present/total_facts*100:.1f}% / {missing/total_facts*100:.1f}% / {false/total_facts*100:.1f}%)")
        assert present + missing + false + null == total_facts, (
            f"{c}: counts don't sum to total_facts ({present}+{missing}+{false}+{null} != {total_facts})"
        )
        print()


if __name__ == "__main__":
    main()
