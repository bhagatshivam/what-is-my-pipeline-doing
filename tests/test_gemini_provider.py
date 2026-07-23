"""
tests/test_gemini_provider.py — llm.gemini_provider.GeminiProvider.

Unit tests inject a fake `client` (constructor param) so no real network
call, real SDK client, or API key is ever needed — these run in normal
CI. The `google.genai.types` config classes themselves ARE used for
real (they're plain config/data objects with no network behaviour), since
google-genai is a hard requirements.txt dependency as of this change.

A separate, real end-to-end test is marked @pytest.mark.slow and skipped
unless a real GEMINI_API_KEY is present in the environment — mirrors the
existing mermaid-cli slow-test precedent in tests/test_single_pipeline.py
exactly. It reads the real pre-test env var at module import time (before
tests/conftest.py's autouse fixture clears it for the test's own scope).
"""

import os

import pytest

from ir.schema import Pipeline, SourcePlatform
from llm.gemini_provider import SYSTEM_PROMPT, GeminiProvider, _build_user_prompt

# Captured at collection time, before tests/conftest.py's autouse
# _clear_gemini_env fixture runs for any individual test.
_REAL_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

STRUCTURED_TEXT = (
    "Pipeline: Check dist\n"
    "Source: tests/fixtures/checkout_check_dist.yml (GitHub Actions)\n"
)


def _pipeline():
    return Pipeline(name="Check dist", source_platform=SourcePlatform.GITHUB_ACTIONS,
                     source_file="tests/fixtures/checkout_check_dist.yml")


class _FakeUsage:
    def __init__(self, prompt_token_count, candidates_token_count):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count


class _FakeResponse:
    def __init__(self, text, usage_metadata=None):
        self.text = text
        self.usage_metadata = usage_metadata


class _FakeModels:
    def __init__(self, response_or_exc):
        self._response_or_exc = response_or_exc
        self.last_call_kwargs = None

    def generate_content(self, **kwargs):
        self.last_call_kwargs = kwargs
        if isinstance(self._response_or_exc, Exception):
            raise self._response_or_exc
        return self._response_or_exc


class _FakeClient:
    def __init__(self, response_or_exc):
        self.models = _FakeModels(response_or_exc)


def _provider_with(response_or_exc, **kwargs):
    client = _FakeClient(response_or_exc)
    return GeminiProvider(api_key="fake-key-not-real", client=client, **kwargs), client


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def test_build_user_prompt_wraps_structured_text_in_fact_sheet_delimiters():
    prompt = _build_user_prompt(STRUCTURED_TEXT)
    assert "FACT SHEET:" in prompt
    assert "<<<" in prompt and ">>>" in prompt
    assert STRUCTURED_TEXT in prompt


def test_call_once_sends_system_prompt_and_exact_structured_text():
    provider, client = _provider_with(_FakeResponse("Some prose about the pipeline."))

    provider._call_once(STRUCTURED_TEXT, _pipeline())

    kwargs = client.models.last_call_kwargs
    assert kwargs["config"].system_instruction == SYSTEM_PROMPT
    assert STRUCTURED_TEXT in kwargs["contents"]


def test_call_once_uses_fixed_low_temperature():
    provider, client = _provider_with(_FakeResponse("prose"))
    provider._call_once(STRUCTURED_TEXT, _pipeline())
    assert client.models.last_call_kwargs["config"].temperature == provider.temperature == 0.2


# ---------------------------------------------------------------------------
# Response handling
# ---------------------------------------------------------------------------

def test_call_once_success_returns_text_and_token_counts():
    provider, _ = _provider_with(_FakeResponse("Clean prose.", usage_metadata=_FakeUsage(42, 17)))

    result = provider._call_once(STRUCTURED_TEXT, _pipeline())

    assert result.text == "Clean prose."
    assert result.input_tokens == 42
    assert result.output_tokens == 17


def test_call_once_missing_usage_metadata_gives_none_token_counts():
    provider, _ = _provider_with(_FakeResponse("Clean prose.", usage_metadata=None))

    result = provider._call_once(STRUCTURED_TEXT, _pipeline())

    assert result.input_tokens is None
    assert result.output_tokens is None


@pytest.mark.parametrize("bad_text", ["", "   ", "NO_OVERVIEW"])
def test_call_once_empty_or_no_overview_raises_for_beautify_to_catch(bad_text):
    provider, _ = _provider_with(_FakeResponse(bad_text))

    with pytest.raises(ValueError):
        provider._call_once(STRUCTURED_TEXT, _pipeline())


def test_beautify_falls_back_cleanly_on_no_overview_response():
    # End-to-end through beautify(), not just _call_once, proving the
    # NO_OVERVIEW escape hatch triggers the documented fallback contract
    # rather than crashing or leaking "NO_OVERVIEW" into the document.
    provider, _ = _provider_with(_FakeResponse("NO_OVERVIEW"))

    result = provider.beautify(STRUCTURED_TEXT, _pipeline())

    assert result.used_fallback is True
    assert result.text == STRUCTURED_TEXT


def test_beautify_falls_back_cleanly_on_sdk_exception():
    provider, _ = _provider_with(RuntimeError("simulated API failure"))

    result = provider.beautify(STRUCTURED_TEXT, _pipeline())

    assert result.used_fallback is True
    assert result.text == STRUCTURED_TEXT
    assert "simulated API failure" in result.error


# ---------------------------------------------------------------------------
# Config / availability
# ---------------------------------------------------------------------------

def test_is_available_false_without_api_key_or_client():
    provider = GeminiProvider(api_key=None)
    assert provider.is_available() is False


def test_is_available_true_with_injected_client():
    provider, _ = _provider_with(_FakeResponse("prose"))
    assert provider.is_available() is True


def test_model_defaults_to_gemini_2_0_flash():
    provider = GeminiProvider(api_key=None)
    assert provider.model_name == "gemini-2.0-flash"


def test_model_env_var_override(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-flash")
    provider = GeminiProvider(api_key=None)
    assert provider.model_name == "gemini-1.5-flash"


# ---------------------------------------------------------------------------
# Live end-to-end smoke test — manual/local only, never in CI's default run.
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.skipif(not _REAL_GEMINI_API_KEY, reason="requires a live GEMINI_API_KEY")
def test_live_gemini_call_against_checkout_check_dist_fixture():
    from generators.text_generator import generate_text
    from parsers.github_actions import GitHubActionsParser

    pipeline = GitHubActionsParser().parse("tests/fixtures/checkout_check_dist.yml")
    structured_text = generate_text(pipeline)

    provider = GeminiProvider(api_key=_REAL_GEMINI_API_KEY)
    result = provider.beautify(structured_text, pipeline)

    assert result.used_fallback is False, result.error
    assert result.text.strip() != ""
