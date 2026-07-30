"""
Tests for evaluation/naive_baseline.py — Tier 4's condition 3.

Unit tests inject a fake `client` into `GeminiProvider` (same pattern as
tests/test_gemini_provider.py) so no real network call, real SDK client,
or API key is ever needed. Tested only against tests/fixtures/, per this
project's held-out boundary — evaluation/held_out_workflows/ is never
touched here.
"""

import ast
import json
import os

import pytest

import tool1.single_pipeline as single_pipeline_module
from evaluation.naive_baseline import NAIVE_PROMPT_VERSION, generate_naive_baseline
from llm.gemini_provider import DEFAULT_MODEL, DEFAULT_TEMPERATURE, GeminiProvider

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fixture_path(filename):
    return os.path.join(FIXTURES_DIR, filename)


# ---------------------------------------------------------------------------
# Fake Gemini client (same shape as tests/test_gemini_provider.py's, kept
# local to this file rather than shared, matching this project's existing
# per-test-file fake convention).
# ---------------------------------------------------------------------------

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
# 1. End-to-end success, across a couple of real fixtures.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", ["checkout_check_dist.yml", "pytorch_lint.yml"])
def test_generate_naive_baseline_success_across_complexity_range(tmp_path, monkeypatch, filename):
    monkeypatch.setattr(single_pipeline_module, "DEFAULT_LLM_LOG_PATH", str(tmp_path / "log.jsonl"))
    provider, client = _provider_with(_FakeResponse("This pipeline does some CI things."))
    source = _fixture_path(filename)

    result = generate_naive_baseline(source, provider=provider)

    assert result.used_fallback is False
    assert result.text == "This pipeline does some CI things."
    assert result.provider_name == "gemini"
    assert result.prompt_version == NAIVE_PROMPT_VERSION
    assert result.error is None

    # The raw YAML text, not a parsed/structured summary, reached the prompt.
    with open(source, encoding="utf-8") as f:
        raw_yaml = f.read()
    sent_contents = client.models.last_call_kwargs["contents"]
    assert raw_yaml in sent_contents
    assert "Explain what this CI/CD pipeline does" in sent_contents

    # No system_instruction at all -- genuinely naive, not quietly guarded.
    sent_config = client.models.last_call_kwargs["config"]
    assert sent_config.system_instruction is None


def test_generate_naive_baseline_never_touches_ir_or_generators(monkeypatch, tmp_path):
    # Sanity check on the module's own claim: no parsers/ir/generators
    # import anywhere in its source.
    naive_baseline_path = os.path.join(REPO_ROOT, "evaluation", "naive_baseline.py")
    with open(naive_baseline_path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=naive_baseline_path)

    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    assert "parsers" not in imported_roots
    assert "ir" not in imported_roots
    assert "generators" not in imported_roots


# ---------------------------------------------------------------------------
# 2. Failure path -- never a silent empty string.
# ---------------------------------------------------------------------------

def test_generate_naive_baseline_falls_back_on_sdk_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(single_pipeline_module, "DEFAULT_LLM_LOG_PATH", str(tmp_path / "log.jsonl"))
    provider, client = _provider_with(RuntimeError("network exploded"))
    source = _fixture_path("checkout_check_dist.yml")

    result = generate_naive_baseline(source, provider=provider)

    assert result.used_fallback is True
    assert result.error is not None
    assert "network exploded" in result.error
    assert result.text != ""
    # Fallback text is the raw YAML unchanged (never an empty string that
    # could be mistaken for "zero hallucinations" during scoring).
    with open(source, encoding="utf-8") as f:
        raw_yaml = f.read()
    assert result.text == raw_yaml
    assert result.retry_count == provider.max_retries


def test_generate_naive_baseline_falls_back_on_empty_response(tmp_path, monkeypatch):
    monkeypatch.setattr(single_pipeline_module, "DEFAULT_LLM_LOG_PATH", str(tmp_path / "log.jsonl"))
    provider, client = _provider_with(_FakeResponse(""))
    source = _fixture_path("checkout_check_dist.yml")

    result = generate_naive_baseline(source, provider=provider)

    assert result.used_fallback is True
    assert result.error == "empty response"
    with open(source, encoding="utf-8") as f:
        raw_yaml = f.read()
    assert result.text == raw_yaml


