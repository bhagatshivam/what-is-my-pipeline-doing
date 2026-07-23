"""
llm.base — swappable LLM beautification interface. Layer 4 of PROJECT_PLAN.md.

Contract:
- A provider's only job is to rewrite `generators.text_generator.generate_text()`'s
  output (already deterministically extracted and structurally validated by
  Python) into prose. `pipeline` is passed alongside it for logging/framing
  metadata only (e.g. `pipeline.name`) — it is NEVER a second source of facts
  to draw prompt content from. This is a hard architectural boundary, not a
  style preference: every current and future `_call_once` implementation
  must build its prompt from `structured_text` alone. This is what keeps the
  "the LLM never sees raw YAML, only already-verified facts" claim in
  PROJECT_PLAN.md's "Why This Is Not Just 'Ask Claude/Gemini to Read the
  YAML'" section true at the code level, not just in prose.
- `beautify()` is the only public entrypoint and is concrete, not abstract —
  every subclass gets the same fallback contract for free, rather than each
  provider having to reimplement it (and risk getting it subtly wrong):
  - Up to `max_retries` extra attempts after the first, each calling the
    subclass's `_call_once()`.
  - If `is_available()` is False, the retry loop is skipped entirely
    (`retry_count=0`) rather than retrying a call that's guaranteed to fail
    for a static reason (e.g. no API key configured).
  - An empty or whitespace-only response counts as failure, same as a raised
    exception.
  - On final failure, returns an `LLMResult` with `text` set to
    `structured_text` UNCHANGED (byte-identical) and `used_fallback=True`.
    `beautify()` itself never raises — a broken, unreachable, rate-limited,
    or misconfigured provider must never crash Tool 1 or block deterministic
    output.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from ir.schema import Pipeline

PROMPT_VERSION = "v1"  # bump whenever a provider's prompt template text changes


@dataclass
class ProviderResponse:
    """One raw provider attempt's result — returned by `_call_once`."""
    text: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


@dataclass
class LLMResult:
    """Returned by `beautify()`. `used_fallback=True` means `text` is
    `structured_text` unchanged — see module docstring for the fallback
    contract this guarantees."""
    text: str
    used_fallback: bool
    provider_name: str
    model: str
    temperature: float
    prompt_version: str
    latency_ms: float
    retry_count: int
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error: Optional[str] = None


class LLMProvider(ABC):
    """Contract for a Layer 4 provider. See module docstring for the full contract."""

    max_retries: int = 1
    timeout_s: float = 20.0

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def temperature(self) -> float:
        raise NotImplementedError

    def is_available(self) -> bool:
        """Cheap static check (e.g. an API key is configured). Default True.
        When False, `beautify()` skips the retry loop entirely instead of
        retrying a call that cannot succeed."""
        return True

    @abstractmethod
    def _call_once(self, structured_text: str, pipeline: Pipeline) -> ProviderResponse:
        """One raw attempt. Return a `ProviderResponse` on success; raise
        (any Exception) on failure — network error, timeout, or a response
        that fails this provider's own sanity check. Implementations must
        not catch and swallow errors here; `beautify()` is the only caller
        and owns turning a raised exception into the documented fallback.
        Must draw ALL prompt content from `structured_text` only — see
        module docstring."""
        raise NotImplementedError

    def beautify(self, structured_text: str, pipeline: Pipeline) -> LLMResult:
        start = time.monotonic()
        common = dict(
            provider_name=self.provider_name,
            model=self.model_name,
            temperature=self.temperature,
            prompt_version=PROMPT_VERSION,
        )

        if not self.is_available():
            return LLMResult(
                text=structured_text,
                used_fallback=True,
                latency_ms=(time.monotonic() - start) * 1000,
                retry_count=0,
                error=f"{self.provider_name} not configured",
                **common,
            )

        last_error: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._call_once(structured_text, pipeline)
                if response.text and response.text.strip():
                    return LLMResult(
                        text=response.text.strip(),
                        used_fallback=False,
                        latency_ms=(time.monotonic() - start) * 1000,
                        retry_count=attempt,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        **common,
                    )
                last_error = "empty response"
            except Exception as exc:  # deliberately broad: any provider failure must fall back, never crash Tool 1
                last_error = f"{type(exc).__name__}: {exc}"

        return LLMResult(
            text=structured_text,
            used_fallback=True,
            latency_ms=(time.monotonic() - start) * 1000,
            retry_count=self.max_retries,
            error=last_error,
            **common,
        )
