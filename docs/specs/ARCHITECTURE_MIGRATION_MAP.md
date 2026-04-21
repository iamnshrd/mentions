# Architecture Migration Map

This document defines the canonical three-layer architecture for the repository.

## Decision

Canonical ownership is now split across three packages:

- `mentions_core/` — runtime shell, CLI, bootstrap, sessions, pack registry
- `mentions_domain/` — canonical shared domain logic
- `agents/mentions/` — Mentions pack adapters, orchestration, capabilities, presentation, storage wiring

## Layer Rules

### `mentions_core/`

Owns:

- CLI entrypoints
- state/session primitives
- generic runtime bootstrap
- observability and generic network helpers
- pack registration and scheduling infrastructure

Must not own:

- Mentions-specific market logic
- speaker/topic resolution logic
- retrieval/ranking heuristics specific to the Mentions domain

### `mentions_domain/`

Owns:

- reusable business-domain contracts
- canonical normalization helpers
- intent classification and shared LLM abstractions
- posterior / probability / time-decay / learning helpers
- reusable retrieval semantics and ranking models
- shared resolution, inference, scoring, and decision logic
- other domain logic that should be reusable by both `agents/mentions` and compatibility layers

Must not own:

- CLI wiring
- filesystem/runtime bootstrapping
- external transport lifecycle code
- pack-specific rendering or storage adapters

### `agents/mentions/`

Owns:

- pack implementation
- capability services and APIs
- orchestration glue
- presentation/rendering
- Mentions-specific DB and storage integrations
- adapters around canonical domain logic

Must not own:

- the canonical source of shared domain rules when those rules are not adapter-specific

## What We Found

The repository had started moving away from an older compatibility tree, but in an inconsistent way:

- the top-level compatibility package declared itself a shim layer
- `mentions_core/` already owned session/bootstrap/runtime shell pieces
- `agents/mentions/` already owned a large amount of active domain and orchestration logic
- the old compatibility tree still contained many real implementations

That created a split-brain architecture:

- some modules were duplicated
- some were shimmed
- some still treated the old compatibility tree as canonical

That historical state has now been resolved: the old compatibility tree has been
removed, and the canonical owners below reflect the live tree.

## Current Migration Status

### Completed

The repository no longer contains the old compatibility tree.

Canonical ownership is now established for the major migration blocks:

- `mentions_core/base/session/*`
- `mentions_core/base/obs/*`
- `mentions_core/base/net/*`
- `mentions_core/base/scheduler/*`
- `agents/mentions/workflows/*`
- `agents/mentions/interfaces/capabilities/*`
- `agents/mentions/services/*`
- `agents/mentions/storage/*`
- `agents/mentions/eval/*`
- `agents/mentions/ingest/*`

The former top-level compatibility package has now been fully removed from the live tree.

### Still Transitional

These areas may still deserve future promotion into `mentions_domain/`
where reuse justifies it:

- reusable evaluation/backtesting primitives
- reusable transcript-processing heuristics
- any pack-specific analysis helpers that prove reusable outside Mentions

## Ownership Map

### Canonical in `mentions_core/`

- [mentions_core/cli.py](/Users/nshrd/Documents/Mentions/mentions/mentions_core/cli.py:1)
- [mentions_core/base/config.py](/Users/nshrd/Documents/Mentions/mentions/mentions_core/base/config.py:1)
- [mentions_core/base/registry.py](/Users/nshrd/Documents/Mentions/mentions/mentions_core/base/registry.py:1)
- [mentions_core/base/net](/Users/nshrd/Documents/Mentions/mentions/mentions_core/base/net)
- [mentions_core/base/obs](/Users/nshrd/Documents/Mentions/mentions/mentions_core/base/obs)
- [mentions_core/base/scheduler](/Users/nshrd/Documents/Mentions/mentions/mentions_core/base/scheduler)
- [mentions_core/base/session](/Users/nshrd/Documents/Mentions/mentions/mentions_core/base/session)

### Canonical in `mentions_domain/`

- domain contracts
- normalization and bundle-shape helpers
- shared analysis helpers such as regime and hedge classification
- intent classification
- shared LLM client/pricing/retry logic
- posterior / probability / time-decay / learning logic
- retrieval models, embedding helpers, recency and reliability semantics
- market candidate scoring and resolution

### Canonical in `agents/mentions/`

- pack/capability APIs
- orchestration/runtime composition
- ingestion and evaluation flows
- presentation and response rendering
- Mentions-specific storage queries
- Mentions-specific fetch/provider integrations
- pack-specific modules still tightly coupled to current runtime wiring

## Migration Rule Of Thumb

When touching a module, classify it first:

1. If it is generic runtime/bootstrap infrastructure, move it to `mentions_core/`.
2. If it is reusable Mentions domain logic, move it to `mentions_domain/`.
3. If it is pack orchestration, rendering, capability wiring, or adapter code, keep it in `agents/mentions/`.
4. If it only exists for backwards compatibility, remove it unless there is an explicit external contract that still requires it.

## Next Recommended Moves

### 1. Continue Extracting Shared Domain Logic Into `mentions_domain/`

Good candidates:

- any remaining reusable posterior/time-decay/learning helpers that still
  live under `agents/mentions/services/*`

These are domain rules, not runtime infrastructure.

### 2. Continue Extracting Shared Retrieval Semantics

Good candidates:

- reusable retrieval/ranking semantics now living under
  `agents/mentions/services/retrieval/*`
- the reusable parts of transcript retrieval heuristics now living under
  `agents/mentions/services/transcripts/*`

The DB-backed query adapters should remain in `agents/mentions/storage/*`.

### 3. Revisit Eval Ownership

Good candidates:

- reusable parts of `agents/mentions/eval/*` if they become domain-level
  rather than pack-level evaluation code

### 4. Keep Public Entry Points Minimal

Eventually:

- prefer `mentionsctl` and `python -m mentions_core ...` as the only supported local CLI surfaces

## Success Criteria

The migration is succeeding when:

- `mentions_domain/` keeps growing as the canonical home of shared domain logic
- `agents/mentions/` becomes more obviously adapter/orchestration-oriented
- `mentions_core/` stays generic and does not absorb domain logic

## Non-goals

- no giant rewrite in one PR
- no moving pack/orchestration glue into `mentions_domain/`
