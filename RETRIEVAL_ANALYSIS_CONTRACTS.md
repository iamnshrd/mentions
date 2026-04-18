# Retrieval + Analysis Contracts

This file is the explicit contract map for the current `mentions` runtime after the retrieval/analysis refactor.

## Top-level retrieval result
Produced by:
- `agents/mentions/runtime/retrieve.py`
- shaped through `agents/mentions/runtime/bundle_contracts.py::build_retrieval_result(...)`

Canonical top-level blocks:
- `market` — normalized market retrieval payload
- `market_prior` — prior extracted from live market state
- `transcripts` — raw transcript chunk list
- `transcript_intelligence` — transcript bundle / summary / risks / knowledge bundle
- `news` — raw news items
- `news_status` — coarse status for news path
- `news_context` — structured news bundle
- `workflow_policy` — release/output gate
- `pmt_knowledge` — raw PMT historical KB bundle
- `selected_pmt_evidence` — compact PMT evidence block
- `text_evidence_assessment` — text/update-pressure block
- `posterior_update` — bounded prior-to-posterior proposal
- `challenge_block` — governance / auditability layer
- `fused_evidence` — fused evidence summary layer
- `has_data` — coarse availability boolean
- `sources_used` — source labels for diagnostics

## Producer ownership

### Context retrieval
- `runtime/context_retrieval.py`
  - `retrieve_market_context(...)`
  - `retrieve_transcript_context(...)`
  - `retrieve_news_context(...)`

### Ticker-specific context retrieval
- `runtime/ticker_retrieval.py`
  - `retrieve_market_context_by_ticker(...)`
  - `retrieve_transcript_context_by_ticker(...)`
  - `retrieve_news_context_by_ticker(...)`

### Decision-support blocks
- `runtime/retrieve_helpers.py`
  - `build_market_prior_block(...)`
  - `build_pmt_knowledge_block(...)`
  - `build_selected_pmt_block(...)`
  - `build_text_evidence_block(...)`
  - `build_posterior_block(...)`
  - `build_challenge_block_helper(...)`
  - `build_fused_evidence_block(...)`

### Persistence side effects
- `runtime/persistence_helpers.py`
  - `persist_market_runtime_state(...)`
  - `persist_source_knowledge(...)`
  - `persist_ticker_news(...)`
  - `persist_analysis_stub(...)`

### Analysis synthesis
- `modules/analysis_engine/engine.py`
  - legacy analysis payload
  - `analysis_v2`
- `modules/analysis_engine/v2.py`
  - `thesis`
  - `fair_value_view`
  - `why_now`
  - `key_risk`
  - `invalidation`
  - `recommended_action_v2`

### Presentation
- `modules/output_profiles/profiles.py`
  - `telegram_brief`
  - `trade_memo`
  - `investor_note`

## Consumer expectations

### `analysis_engine`
Consumes:
- `market_prior`
- `workflow_policy`
- `pmt_knowledge`
- `fused_evidence`
- plus legacy `market/news/transcripts`

### `analysis_v2`
Consumes:
- `market_prior`
- `posterior_update`
- `selected_pmt_evidence`
- `challenge_block`
- `workflow_policy`
- `text_evidence_assessment`

### `output_profiles`
Consumes:
- `analysis_v2`
- especially:
  - `thesis`
  - `fair_value_view`
  - `why_now`
  - `key_risk`
  - `invalidation`
  - `recommended_action_v2`
  - `supporting_blocks.market_prior.title`

## Naming discipline
- `*_context` = retrieval-stage contextual bundle
- `*_knowledge` = raw historical/derived knowledge
- `*_evidence` = selected or fused decision-use evidence
- `*_assessment` = scored interpretation layer
- `*_update` = prior/posterior transition layer
- `*_block` = stable normalized decision-support object

## Current known cleanup hotspots
1. `market_prior` semantics still need continued tuning for thin markets.
2. `analysis_engine` still carries legacy + v2 payloads in one object.
3. `output_profiles` still contains wording cleanup + header rendering + profile rendering in one file.
4. `fused_evidence` is still more of an organizing contract than a mature arbitration engine.
5. `pmt_selector` remains top-1 category selection, not a true scored selector yet.
