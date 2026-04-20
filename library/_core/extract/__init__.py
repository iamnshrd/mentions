"""LLM-driven extraction pipeline.

Enriches the structured KB (``heuristics``, ``decision_cases``,
``pricing_signals`` + ``heuristic_evidence``) from transcript chunks.

Design:
* LLM-driven only — when no :class:`~library._core.llm.LLMClient` is
  available (i.e. :class:`~library._core.llm.NullClient`), extraction
  is a no-op. The structured KB is already populated from the PMT
  dump; the pipeline only *adds* new evidence when the LLM is present.
* Idempotent upserts — re-running over the same document does not
  duplicate rows. Heuristics dedupe by normalized text; signals by
  ``signal_name``; decision cases by ``(document_id, chunk_id, setup)``.
* Every extracted heuristic gets a ``heuristic_evidence`` row linking
  it to its source chunk + quote for later provenance.
"""
from __future__ import annotations

from library._core.extract.pipeline import (
    extract_from_chunk,
    run_extraction,
)

__all__ = ['extract_from_chunk', 'run_extraction']
