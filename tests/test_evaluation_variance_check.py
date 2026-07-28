"""
Tests for evaluation/variance_check.py: exercises the four scenarios that
matter for the harness -- identical outputs (zero variance), spread
outputs (real variance with correct summary stats), a mid-loop failure
(errors list populated, other samples still counted), and the held-out
path guard. Uses a fake `LLMProvider` subclass modelled on
tests/test_llm_base.py's own `_FakeProvider` sequence-of-responses shape,
so no test ever makes a live LLM call.
"""

import os

import pytest

from evaluation._path_guard import HELD_OUT_ROOT
from evaluation.variance_check import (
    SampleResult,
    VarianceResult,
    score_workflow_variance,
)
from llm.base import LLMProvider, LLMResult, PROMPT_VERSION

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
_TEST_FIXTURE = os.path.join(_FIXTURES_DIR, "rust_ci.yml")


class _FakeVarianceProvider(LLMProvider):
    """Consumes a pre-scripted list of responses, one per beautify() call.
    Each entry is either an LLMResult (success or explicit fallback) or an
    Exception subclass -- if the latter, we build an LLMResult with
    used_fallback=True carrying the exception's string, matching what
    llm/base.py's real beautify() would produce.
    """

    def __init__(self, responses):
        self._responses = list(responses)

    @property
    def provider_name(self):
        return "fake"

    @property
    def model_name(self):
        return "fake-model"

    @property
    def temperature(self):
        return 0.2

    def _call_once(self, structured_text, pipeline):
        raise NotImplementedError("this fake overrides beautify() directly")

    def beautify(self, structured_text, pipeline) -> LLMResult:
        item = self._responses.pop(0)
        common = dict(
            provider_name=self.provider_name,
            model=self.model_name,
            temperature=self.temperature,
            prompt_version=PROMPT_VERSION,
            latency_ms=0.0,
            retry_count=0,
        )
        if isinstance(item, Exception):
            return LLMResult(
                text=structured_text,
                used_fallback=True,
                error=f"{type(item).__name__}: {item}",
                **common,
            )
        return LLMResult(text=item, used_fallback=False, **common)


_PROSE_LOW_FKGL = "The pipeline runs on push. It builds the code. It tests the code."
_PROSE_HIGH_FKGL = (
    "This continuous integration workflow orchestrates comprehensive "
    "multi-platform verification procedures encompassing compilation, "
    "instrumentation, and validation phases across heterogeneous environments."
)


def test_score_workflow_variance_identical_outputs_gives_zero_variance():
    provider = _FakeVarianceProvider([_PROSE_LOW_FKGL] * 5)
    result = score_workflow_variance(_TEST_FIXTURE, repeats=5, provider=provider)

    assert isinstance(result, VarianceResult)
    assert result.fixture == "rust_ci.yml"
    assert len(result.samples) == 5
    assert all(isinstance(s, SampleResult) for s in result.samples)
    assert all(s.text == _PROSE_LOW_FKGL for s in result.samples)
    assert result.errors == []
    assert result.std_dev == 0.0
    assert result.range == 0.0
    assert result.interpretation == "essentially deterministic (range < 1 grade level)"


def test_score_workflow_variance_spread_outputs_produces_real_variance():
    provider = _FakeVarianceProvider([
        _PROSE_LOW_FKGL,
        _PROSE_HIGH_FKGL,
        _PROSE_LOW_FKGL,
        _PROSE_HIGH_FKGL,
    ])
    result = score_workflow_variance(_TEST_FIXTURE, repeats=4, provider=provider)

    assert len(result.samples) == 4
    assert result.errors == []
    assert result.range is not None and result.range > 1.0
    assert result.std_dev is not None and result.std_dev > 0.0
    assert result.min == min(s.fkgl for s in result.samples)
    assert result.max == max(s.fkgl for s in result.samples)
    assert result.min < result.max
    # Interpretation label must reflect the observed range via the fixed rule.
    if result.range < 3.0:
        assert result.interpretation == "moderate drift (range 1-3 grade levels)"
    else:
        assert result.interpretation == "large drift (range >= 3 grade levels)"


def test_score_workflow_variance_records_error_and_keeps_other_samples():
    provider = _FakeVarianceProvider([
        _PROSE_LOW_FKGL,
        RuntimeError("simulated mid-run failure"),
        _PROSE_LOW_FKGL,
    ])
    result = score_workflow_variance(_TEST_FIXTURE, repeats=3, provider=provider)

    assert len(result.samples) == 2  # failed repeat excluded, others kept
    assert len(result.errors) == 1
    assert "RuntimeError: simulated mid-run failure" in result.errors[0]
    # Numeric summaries still computed against the successful repeats:
    assert result.mean is not None
    assert result.range == 0.0  # two identical successful samples


def test_score_workflow_variance_all_failures_returns_empty_samples():
    provider = _FakeVarianceProvider([
        RuntimeError("boom"),
        RuntimeError("boom again"),
    ])
    result = score_workflow_variance(_TEST_FIXTURE, repeats=2, provider=provider)

    assert result.samples == []
    assert len(result.errors) == 2
    assert result.mean is None
    assert result.std_dev is None
    assert result.range is None
    assert result.interpretation == ""


def test_score_workflow_variance_no_provider_labels_missing_key(monkeypatch):
    monkeypatch.setattr("evaluation.variance_check.get_default_provider", lambda: None)
    result = score_workflow_variance(_TEST_FIXTURE, repeats=3)

    assert result.samples == []
    assert result.errors == ["GEMINI_API_KEY not set"]
    # Deterministic FKGL is still populated -- doesn't need the LLM.
    assert isinstance(result.deterministic_fkgl, float)


def test_score_workflow_variance_refuses_held_out_path():
    held_out_file = os.path.join(str(HELD_OUT_ROOT), "requests_lint.yml")
    with pytest.raises(ValueError):
        score_workflow_variance(held_out_file, repeats=1)
