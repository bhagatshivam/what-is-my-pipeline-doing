"""llm — Layer 4: swappable LLM beautification providers."""

from __future__ import annotations

import os
from typing import Optional

from llm.base import LLMProvider


def get_default_provider() -> Optional[LLMProvider]:
    """Return the configured LLMProvider for this environment, or None if
    no provider is configured (e.g. GEMINI_API_KEY unset). Callers must
    treat None as "skip Layer 4, deterministic output only" — never as an
    error. The single call site for this is
    tool1.single_pipeline._build_documentation()."""
    if os.environ.get("GEMINI_API_KEY"):
        from llm.gemini_provider import GeminiProvider  # lazy: avoid requiring the SDK when unused

        return GeminiProvider()
    return None
