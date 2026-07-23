"""
tests/test_llm_base.py — llm.base.LLMProvider's fallback contract.

Uses a _FakeProvider test double rather than any real provider, so these
tests exercise beautify()'s retry/fallback logic in isolation, with no
network, no SDK, no API key.
"""

import pytest

from ir.schema import Pipeline, SourcePlatform
from llm.base import PROMPT_VERSION, LLMProvider, ProviderResponse

STRUCTURED_TEXT = "Pipeline: Example\nSource: example.yml (GitHub Actions)\n"


def _pipeline():
    return Pipeline(name="Example", source_platform=SourcePlatform.GITHUB_ACTIONS, source_file="example.yml")


class _FakeProvider(LLMProvider):
    """Each entry in `responses` is either an Exception instance (raised)
    or a ProviderResponse (returned) for one _call_once attempt, consumed
    in order. `available` controls is_available()."""

    def __init__(self, responses=None, available=True):
        self._responses = list(responses or [])
        self._available = available
        self.call_count = 0

    @property
    def provider_name(self):
        return "fake"

    @property
    def model_name(self):
        return "fake-model"

    @property
    def temperature(self):
        return 0.0

    def is_available(self):
        return self._available

    def _call_once(self, structured_text, pipeline):
        self.call_count += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_beautify_success_on_first_attempt():
    provider = _FakeProvider(responses=[ProviderResponse(text="Some prose.")])
    result = provider.beautify(STRUCTURED_TEXT, _pipeline())

    assert result.used_fallback is False
    assert result.text == "Some prose."
    assert result.retry_count == 0
    assert result.error is None
    assert provider.call_count == 1


def test_beautify_success_after_one_retry():
    provider = _FakeProvider(responses=[ConnectionError("network blip"), ProviderResponse(text="Recovered.")])
    result = provider.beautify(STRUCTURED_TEXT, _pipeline())

    assert result.used_fallback is False
    assert result.text == "Recovered."
    assert result.retry_count == 1
    assert provider.call_count == 2


def test_beautify_exhausts_retries_and_falls_back():
    provider = _FakeProvider(responses=[TimeoutError("timed out"), ValueError("still broken")])
    result = provider.beautify(STRUCTURED_TEXT, _pipeline())

    assert result.used_fallback is True
    assert result.text == STRUCTURED_TEXT  # byte-identical to input, unchanged
    assert result.retry_count == provider.max_retries == 1
    assert "ValueError: still broken" in result.error
    assert provider.call_count == 2


def test_beautify_empty_response_counts_as_failure_and_falls_back():
    provider = _FakeProvider(responses=[ProviderResponse(text=""), ProviderResponse(text="   ")])
    result = provider.beautify(STRUCTURED_TEXT, _pipeline())

    assert result.used_fallback is True
    assert result.text == STRUCTURED_TEXT
    assert result.error == "empty response"
    assert provider.call_count == 2


def test_beautify_never_raises_out_of_call_once():
    provider = _FakeProvider(responses=[RuntimeError("boom"), RuntimeError("boom again")])
    # Must not raise.
    result = provider.beautify(STRUCTURED_TEXT, _pipeline())
    assert result.used_fallback is True


def test_beautify_skips_retry_loop_when_not_available():
    provider = _FakeProvider(responses=[ProviderResponse(text="should never be reached")], available=False)
    result = provider.beautify(STRUCTURED_TEXT, _pipeline())

    assert result.used_fallback is True
    assert result.text == STRUCTURED_TEXT
    assert result.retry_count == 0
    assert "not configured" in result.error
    assert provider.call_count == 0  # _call_once must never be invoked


@pytest.mark.parametrize("used_fallback_case", [True, False])
def test_llm_result_common_fields_populated(used_fallback_case):
    if used_fallback_case:
        provider = _FakeProvider(responses=[ValueError("x"), ValueError("x")])
    else:
        provider = _FakeProvider(responses=[ProviderResponse(text="ok")])

    result = provider.beautify(STRUCTURED_TEXT, _pipeline())

    assert result.used_fallback is used_fallback_case
    assert result.provider_name == "fake"
    assert result.model == "fake-model"
    assert result.temperature == 0.0
    assert result.prompt_version == PROMPT_VERSION
    assert result.latency_ms >= 0