def test_generate_naive_baseline_not_configured_skips_retry_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(single_pipeline_module, "DEFAULT_LLM_LOG_PATH", str(tmp_path / "log.jsonl"))
    provider = GeminiProvider(api_key=None, client=None)  # is_available() -> False
    source = _fixture_path("checkout_check_dist.yml")

    result = generate_naive_baseline(source, provider=provider)

    assert result.used_fallback is True
    assert result.retry_count == 0
    assert "not configured" in result.error


# ---------------------------------------------------------------------------
# 3. Fairness: model/temperature match condition 2's constants, by
# construction (same provider defaults), not by a separately-maintained
# assumption.
# ---------------------------------------------------------------------------

def test_generate_naive_baseline_uses_same_model_and_temperature_as_condition_2(tmp_path, monkeypatch):
    monkeypatch.setattr(single_pipeline_module, "DEFAULT_LLM_LOG_PATH", str(tmp_path / "log.jsonl"))
    provider, client = _provider_with(_FakeResponse("explanation"))
    source = _fixture_path("checkout_check_dist.yml")

    result = generate_naive_baseline(source, provider=provider)

    assert result.model == DEFAULT_MODEL
    assert result.temperature == DEFAULT_TEMPERATURE
    assert client.models.last_call_kwargs["model"] == DEFAULT_MODEL
    assert client.models.last_call_kwargs["config"].temperature == DEFAULT_TEMPERATURE


def test_generate_naive_baseline_default_provider_is_a_real_gemini_provider(tmp_path, monkeypatch):
    # No provider passed -> GeminiProvider() constructed directly, same
    # construction llm.get_default_provider() uses internally. Without a
    # real/fake API key this has no client, so it takes the
    # not-configured fallback path rather than crashing.
    monkeypatch.setattr(single_pipeline_module, "DEFAULT_LLM_LOG_PATH", str(tmp_path / "log.jsonl"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    source = _fixture_path("checkout_check_dist.yml")

    result = generate_naive_baseline(source)

    assert result.provider_name == "gemini"
    assert result.model == DEFAULT_MODEL
    assert result.used_fallback is True


# ---------------------------------------------------------------------------
# 4. Logging: same evaluation/llm_call_log.jsonl structure as condition 2,
# distinguishable via prompt_version.
# ---------------------------------------------------------------------------

def test_generate_naive_baseline_logs_to_same_log_structure(tmp_path, monkeypatch):
    log_path = tmp_path / "llm_call_log.jsonl"
    monkeypatch.setattr(single_pipeline_module, "DEFAULT_LLM_LOG_PATH", str(log_path))
    provider, client = _provider_with(_FakeResponse("explanation"))
    source = _fixture_path("checkout_check_dist.yml")

    generate_naive_baseline(source, provider=provider)

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["provider"] == "gemini"
    assert record["model"] == DEFAULT_MODEL
    assert record["prompt_version"] == "naive-v1"
    assert record["prompt_version"] != "v1"  # condition 2's prompt_version -- must stay distinguishable
    assert record["used_fallback"] is False
    assert record["source_file"] == source
    assert record["pipeline_name"] == "checkout_check_dist"


# ---------------------------------------------------------------------------
# 5. Isolation: neither tool1/single_pipeline.py nor tool2/multi_pipeline.py
# may ever import from evaluation.naive_baseline. Static, ast-based --
# not just a documentation promise.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "module_path",
    [
        os.path.join(REPO_ROOT, "tool1", "single_pipeline.py"),
        os.path.join(REPO_ROOT, "tool2", "multi_pipeline.py"),
    ],
)
def test_tool1_and_tool2_never_import_naive_baseline(module_path):
    with open(module_path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=module_path)

    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)
            for alias in node.names:
                imported_names.add(f"{node.module}.{alias.name}")

    for name in imported_names:
        assert "naive_baseline" not in name, (
            f"{module_path} must never import from evaluation.naive_baseline "
            f"(found: {name}) -- that module must not be reachable from "
            f"Tool 1's or Tool 2's real document-generation path."
        )
