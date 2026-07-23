"""
tests/conftest.py — shared pytest fixtures.

Autouse: strips GEMINI_API_KEY/GEMINI_MODEL from the environment for every
test by default. Phase 5's document_pipeline()/_build_documentation()
default to use_llm=True, resolving a provider via llm.get_default_provider()
whenever the caller doesn't pass one explicitly — this fixture guarantees
that default path stays a deterministic no-op (no live network call) in
the test suite regardless of what happens to be set in the environment the
suite is run from. Tests that specifically want to exercise a configured
provider set the key explicitly via monkeypatch, or (for the one live
Gemini smoke test in tests/test_gemini_provider.py) read the real
pre-test value captured at module import time, before this fixture runs.
"""

import pytest


@pytest.fixture(autouse=True)
def _clear_gemini_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
