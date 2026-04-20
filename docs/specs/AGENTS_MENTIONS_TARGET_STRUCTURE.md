# Agents Mentions Target Structure

This document defines the target internal structure for [`agents/mentions/`](/Users/nshrd/Documents/Mentions/mentions/agents/mentions).

It is intentionally narrower than [ARCHITECTURE_MIGRATION_MAP.md](/Users/nshrd/Documents/Mentions/mentions/docs/specs/ARCHITECTURE_MIGRATION_MAP.md:1): that document defines repository-wide ownership across `mentions_core/`, `mentions_domain/`, and `agents/mentions/`; this document defines how `agents/mentions/` itself should be organized.

## Goal

Turn `agents/mentions/` into a clearer application-layer package with explicit boundaries:

- `interfaces/` for external entrypoints
- `workflows/` for orchestration and use-case composition
- `services/` for Mentions-specific business logic
- `providers/` for external integrations
- `storage/` for persistence
- `presentation/` for output shaping
- `assets/` for static data/config
- `skills/` for prompt assets
- `eval/` for evaluation and review tooling

## Why This Exists

`agents/mentions/` already has strong separation from `mentions_core/` and `mentions_domain/`, but its internal layout is still partially historical. Right now it mixes:

- capability adapters
- orchestration code
- domain-ish modules
- provider/fetch integrations
- storage helpers
- rendering
- review/eval utilities
- prompt assets

That makes the package harder to scan, and it obscures which files own business logic versus transport glue.

## Target Tree

```text
agents/mentions/
  interfaces/
    capabilities/
  workflows/
  services/
  providers/
  storage/
  presentation/
  assets/
  skills/
  eval/
```

## Layer Rules

### `interfaces/`

Owns:

- capability APIs
- action argument parsing
- thin adapters from external calls into workflows/services

Must not own:

- heavy business logic
- persistence details
- provider-specific fetch logic

### `workflows/`

Owns:

- orchestration
- route selection
- retrieval/synthesis flow composition
- end-to-end use-case coordination
- workflow-specific policies and fallbacks

Must not own:

- low-level provider implementations
- long-lived storage primitives
- reusable core business rules that can live in `services/`

### `services/`

Owns:

- Mentions-specific business logic
- analysis logic
- market and transcript services
- knowledge-building/query logic
- wording/policy logic tied to the Mentions pack

Must not own:

- transport adapters
- low-level DB bootstrapping
- raw external API clients

### `providers/`

Owns:

- News, RSS, Kalshi, and other external integrations
- fetch clients
- provider-specific normalization close to the external API boundary

Must not own:

- end-to-end workflows
- presentation logic

### `storage/`

Owns:

- DB access
- schema and migrations
- runtime persistence helpers
- cache/index/repository implementations

Must not own:

- business-level analysis decisions
- provider/network code

### `presentation/`

Owns:

- renderers
- report sections
- output profiles
- user-facing shaping/formatting

Must not own:

- provider calls
- DB writes
- workflow routing

### `assets/`

Owns:

- JSON manifests
- static thresholds
- source profile data
- wording DB files

### `skills/`

Owns:

- prompt assets
- skill documentation and references

It should remain separate from runtime code.

### `eval/`

Owns:

- audit helpers
- review flows
- evaluation-only tooling
- experiments that should not sit on the production path

## Current State

The following existing top-level areas should converge toward the target layout:

- `capabilities/` -> `interfaces/capabilities/`
- `runtime/` -> `workflows/`
- `analysis/` + much of `modules/` -> `services/`
- `fetch/` + `providers/rss_provider.py` -> `providers/`
- `db.py` + `storage/` + storage-related parts of `kb/` and `runtime/` -> `storage/`
- `presentation/` remains `presentation/`
- `review/` trends toward `eval/`

## Mapping Guide

This section records the intended destination for current paths. It is a planning map, not a requirement to move everything at once.

### Interfaces

- `agents/mentions/capabilities/*` -> `agents/mentions/interfaces/capabilities/*`

### Workflows

- `agents/mentions/runtime/orchestrator.py` -> `agents/mentions/workflows/orchestrator.py`
- `agents/mentions/runtime/retrieve.py` -> `agents/mentions/workflows/retrieve.py`
- `agents/mentions/runtime/synthesize.py` -> `agents/mentions/workflows/synthesize.py`
- `agents/mentions/runtime/synthesize_speaker.py` -> `agents/mentions/workflows/speaker_synthesis.py`
- `agents/mentions/runtime/respond.py` -> `agents/mentions/workflows/respond.py`
- `agents/mentions/runtime/routes.py` -> `agents/mentions/workflows/routes.py`
- `agents/mentions/runtime/frame.py` -> `agents/mentions/workflows/frame_selection.py`
- `agents/mentions/runtime/context_retrieval.py` -> `agents/mentions/workflows/context_retrieval.py`
- `agents/mentions/runtime/retrieval_defaults.py` -> `agents/mentions/workflows/retrieval_defaults.py`
- `agents/mentions/runtime/retrieval_fallbacks.py` -> `agents/mentions/workflows/retrieval_fallbacks.py`
- `agents/mentions/modules/workflow_policy/policy.py` -> `agents/mentions/workflows/policy.py`
- `agents/mentions/ingest/auto.py` -> `agents/mentions/workflows/auto_ingest.py`
- `agents/mentions/ingest/transcript.py` -> `agents/mentions/workflows/transcript_ingest.py`
- `agents/mentions/ingest/manual_transcript.py` -> `agents/mentions/workflows/manual_transcript_ingest.py`
- `agents/mentions/scheduler/runner.py` -> `agents/mentions/workflows/scheduling/runner.py`

