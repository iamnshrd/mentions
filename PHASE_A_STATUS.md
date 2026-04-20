# Mentions Phase A Status

## Goal
Create the minimum architectural scaffolding needed for a modular refactor without doing a giant rewrite.

## Completed in this pass

### 1. Added explicit contracts
File:
- `agents/mentions/contracts.py`

Introduced protocol/data-object scaffolding for future swappable modules:
- `MarketResolver`
- `MarketDataProvider`
- `NewsContextProvider`
- `TranscriptRetriever`
- `AnalysisEngine`
- `WorkflowPolicy`
- `MemoRenderer`

Data objects added:
- `MarketQuery`
- `MarketCandidate`
- `ResolvedMarket`
- `EvidenceBundle`
- `WorkflowDecision`
- `RenderedOutput`

### 2. Added lightweight module registry
File:
- `agents/mentions/module_registry.py`

This creates a canonical wiring layer for:
- frame selection
- retrieval bundle building
- ticker retrieval
- analysis engine
- response rendering

### 3. Thinned the orchestrator slightly
File:
- `agents/mentions/runtime/orchestrator.py`

The orchestrator now resolves major runtime pieces through the module registry instead of hard-importing all of them directly.
This is intentionally a small Phase A move, not a deep rewrite.

## Not completed yet

### Still transitional
- `library/` still exists as compatibility layer and has not been frozen/documented in code yet
- module registry still points to existing runtime modules rather than extracted modular implementations
- `market_resolution` is not extracted yet
- `workflow_policy` and `memo_renderer` are not extracted yet

## Immediate next step
Phase B:
- extract `market_resolution` as a first-class module
- move query/url candidate selection logic there
- add real-case resolution regression coverage
