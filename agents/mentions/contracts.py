"""Core protocol contracts for modular Mentions components.

These contracts define the target replaceable module boundaries for the
Mentions runtime. They do not force inheritance, only compatible structure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable, Any


@dataclass(frozen=True)
class MarketQuery:
    text: str
    user_id: str = 'default'
    source: str = 'text'
    session_id: str = ''


@dataclass(frozen=True)
class MarketCandidate:
    ticker: str
    title: str
    score: float
    rationale: str = ''
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedMarket:
    ticker: str
    title: str = ''
    confidence: str = 'low'
    rationale: str = ''
    candidates: tuple[MarketCandidate, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceBundle:
    market: dict = field(default_factory=dict)
    news: list[dict] = field(default_factory=list)
    transcripts: list[dict] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowDecision:
    decision: str
    confidence: str = 'low'
    output_mode: str = 'partial'
    rationale: str = ''
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderedOutput:
    text: str
    format: str = 'telegram-brief'
    meta: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MarketResolver(Protocol):
    def resolve(self, query: MarketQuery) -> ResolvedMarket: ...


@runtime_checkable
class MarketDataProvider(Protocol):
    def fetch_market(self, ticker: str) -> dict: ...
    def fetch_history(self, ticker: str, days: int = 30) -> list[dict]: ...
    def search_markets(self, query: str, limit: int = 5) -> list[dict]: ...


@runtime_checkable
class NewsContextProvider(Protocol):
    def build_context(self, query: str, category: str = 'general',
                      require_live: bool = False) -> dict: ...


@runtime_checkable
class TranscriptRetriever(Protocol):
    def search(self, query: str, limit: int = 5, speaker: str = '') -> list[dict]: ...


@runtime_checkable
class AnalysisEngine(Protocol):
    def analyze(self, query: str, frame: dict, evidence: EvidenceBundle) -> dict: ...


@runtime_checkable
class WorkflowPolicy(Protocol):
    def decide(self, query: str, frame: dict, evidence: EvidenceBundle,
               analysis: dict | None = None) -> WorkflowDecision: ...


@runtime_checkable
class MemoRenderer(Protocol):
    def render(self, analysis: dict, decision: WorkflowDecision,
               target: str = 'telegram-brief') -> RenderedOutput: ...
