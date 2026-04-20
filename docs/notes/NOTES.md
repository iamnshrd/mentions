# NOTES.md — Mentions Retrospective

This file keeps only high-level project history that is still useful after the architecture cleanup.

## Current state

- canonical runtime shell lives in `mentions_core/`
- shared domain logic lives in `mentions_domain/`
- pack implementation lives in `agents/mentions/`
- old compatibility layers and migration shells have been removed from the live tree

## Milestones kept for context

### Retrieval quality
- recency-aware retrieval was added
- transcript search evolved into a hybrid flow with semantic and lexical signals
- reliability and evidence-fusion layers were split into explicit services

### Ingest and knowledge
- transcript ingest gained structure-aware chunking and section tagging
- KB/FTS sync and PMT knowledge import moved into explicit storage and knowledge owners
- transcript intelligence and extraction were separated from orchestration

### Evaluation and observability
- evaluation harness, audit flows, and counterfactual analysis became first-class modules
- metrics and trace logging moved into the base layer
- cost and latency instrumentation were added to make runtime behaviour inspectable

### Architecture
- runtime, service, provider, storage, and presentation layers were separated
- historical compatibility shells were removed after the migration completed
- local CLI and runtime paths were consolidated around `mentionsctl` and `python -m mentions_core ...`

## What to use now

- local CLI: `mentionsctl ...`
- canonical module ownership: `docs/specs/ARCHITECTURE_MIGRATION_MAP.md`
- path migration reference: `docs/specs/MIGRATION.md`

Older, file-by-file migration notes were intentionally removed to keep the repository focused on the current architecture.
