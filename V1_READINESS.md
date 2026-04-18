# V1 Readiness

This file maps the current roadmap and implementation status to `V1_SPEC.md`.

## Canonical V1 target

V1 target:
- market URL in
- market/news/speaker-context retrieval
- analytical report out

## V1-critical blocks

### 1. Input & Market Resolution
Status:
- strong

Current readiness:
- ~80%

Why:
- URL intake exists
- canonical ticker recovery exists
- explicit trailing ticker handling exists
- market context contract has been normalized

Remaining V1 work:
- edge-case URL/query resolution cleanup
- better title normalization for user-facing output

---

### 2. Market Prior
Status:
- strong enough for V1

Current readiness:
- ~75-80%

Why:
- canonical prior extraction hierarchy exists
- thin-market penalties exist
- prior quality classes exist
- diagnostics exist

Remaining V1 work:
- final tuning for degenerate 0/1 books
- maybe clearer distinction between quoted-only and tradeable priors

---

### 3. News / Transcript / Speaker Context Retrieval
Status:
- usable but uneven

Source-stack decision:
- primary news direction: Event Registry
- fallback/bootstrap news source: NewsAPI
- GDELT: paused experimental provider
- social discovery: Grok (Twitter/X-oriented discovery only)

Current readiness:
- ~60-65%

Why:
- retrieval modules exist
- transcript/news bundles exist
- runtime DB fallback exists
- historical PMT support exists

Remaining V1 work:
- improve retrieval usefulness / relevance
- better coverage on real cases
- improve live freshness and transcript matching quality
- add topic-relevant transcript-backed speaker-event retrieval instead of generic speaker history

---

### 4. Historical Intelligence
Status:
- partial

Current readiness:
- ~65-70%

Why:
- PMT legacy KB is wired in
- selector exists
- scoring/rejection logic exists

Remaining V1 work:
- better selector discrimination
- better metadata / topic / format / phase sensitivity
- reduce generic analog noise

---

### 5. Fusion / Decision Logic
Status:
- usable

Current readiness:
- ~70-75%

Why:
- evidence fusion has conflicts / coverage / source quality
- text assessor is less naive
- posterior update abstains appropriately in weak cases

Remaining V1 work:
- stronger arbitration quality
- better uncertainty handling
- better calibrated downstream use of fused evidence

---

### 6. Final Analysis Layer
Status:
- usable

Current readiness:
- ~70-75%

Why:
- analysis_v2 exists
- it uses prior quality / abstain / conflicts / coverage
- it can produce thesis / fair value / risk / invalidation / action

Remaining V1 work:
- tighten market-native phrasing
- improve trade usefulness and punchiness

---

### 7. Presentation Layer
Status:
- close but not done

Current readiness:
- ~75%

Why:
- analysis/presentation split exists
- headers exist
- wording layer exists
- telegram brief / memo / investor note exist

Remaining V1 work:
- adaptive wording module
- less mixed RU/EN phrasing
- final polish for action / risk / invalidation output

---

## Blocks that are strong enough already
- architecture / codebase health
- retrieval layering
- persistence split
- analysis/presentation separation
- top-level contracts

These are no longer the main V1 blockers.

## Main V1 blockers now

The main blockers are no longer architecture.
They are quality blockers in the core URL -> context -> report path:

1. retrieval quality on real markets
2. transcript-backed topic-relevant speaker-event retrieval
3. historical intelligence quality
4. final analysis sharpness
5. presentation polish

## Recommended V1 finishing order

1. News / Transcript / Speaker Context Retrieval
2. Transcript-backed topic-relevant Speaker Event Retrieval
3. Historical Intelligence
4. Final Analysis Layer
5. Presentation Layer

## Practical definition of V1-ready

The app is V1-ready when the following is true:
- a user sends a normal Kalshi market URL
- the app reliably resolves the correct market
- the app gathers enough market/news/speaker context to produce a useful report
- historical speaker context is transcript-backed and topic-relevant rather than generic biography/history noise
- the report is honest, coherent, and readable
- weak evidence leads to partial / abstain style output instead of fake certainty
