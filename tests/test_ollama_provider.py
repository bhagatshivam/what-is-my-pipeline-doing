"""
tests/test_ollama_provider.py — llm.ollama_provider.OllamaProvider.

Interface-only stub (see module docstring in llm/ollama_provider.py) —
these tests confirm it's a genuine, safe LLMProvider: is_available() is
always False, so beautify() falls back cleanly without ever invoking
_call_once (which would raise NotImplementedError if it were reached).
This is the proof that llm.base.LLMProvider is swappable even for an
intentionally-incomplete provider, not just for GeminiProvider.
"""

import pytest

from ir.schema import Pipeline, SourcePlatform
from llm.base import LLMProvider
from llm.ollama_provider import OllamaProvider

STRUCTURED_TEXT = "Pipeline: Example\nSource: example.yml (GitHub Actions)\n"


def _pipeline():
    return Pipeline(name="Example", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="example.yml")


def test_is_instance_of_llm_provider():
    assert isinstance(OllamaProvider(), LLMProvider)


def test_is_available_is_always_false():
    assert OllamaProvider().is_available() is False


def test_call_once_raises_not_implemented_directly():
    with pytest.raises(NotImplementedError):
        OllamaProvider()._call_once(STRUCTURED_TEXT, _pipeline())


def test_beautify_falls_back_cleanly_without_ever_calling_call_once(monkeypatch):
    provider = OllamaProvider()

    def fail_if_called(structured_text, pipeline):
        pytest.fail("_call_once must never be invoked when is_available() is False")

    monkeypatch.setattr(provider, "_call_once", fail_if_called)

    result = provider.beautify(STRUCTURED_TEXT, _pipeline())

    assert result.used_fallback is True
    assert result.text == STRUCTURED_TEXT
    assert result.retry_count == 0
    assert result.provider_name == "ollama"


def test_default_model_name():
    assert OllamaProvider().model_name == "llama3.1:8b"
