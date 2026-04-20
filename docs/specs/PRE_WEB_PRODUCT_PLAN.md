# Pre-Web Product Plan

This document freezes the product work order before a dedicated web UI.

## Priority Order

1. `transcripts + DB`
2. `news`
3. `analytics`
4. `web UI`

The web surface should come only after the underlying product blocks expose
stable contracts, predictable behavior, and reproducible debugging paths.

## Good State Criteria

### Transcripts + DB

- ingest is idempotent and reacts correctly to source-file changes
- transcript schema is verified before write-heavy paths run
- every ingest result carries enough trace metadata to debug later retrieval
- chunking / tagging / FTS sync remain deterministic across rechunk runs
- document -> chunks -> evidence trace is easy to follow

### News

- sources are normalized and deduplicated
- ranking separates direct-event news from ambient macro context
- freshness rules are explicit
- source metadata is preserved for rendering and debugging

### Analytics

- final output has a stable shape
- abstain / uncertainty behavior is explicit
- conflict / warning / posterior effects are inspectable
- the system does not hide weak retrieval behind confident prose

## Backlog

### Transcripts + DB

`P0`

- strengthen transcript ingest contract in [`agents/mentions/ingest/transcript.py`](/Users/nshrd/Documents/Mentions/mentions/agents/mentions/ingest/transcript.py:1)
- add schema guards for transcript tables/columns in [`agents/mentions/db.py`](/Users/nshrd/Documents/Mentions/mentions/agents/mentions/db.py:1)
- make ingest results traceable enough for later API / UI use

`P1`

- evaluate chunking and tagging quality on real transcript samples
- improve transcript retrieval precision for event-relevant chunks

`P2`

- operator tooling for bad documents / partial failures
- transcript retrieval regression pack

### News

`P0`

- dedup + source normalization
- direct-event ranking over ambient context

`P1`

- freshness policy
- explicit `direct/context/background` output layers

`P2`

- source-quality heuristics
- small gold eval set

### Analytics

`P0`

- stable response shape
- abstain mode
- inspectable warning / posterior effects

`P1`

- trade-memo consistency
- strong / weak / abstain eval scenarios

`P2`

- calibration review
- transcript/news/conclusion consistency review

## Current Execution Focus

The active implementation focus is the first `P0` block under
`transcripts + DB`.
