"""
llm.ollama_provider — local Ollama LLM provider (stub; future work per BUILD_PLAN.md).

Interface-only: local LLM mode stays documented future work per the
existing scope decision in BUILD_PLAN.md's Phase 5. This class exists only
to prove `llm.base.LLMProvider` is genuinely swappable — including the
case where a provider is intentionally incomplete — not to run anything.
`is_available()` is always False, so `beautify()` always falls back
cleanly without ever calling `_call_once`.
"""

from __future__ import annotations

from ir.schema import Pipeline
from llm.base import LLMProvider, ProviderResponse

DEFAULT_MODEL = "llama3.1:8b"


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = DEFAULT_MODEL):
        self._model = model

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def temperature(self) -> float:
        return 0.2

    def is_available(self) -> bool:
        return False

    def _call_once(self, structured_text: str, pipeline: Pipeline) -> ProviderResponse:
        raise NotImplementedError(
            "OllamaProvider is a documented future-work stub — see BUILD_PLAN.md Phase 5"
        )
