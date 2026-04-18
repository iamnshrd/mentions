# News + Social Source Stack

## Decision

For `mentions` V1:
- primary news direction: `Event Registry`
- fallback / bootstrap news source: `NewsAPI`
- `GDELT` stays paused as an experimental provider
- social discovery layer: `Grok`
- do not treat social discovery as equivalent to confirmed news

## Why

### Event Registry
Recommended as the primary news/event intake direction because it is better aligned with:
- politics
- geopolitics
- event-driven markets
- topic/event clustering
- broader event-aware retrieval than a generic news API

It is not sufficient by itself.
It must sit under a relevance/ranking layer.

### GDELT
Keep connected only as a paused experimental provider for now.
It may still become useful later for broader event discovery, but it is not the current primary path.

### NewsAPI
Keep as:
- bootstrap source
- backup path
- quick fallback when GDELT is unavailable or not yet wired for a case

It is useful for speed, but should not be the final strategic dependency for `mentions`.

### Grok
Use only as:
- social discovery
- X/Twitter-oriented signal scouting
- candidate post/account/theme discovery

Do not treat Grok as a canonical source of truth.
Do not collapse Grok output into confirmed news.

## Required architecture split

### 1. `news_provider`
Purpose:
- raw article/event intake from external news sources

Required output shape:
- `provider`
- `query`
- `raw_items`
- `provider_status`

Expected providers:
- `event_registry`
- `newsapi`
- `gdelt` (experimental / paused)

### 2. `news_relevance`
Purpose:
- score/filter/rank raw news items into market-relevant context

Required output shape:
- `speaker_relevance`
- `topic_relevance`
- `event_relevance`
- `source_quality`
- `freshness_score`
- `noise_flags`
- `final_relevance_score`
- `decision`

### 3. `social_discovery`
Purpose:
- discover candidate X/Twitter-relevant social signals

Required output shape:
- `provider`
- `query`
- `speaker`
- `topics`
- `candidate_posts`
- `candidate_accounts`
- `narrative_clusters`
- `discovery_confidence`

Initial provider:
- `grok`

### 4. `social_evidence`
Purpose:
- separate social findings into evidence classes

Suggested output shape:
- `official_posts`
- `high-signal chatter`
- `clip circulation`
- `rumor/noise candidates`
- `platform_risks`

### 5. `evidence_fusion`
Purpose:
- combine news evidence and social evidence without flattening them into one class

The fusion layer must distinguish:
- confirmed news
- social-only signal
- official speaker signal
- rumor/noise

## V1 policy

For V1:
- `Event Registry` is the recommended primary news direction
- `NewsAPI` remains the practical fallback path
- `GDELT` remains paused as an experimental provider
- `Grok` is limited to social discovery
- social discovery does not automatically become normal evidence

## Practical next move

1. Keep current `NewsAPI` path alive as fallback.
2. Add a provider contract that allows `event_registry` and `newsapi` side-by-side.
3. Keep `gdelt` paused as an experimental provider.
4. Build a `news_relevance` layer above provider output.
5. Add a separate `social_discovery` contract for Grok-driven Twitter/X signal discovery.
6. Only then fuse the two in `evidence_fusion`.
