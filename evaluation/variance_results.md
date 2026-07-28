# Variance results (Tier 1, Method 4)

This variance check answers the question raised by PR 2's readability results (evaluation/readability_results.md): are the per-fixture FKGL swings between deterministic and LLM-polished text real repeatable effects of each fixture's content, or run-to-run noise on a single call?

Scope: FKGL only (per-metric variance for Reading Ease/Gunning Fog is recoverable after the fact from each row's stored raw prose without spending fresh quota). Pure stochastic variance at the tool's production temperature (0.2) -- not a temperature sweep.

Interpretation rule (fixed, stated explicitly so the label isn't opaque):
  range < 1.0            -> essentially deterministic
  1.0 <= range < 3.0     -> moderate drift
  range >= 3.0           -> large drift

## Summary

| Fixture | Det. FKGL | LLM FKGL mean (N=10) | Std dev | Min | Max | Range | Interpretation | Notes |
|---|---|---|---|---|---|---|---|---|
| pytorch_lint.yml | 17.69 | -- | -- | -- | -- | -- | no samples | GEMINI_API_KEY not set |
| setup_python_test.yml | 11.08 | -- | -- | -- | -- | -- | no samples | GEMINI_API_KEY not set |
| rust_ci.yml | 10.37 | -- | -- | -- | -- | -- | no samples | GEMINI_API_KEY not set |

## Per-fixture raw samples

### pytorch_lint.yml — PR 2 showed a 6.42-grade-level drop under LLM polish

No successful samples (errors: ['GEMINI_API_KEY not set']).

### setup_python_test.yml — PR 2 showed a 4.12-grade-level rise

No successful samples (errors: ['GEMINI_API_KEY not set']).

### rust_ci.yml — PR 2 showed a 0.31, essentially flat, control

No successful samples (errors: ['GEMINI_API_KEY not set']).
