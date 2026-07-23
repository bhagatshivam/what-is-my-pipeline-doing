"""
llm.gemini_provider — Gemini API LLM provider (Google AI Studio free tier).

Uses the `google-genai` SDK, imported lazily (inside this module only) so
nothing that only needs `llm.base`/`llm.ollama_provider`, or a `--no-llm`
run, is forced to have the SDK installed.

Config: `GEMINI_API_KEY` env var (required — `is_available()` is False
without it, see `llm.base.LLMProvider`), `GEMINI_MODEL` env var (optional,
default `gemini-2.0-flash`). Temperature is fixed at 0.2 — this is
rewriting, not creative writing.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from ir.schema import Pipeline
from llm.base import LLMProvider, ProviderResponse

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_TEMPERATURE = 0.2

# `pipeline` is intentionally never referenced below — see llm/base.py's
# module docstring for why. Only `structured_text` (generate_text()'s
# output) ever reaches the prompt.
SYSTEM_PROMPT = """You are a technical writer producing documentation for a
CI/CD pipeline. You will be given a structured, plain-text FACT SHEET that
was extracted and validated by a separate deterministic program — not by
you. Every fact in it is already correct and complete for this task.

Your only job is to rewrite this fact sheet into 2-4 short, clear prose
paragraphs describing what the pipeline does, for a developer who has
never seen it before.

Rules:
- Do not add any fact, number, name, condition, or claim that is not
  already present in the fact sheet below.
- Do not infer, guess, or speculate about intent, security implications,
  or behaviour beyond what the fact sheet states.
- Do not omit a trigger, job, or secret listed in the fact sheet.
- Do not include YAML, code blocks, or markdown headings — plain prose
  paragraphs only.
- If you are unsure how to rewrite the fact sheet safely, respond with
  exactly: NO_OVERVIEW
"""


def _build_user_prompt(structured_text: str) -> str:
    return (
        "FACT SHEET:\n"
        "<<<\n"
        f"{structured_text}"
        ">>>\n\n"
        "Rewrite the FACT SHEET above into prose following the rules."
    )


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        client: Optional[Any] = None,
    ):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self._temperature = temperature
        self._client = client if client is not None else self._build_client()

    def _build_client(self) -> Optional[Any]:
        if not self._api_key:
            return None
        from google import genai  # lazy: only imported when an API key is actually configured

        return genai.Client(api_key=self._api_key)

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def temperature(self) -> float:
        return self._temperature

    def is_available(self) -> bool:
        return self._client is not None

    def _call_once(self, structured_text: str, pipeline: Pipeline) -> ProviderResponse:
        from google.genai import types  # lazy, same reasoning as _build_client

        response = self._client.models.generate_content(
            model=self._model,
            contents=_build_user_prompt(structured_text),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=self._temperature,
                http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000)),  # ms, not seconds
            ),
        )
        text = (response.text or "").strip()
        if not text or text == "NO_OVERVIEW":
            raise ValueError(f"unusable response: {text!r}")

        usage = getattr(response, "usage_metadata", None)
        return ProviderResponse(
            text=text,
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
        )