### Services

- `agents/mentions/analysis/*` -> `agents/mentions/services/analysis/*`
- `agents/mentions/modules/analysis_engine/*` -> `agents/mentions/services/analysis/*`
- `agents/mentions/modules/challenge_layer/*` -> `agents/mentions/services/analysis/*`
- `agents/mentions/modules/evidence_fusion/*` -> `agents/mentions/services/analysis/*`
- `agents/mentions/modules/text_evidence_assessor/*` -> `agents/mentions/services/analysis/*`
- `agents/mentions/modules/news_context/*` -> `agents/mentions/services/news/*`
- `agents/mentions/modules/news_relevance/*` -> `agents/mentions/services/news/*`
- `agents/mentions/modules/market_data/*` -> `agents/mentions/services/markets/*`
- `agents/mentions/modules/market_prior/*` -> `agents/mentions/services/markets/*`
- `agents/mentions/modules/market_resolution/*` -> `agents/mentions/services/markets/resolution/*`
- `agents/mentions/modules/posterior_update/*` -> `agents/mentions/services/markets/*`
- `agents/mentions/modules/pmt_selector/*` -> `agents/mentions/services/markets/*`
- `agents/mentions/analysis/trade_params.py` -> `agents/mentions/services/markets/trade_params.py`
- `agents/mentions/modules/transcript_intelligence/*` -> `agents/mentions/services/transcripts/*`
- `agents/mentions/modules/transcript_tagging/*` -> `agents/mentions/services/transcripts/*`
- `agents/mentions/modules/speaker_event_retrieval/*` -> `agents/mentions/services/speakers/*`
- `agents/mentions/analysis/speaker.py` -> `agents/mentions/services/speakers/speaker_analysis.py`
- `agents/mentions/analysis/speaker_extract.py` -> `agents/mentions/services/speakers/extract.py`
- `agents/mentions/modules/transcript_knowledge_extraction/*` -> `agents/mentions/services/knowledge/*`
- `agents/mentions/kb/build.py` -> `agents/mentions/services/knowledge/build.py`
- `agents/mentions/kb/query.py` -> `agents/mentions/services/knowledge/query.py`
- `agents/mentions/modules/url_intake/*` -> `agents/mentions/services/intake/*`
- `agents/mentions/wording/enforcer.py` -> `agents/mentions/services/wording/enforcer.py`
- `agents/mentions/modules/pmt_legacy_kb/*` -> `agents/mentions/services/knowledge/*`

### Providers

- low-level Kalshi transport lives in `agents/mentions/providers/kalshi/client.py`
- Kalshi bundle/wrapper logic lives in `agents/mentions/providers/kalshi/`
- news providers live in `agents/mentions/providers/news/`
- RSS provider code lives in `agents/mentions/providers/rss/`
- multi-provider fetch orchestration lives in `agents/mentions/workflows/fetch_auto.py`
- Kalshi URL intake parsing lives in `agents/mentions/services/intake/url_parser.py`

### Storage

- `agents/mentions/db.py` -> `agents/mentions/storage/db.py`
- `agents/mentions/storage/runtime_db.py` -> `agents/mentions/storage/runtime/db.py`
- `agents/mentions/storage/runtime_query.py` -> `agents/mentions/storage/runtime/query.py`
- `agents/mentions/storage/schema.py` stays in `agents/mentions/storage/schema.py`
- `agents/mentions/runtime/persistence_helpers.py` -> `agents/mentions/storage/persistence_helpers.py`
- `agents/mentions/kb/migrate.py` -> `agents/mentions/storage/knowledge/migrate.py`

### Presentation

- `agents/mentions/presentation/*` stays in `agents/mentions/presentation/*`
- `agents/mentions/modules/memo_renderer/*` -> `agents/mentions/presentation/*`
- `agents/mentions/modules/output_profiles/*` -> `agents/mentions/presentation/*`
- `agents/mentions/runtime/speaker_report.py` -> `agents/mentions/presentation/speaker_report.py`

### Eval / Experiments

- `agents/mentions/review/transcript_tag_review.py` -> `agents/mentions/eval/transcript_tag_review.py`
- experimental-heavy parts of `agents/mentions/modules/transcript_semantic_retrieval/*` should move to `agents/mentions/eval/` or a dedicated `experiments/` subtree instead of staying on the production service path

## Transition Strategy

This refactor should be incremental.

Preferred sequence:

1. Add the target folders and a short architecture note.
2. Move `capabilities/` into `interfaces/` with re-export shims.
3. Create `workflows/` and move orchestration files there with re-export shims from `runtime/`.
4. Consolidate `fetch/` and `providers/`.
5. Move service logic out of `analysis/`, `modules/`, and selected `runtime/` files.
6. Consolidate storage ownership.
7. Rewrite internal imports to new paths.
8. Remove transitional shims only after tests are green.

## Compatibility Rule

During migration:

- keep old import paths working with temporary re-export wrappers
- do not mix large path renames with deep logic changes in the same PR
- move one ownership boundary at a time

## Non-goals

- no giant one-shot rewrite
- no immediate deletion of every legacy path inside `agents/mentions/`
- no movement of Mentions-specific application logic into `mentions_core/`
- no movement of pack-specific rendering/orchestration into `mentions_domain/`
