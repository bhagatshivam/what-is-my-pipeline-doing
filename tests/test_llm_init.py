"""
tests/test_llm_init.py — llm.get_default_provider().

No real API call is made in either branch: constructing google.genai.Client
with a fake key does no network I/O (only an actual generate_content call
would), so the "key present" case is safe to run in CI.
"""

from llm import get_default_provider
from llm.gemini_provider import GeminiProvider


def test_returns_none_when_gemini_api_key_unset(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert get_default_provider() is None


def test_returns_gemini_provider_when_gemini_api_key_set(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-not-real")
    provider = get_default_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.is_available() is True
