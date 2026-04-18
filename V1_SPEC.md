# V1 Spec

## Goal

V1 is a URL-driven market intelligence app for Kalshi mention markets.

Core promise:
- market URL in
- market/news/speaker-context retrieval
- analytical report out

## Primary user flow

1. User sends a Kalshi market URL.
2. The app resolves the canonical market and gathers relevant context.
3. The app returns an analytical report for that market.

## Input

Required input:
- Kalshi market URL

Example input shape:
- `/markets/{series}/{pretty-slug}/{ticker}`
- `/markets/{series}/{ticker-or-slug}`

## Required pipeline

### 1. Market intake
The system must:
- parse the URL
- recover the canonical ticker
- resolve the market/event identity

### 2. Market context
The system must gather:
- market payload
- event/series context
- market prior
- liquidity / spread / regime / fragility context

### 3. News context
The system must gather:
- fresh news relevant to the event/topic/speaker when available
- event-specific context that may affect the market

### 4. Speaker historical context
The system must gather:
- relevant prior speaker events
- transcript-backed context
- relevant PMT-style historical analogs when available

Rules for valid historical speaker context in V1:
- it must be topic-relevant to the current market
- it must be backed by transcript evidence in the local corpus or manually provided transcripts
- same-speaker match is required
- format similarity is preferred when available

The app must not treat generic speaker history or transcriptless prior events as normal evidence.

### 5. Evidence synthesis
The system must:
- distinguish primary vs secondary evidence
- identify conflicts / missing evidence
- avoid overstating weak evidence
- allow partial / abstain style conclusions when evidence is weak

### 6. Analytical report generation
The system must output a report that includes at least:
- what market this is
- baseline market prior
- what the fresh context says
- what relevant prior speaker/event history says
- main thesis
- fair value / provisional fair value view
- key risk
- invalidation / what changes the view
- action framing:
  - no-trade
  - monitor
  - interesting setup

## Required output quality

V1 output should:
- be analytically useful
- be honest about uncertainty
- avoid fake precision
- avoid pretending weak evidence is strong
- support partial-only outcomes when context is missing

## Non-goals for V1

V1 does NOT need to:
- automatically trade
- be a fully calibrated probabilistic forecasting engine
- include GraphRAG
- include Airflow / MLflow / River
- include full Bayesian model machinery
- support every possible market type
- be production-perfect

## Scope discipline

A feature is V1-priority only if it directly improves:
- URL -> context gathering -> analytical report

If it does not materially improve that path, it is not core V1 work.

## Canonical V1 definition

V1 = market URL in -> market/news/speaker-context retrieval -> analytical report out
