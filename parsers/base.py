"""
parsers/base.py — abstract interface every platform-specific parser must implement.

Layer 1 of the architecture (see PROJECT_PLAN.md). Each CI platform (GitHub
Actions, and later GitLab CI / CircleCI / Jenkins) gets its own parser class
implementing `BaseParser.parse`. Nothing downstream of this boundary — no
generator, no LLM prompt — is allowed to see raw platform-specific YAML;
everything past this point works only with `ir.schema.Pipeline`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ir.schema import Pipeline


class BaseParser(ABC):
    """
    Contract for a Layer 1 parser.

    `parse` must guarantee:
    - It returns an `ir.schema.Pipeline` instance — never a bare dict or
      platform-specific structure.
    - The returned `Pipeline` must pass `ir.validate.is_valid()`, or the
      method must raise rather than return a structurally broken IR.
    - No information from the source file may be silently dropped. Anything
      the schema doesn't have a structured field for yet must be preserved
      in the relevant `raw_extras` dict (on `Pipeline`, `Job`, or `Step`)
      instead of being discarded.
    - Fields whose original syntax can't be reliably parsed into a
      structured form (e.g. a `Condition`) must still populate the raw
      `expression`/`raw` string — never leave both the structured and raw
      forms empty when the source data existed.
    """

    @abstractmethod
    def parse(self, file_path: str) -> Pipeline:
        """Parse a pipeline definition file at `file_path` into a `Pipeline`."""
        raise NotImplementedError
