"""
scripts/run_variance_check.py — Tier 1 Method 4 (determinism/variance
of LLM output): runs 10 repeated `beautify()` calls at the tool's
production temperature (0.2) against 3 fixtures and writes
evaluation/variance_results.md.

Manual, deliberate action only -- never invoked by the test suite (see
tests/test_evaluation_variance_check.py for the pytest regression, which
uses a fake provider and never makes a live call). Requires a real
GEMINI_API_KEY in the environment; without one, every row will simply
carry a "GEMINI_API_KEY not set" error and no live call happens.

Fixtures were chosen to probe PR 2's finding that LLM-polished FKGL swings
unevenly per fixture (see evaluation/readability_results.md):
  - pytorch_lint.yml     -- 6.42-grade-level drop under LLM polish
  - setup_python_test.yml -- 4.12-grade-level rise
  - rust_ci.yml          -- 0.31, essentially flat, control

Cost: 30 total live calls per run. At the free-tier limit of 5
requests/minute for gemini-2.5-flash, this is ~6 minutes wall-clock
minimum. This script catches Gemini's 429 RESOURCE_EXHAUSTED response,
sleeps for the API-provided retryDelay hint (or 60s if absent), logs the
pause plainly, and retries -- rate-limiting is a normal (not exceptional)
mid-run event on this tier.

Usage:
    python scripts/run_variance_check.py
"""

import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
RESULTS_PATH = os.path.join(REPO_ROOT, "evaluation", "variance_results.md")

sys.path.insert(0, REPO_ROOT)

from evaluation.variance_check import (  # noqa: E402
    VarianceResult,
    score_workflow_variance,
)
from llm import get_default_provider  # noqa: E402
from llm.base import LLMProvider, LLMResult  # noqa: E402

_FIXTURES = [
    ("pytorch_lint.yml", "PR 2 showed a 6.42-grade-level drop under LLM polish"),
    ("setup_python_test.yml", "PR 2 showed a 4.12-grade-level rise"),
    ("rust_ci.yml", "PR 2 showed a 0.31, essentially flat, control"),
]
_REPEATS = 10
_DEFAULT_RETRY_DELAY_SECONDS = 60
_RETRY_DELAY_RE = re.compile(r"'retryDelay':\s*'(\d+)s'")


_HEADER = (
    "This variance check answers the question raised by PR 2's readability "
    "results (evaluation/readability_results.md): are the per-fixture FKGL "
    "swings between deterministic and LLM-polished text real repeatable "
    "effects of each fixture's content, or run-to-run noise on a single call?\n\n"
    "Scope: FKGL only (per-metric variance for Reading Ease/Gunning Fog is "
    "recoverable after the fact from each row's stored raw prose without "
    "spending fresh quota). Pure stochastic variance at the tool's production "
    "temperature (0.2) -- not a temperature sweep.\n\n"
    "Interpretation rule (fixed, stated explicitly so the label isn't opaque):\n"
    "  range < 1.0            -> essentially deterministic\n"
    "  1.0 <= range < 3.0     -> moderate drift\n"
    "  range >= 3.0           -> large drift"
)


class _RetryingProvider(LLMProvider):
    """Wraps whatever get_default_provider() returns and catches
    Gemini-shaped 429 RESOURCE_EXHAUSTED errors from its own beautify(),
    sleeping for the API-provided retryDelay hint (or a sane default)
    before retrying. This lives here in the script, not in
    llm/base.py -- rate-limit backoff is a script-side concern (the
    module's beautify() correctly counts any failure toward its own
    fallback contract; we don't want to make that contract lie by
    silently succeeding after a long sleep). Non-429 failures fall
    through to the wrapped provider's normal fallback behaviour."""

    def __init__(self, inner: LLMProvider):
        self._inner = inner

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def temperature(self) -> float:
        return self._inner.temperature

    def is_available(self) -> bool:
        return self._inner.is_available()

    def _call_once(self, structured_text, pipeline):
        return self._inner._call_once(structured_text, pipeline)

    def beautify(self, structured_text, pipeline) -> LLMResult:
        for _ in range(6):  # up to 6 tries per repeat -- practical safety bound
            result = self._inner.beautify(structured_text, pipeline)
            if not result.used_fallback:
                return result
            error = result.error or ""
            if "RESOURCE_EXHAUSTED" not in error and "429" not in error:
                return result  # non-rate-limit failure: pass through to normal fallback path
            delay_match = _RETRY_DELAY_RE.search(error)
            delay = int(delay_match.group(1)) if delay_match else _DEFAULT_RETRY_DELAY_SECONDS
            print(f"  [rate-limited, sleeping {delay}s before retry]", flush=True)
            time.sleep(delay)
        return result


def _format_row(vr: VarianceResult) -> str:
    if not vr.samples:
        err = vr.errors[0] if vr.errors else "no samples"
        return (
            f"| {vr.fixture} | {vr.deterministic_fkgl:.2f} | -- | -- | -- | -- | -- "
            f"| no samples | {err} |"
        )
    return (
        f"| {vr.fixture} | {vr.deterministic_fkgl:.2f} "
        f"| {vr.mean:.2f} | {vr.std_dev:.2f} "
        f"| {vr.min:.2f} | {vr.max:.2f} | {vr.range:.2f} "
        f"| {vr.interpretation} "
        f"| {len(vr.errors)} error(s) |"
    )


def _format_raw_block(vr: VarianceResult, reason: str) -> list:
    lines = [f"### {vr.fixture} — {reason}", ""]
    if not vr.samples:
        lines.append(f"No successful samples (errors: {vr.errors}).")
        lines.append("")
        return lines
    lines.append("Raw N=10 FKGL values (`fkgl` per repeat):")
    lines.extend(f"- {s.fkgl:.2f}" for s in vr.samples)
    lines.append("")
    lines.append("Stored raw prose per repeat (for later recomputation of other metrics without spending fresh quota):")
    for i, s in enumerate(vr.samples, start=1):
        lines.append(f"<details><summary>repeat {i} (FKGL {s.fkgl:.2f})</summary>")
        lines.append("")
        lines.append(s.text)
        lines.append("")
        lines.append("</details>")
    if vr.errors:
        lines.append("")
        lines.append(f"Errors during this fixture's run: {vr.errors}")
    lines.append("")
    return lines


def main() -> None:
    provider = get_default_provider()
    if provider is not None:
        provider = _RetryingProvider(provider)

    original_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        results = []
        for filename, reason in _FIXTURES:
            print(f"{filename}: {_REPEATS} repeats -- {reason}", flush=True)
            fixture_path = os.path.join("tests", "fixtures", filename)
            vr = score_workflow_variance(fixture_path, repeats=_REPEATS, provider=provider)
            results.append((vr, reason))
            print(
                f"  -> mean={vr.mean if vr.mean is None else f'{vr.mean:.2f}'}, "
                f"range={vr.range if vr.range is None else f'{vr.range:.2f}'}, "
                f"errors={len(vr.errors)}",
                flush=True,
            )
    finally:
        os.chdir(original_cwd)

    lines = [
        "# Variance results (Tier 1, Method 4)",
        "",
        _HEADER,
        "",
        "## Summary",
        "",
        "| Fixture | Det. FKGL | LLM FKGL mean (N=10) | Std dev | Min | Max | Range | Interpretation | Notes |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    lines.extend(_format_row(vr) for vr, _ in results)
    lines.append("")
    lines.append("## Per-fixture raw samples")
    lines.append("")
    for vr, reason in results:
        lines.extend(_format_raw_block(vr, reason))

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
