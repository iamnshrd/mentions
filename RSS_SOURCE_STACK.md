# RSS Source Stack

## Decision

For the practical non-paid `mentions` V1 news path:
- use a curated RSS source stack
- start with ~10 strong media sources
- keep social discovery separate
- keep commercial aggregators out of the critical path for now

## Selection principle

Pick sources that are:
- strong for politics / geopolitics / event-driven news
- reasonably reliable for catalyst detection
- available via RSS
- more useful for actionable context than generic opinion-heavy feeds

Prefer targeted politics/world feeds over generic homepage feeds when possible.

## Initial source candidates

### Tier 1 core
1. Reuters World / Politics
2. Associated Press
3. Bloomberg
4. Financial Times
5. Politico
6. Axios

### Tier 2 supplement
7. The Hill
8. Al Jazeera
9. BBC World
10. CNN Politics or Fox News Politics (pick based on feed quality / usability)

## Architecture fit

### `rss_provider`
Purpose:
- ingest raw headlines/items from curated feeds

Required output shape:
- `provider = rss`
- `source`
- `feed_url`
- `headline`
- `summary`
- `published_at`
- `url`
- `provider_payload`

### `news_relevance`
Purpose:
- score/filter/rank RSS items into market-relevant context

### `news_cache`
Purpose:
- dedupe and persist fetched feed items for reuse

### `social_discovery`
Purpose:
- separate Grok/X discovery from normal news evidence

## V1 policy

For now:
- curated RSS becomes the practical news backbone
- relevance/ranking stays above RSS output
- social discovery remains separate
- commercial aggregators are not part of the critical path

## Practical next move

1. define the concrete feed URLs
2. build `rss_provider`
3. connect RSS output into the existing `news_relevance` layer
4. persist/dedupe useful results in cache/runtime storage
