"""
evaluation.naive_baseline — Tier 4's condition 3: raw YAML dumped straight
into an LLM with a generic, unengineered "explain this" prompt.

This module exists solely to give condition 2 (structured text ->
LLM-polished, via `llm/gemini_provider.py`) something fair to be compared
against in the pre-registered fact-checklist protocol (PR #43,
`EVALUATION_PLAN.md` Method 9). It deliberately violates this project's
central architectural claim -- the LLM never sees raw YAML, only
already-extracted, structurally-validated IR facts -- on purpose, because
that is exactly the variable Tier 4's condition-2-vs-3 comparison is
designed to isolate.

Contract:
- No `parsers/`, `ir/`, or `generators/` module is imported or called
  anywhere in this file. Input is the raw YAML file's text content, read
  directly from disk. This is enforced by convention here and verified by
  `tests/test_naive_baseline.py`'s isolation test (see below).
- Must NEVER be reachable from Tool 1's or Tool 2's real document-
  generation path. `tests/test_naive_baseline.py::test_tool1_and_tool2_never_import_naive_baseline`
  is a static, `ast`-based guard for this -- not just a documentation
  promise.
- Fairness requirement: this module must use the same underlying LLM
  model and comparable generation settings (model string, temperature) as
  condition 2's `llm/gemini_provider.py`. Achieved by construction, not by
  convention: `generate_naive_baseline` accepts (or default-constructs) a
  real `llm.gemini_provider.GeminiProvider` and reads its `model_name`/
  `temperature` directly, then calls the exact same
  `llm.gemini_provider._generate_once` low-level helper `GeminiProvider
  ._call_once` itself calls for condition 2 -- so if `DEFAULT_MODEL`/
  `DEFAULT_TEMPERATURE` ever change, both conditions change together,
  automatically, with no second constant to keep in sync.
  **`timeout_s` is deliberately excluded from this parity requirement.**
  Condition 3's prompt is unavoidably larger than condition 2's -- raw,
  unfiltered YAML vs. condition 2's already-extracted, compact structured
  text -- purely as a structural consequence of what condition 3 is
  testing, so it legitimately needs more wall-clock time to complete, the
  same way it needs a larger implicit token budget. A longer timeout
  doesn't change *what* the model is allowed to produce (that's what
  model/temperature parity guards against); it only changes whether an
  oversized prompt gets the chance to finish at all. `generate_naive_baseline`
  therefore uses its own `NAIVE_TIMEOUT_S` (60.0s, 3x `LLMProvider`'s
  class default of 20.0s -- see `llm/base.py`), not `provider.timeout_s`;
  condition 2's `GeminiProvider._call_once` is untouched by this and keeps
  using `provider.timeout_s` as before. Found empirically: a 39KB/1091-line
  held-out pipeline (`nextjs_build_and_test.yml`) hit `504 DEADLINE_EXCEEDED`
  twice at the 20.0s default (~37s elapsed across both attempts) while
  condition 2 succeeded on the same file in 12.2s -- confirming the gap is
  specifically "much larger unfiltered prompt," not a general API issue.
- Does NOT subclass `llm.base.LLMProvider` and does NOT call
  `GeminiProvider.beautify()`/`_call_once()` anywhere -- that class's
  entire public contract (`_call_once(structured_text: str, pipeline:
  Pipeline)`, `beautify()`'s docstring) is IR-fact-rewriting-shaped.
  Forcing raw YAML through it (even by passing `pipeline=None`) would be
  exactly the kind of "make it superficially fit" move this module exists
  to avoid. Instead, `generate_naive_baseline` has its own small retry/
  fallback loop that behaviorally mirrors `LLMProvider.beautify()`'s
  contract (same `max_retries` from the provider, same `is_available()`
  skip, same empty-response-counts-as-failure, same "fallback returns the
  original input unchanged" convention -- here, the raw YAML text) without
  inheriting from or calling into that class.
- Held-out boundary: this module intentionally does NOT call
  `evaluation._path_guard.assert_not_held_out()` -- unlike Tier 1/2's
  evaluation entry points, this function's entire purpose is to eventually
  run against `evaluation/held_out_workflows/` once Tier 4 execution
  itself happens (a separate, later task). "Don't run this against
  held-out data" is a constraint on this development session, not a
  permanent restriction the module should enforce on itself.
- Logging: reuses `tool1.single_pipeline._log_llm_call` and
  `DEFAULT_LLM_LOG_PATH` exactly as-is, so condition 3 records land in the
  same `evaluation/llm_call_log.jsonl` structure as condition 2's, with a
  distinct `prompt_version` (`NAIVE_PROMPT_VERSION`, not
  `llm.base.PROMPT_VERSION`) so the two conditions' records are
  distinguishable after the fact.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from llm.base import LLMResult
from llm.gemini_provider import GeminiProvider, _generate_once

NAIVE_PROMPT_VERSION = "naive-v1"  # distinct from llm/base.py's PROMPT_VERSION ("v1"),
                                    # so log records can tell condition 2 and 3 apart

NAIVE_TIMEOUT_S = 60.0  # 3x LLMProvider's class default (20.0, llm/base.py) -- deliberately
                         # NOT provider.timeout_s. See module docstring's "Fairness
                         # requirement" note for why timeout is excluded from the
                         # model/temperature parity condition 3 must maintain with
                         # condition 2.


def _build_naive_prompt(yaml_text: str) -> str:
    return f"Explain what this CI/CD pipeline does:\n\n{yaml_text}"
    # No system_instruction at all (see generate_naive_baseline -- None is
    # passed to _generate_once). This is the entire prompt: no rules, no
    # "don't hallucinate" instructions, no formatting constraints, no
    # NO_OVERVIEW escape hatch. A developer pasting YAML into a chat and
    # asking "explain this" doesn't set a system prompt either -- adding
    # any guardrail here would defeat the point, since the
    # hallucination-rate *difference* between condition 2 and condition 3
    # must be attributable to "constrained IR facts vs. raw YAML", not to
    # condition 3 secretly getting anti-hallucination guardrails
    # condition 2's SYSTEM_PROMPT also has, just phrased differently.


def generate_naive_baseline(
    yaml_path: str,
    provider: Optional[GeminiProvider] = None,
    timeout_s: Optional[float] = None,
) -> LLMResult:
    """Condition 3: dump raw YAML into an LLM with a generic prompt, no
    parser/IR/generators involved at all. Returns llm.base.LLMResult
    (reused, not a parallel type) so it slots into the same
    logging/scoring plumbing as condition 2. Logs to
    evaluation/llm_call_log.jsonl via tool1.single_pipeline._log_llm_call.

    `timeout_s` defaults to `NAIVE_TIMEOUT_S` (60.0), not `provider.timeout_s`
    -- see module docstring's "Fairness requirement" note. Pass an explicit
    value to override (e.g. for testing).
    """
    # Local import: tool1.single_pipeline is only needed for _log_llm_call,
    # and importing it lazily keeps this module's own import graph minimal
    # (no parser/ir/generators import at module load time either way,
    # since single_pipeline.py itself only imports generators/ir at its
    # own module level -- this is a belt-and-suspenders readability choice,
    # not a functional requirement).
    from tool1.single_pipeline import _log_llm_call

    yaml_text = Path(yaml_path).read_text(encoding="utf-8")
    pipeline_name = Path(yaml_path).stem

    if provider is None:
        provider = GeminiProvider()
    effective_timeout_s = NAIVE_TIMEOUT_S if timeout_s is None else timeout_s

    start = time.monotonic()
    common = dict(
        provider_name=provider.provider_name,
        model=provider.model_name,
        temperature=provider.temperature,
        prompt_version=NAIVE_PROMPT_VERSION,
    )

    if not provider.is_available():
        result = LLMResult(
            text=yaml_text,
            used_fallback=True,
            latency_ms=(time.monotonic() - start) * 1000,
            retry_count=0,
            error=f"{provider.provider_name} not configured",
            **common,
        )
        _log_llm_call(yaml_path, pipeline_name, result)
        return result

    last_error: Optional[str] = None
    for attempt in range(provider.max_retries + 1):
        try:
            response = _generate_once(
                provider._client, provider.model_name, provider.temperature,
                effective_timeout_s, None, _build_naive_prompt(yaml_text),
            )
            if response.text and response.text.strip():
                result = LLMResult(
                    text=response.text.strip(),
                    used_fallback=False,
                    latency_ms=(time.monotonic() - start) * 1000,
                    retry_count=attempt,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    **common,
                )
                _log_llm_call(yaml_path, pipeline_name, result)
                return result
            last_error = "empty response"
        except Exception as exc:  # deliberately broad: any failure must fall back, never crash the caller
            last_error = f"{type(exc).__name__}: {exc}"

    result = LLMResult(
        text=yaml_text,
        used_fallback=True,
        latency_ms=(time.monotonic() - start) * 1000,
        retry_count=provider.max_retries,
        error=last_error,
        **common,
    )
    _log_llm_call(yaml_path, pipeline_name, result)
    return result
