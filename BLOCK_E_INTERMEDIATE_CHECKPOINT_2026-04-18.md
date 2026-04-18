# Block E intermediate checkpoint (Market / provider layer)

## Scope
This note records the current **intermediate** state of Block E after the first controlled cleanup passes across the Kalshi market/provider layer.

This is not a final Block E checkpoint. It is a stable intermediate marker showing that provider search/sourcing logic has started to separate into clearer seams.

---

## Canonical active surfaces in this phase

### Fetch side
- `agents/mentions/fetch/kalshi.py`

### Provider / sourcing side
- `agents/mentions/modules/kalshi_provider/provider.py`
- `agents/mentions/modules/kalshi_provider/sourcing.py`

---

## What changed in this cleanup sequence

### 1. Search fallback param semantics were isolated
In `fetch/kalshi.py`:
- `_search_market_param_sets(...)`

This separated the ordered fallback parameter strategy for `search_markets(...)`:
- `tickers`
- `series_ticker`
- `keyword`

This did not fix broader Kalshi API limitations, but it made the fallback search path more explicit and easier to reason about.

### 2. Market-set append coupling was isolated
In `modules/kalshi_provider/sourcing.py`:
- `_append_market_set(...)`

This centralized the repeated coupling between:
- appending a non-empty market set to `result_sets`
- appending the matching diagnostic label to `diagnostics`

### 3. Speaker-series sourcing was isolated
Also in `sourcing.py`:
- `_collect_speaker_series_markets(...)`

This moved out:
- series-hint iteration
- initial series fetch
- conditional series expansion
- diagnostics/result-set appends for speaker-series sourcing

### 4. Speaker-event sourcing was isolated
Also in `sourcing.py`:
- `_collect_speaker_event_markets(...)`

This moved out:
- speaker-event search
- event-seed filtering
- event expansion via `event_ticker`
- diagnostics/result-set appends for event-search sourcing

### 5. Topic-search sourcing was isolated
Also in `sourcing.py`:
- `_collect_topic_search_markets(...)`

This moved out:
- topic iteration
- topic-event hint search
- diagnostics/result-set appends for topic-search sourcing

---

## Practical effect

### Before
`build_candidate_market_pool(...)` mixed together:
- speaker-series sourcing
- speaker-event sourcing
- topic sourcing
- fallback search sourcing
- append diagnostics/result-set coupling

### After
That function still orchestrates the overall candidate-pool flow, but several branches are now explicit helpers:
- append coupling
- speaker-series branch
- speaker-event branch
- topic-search branch

This makes the sourcing layer easier to read and lowers the risk of future branch-specific cleanup drifting into copy-paste edits.

---

## Validation
Focused retrieval smoke remained stable after the Block E cleanup passes:

```bash
PYTHONPATH=. python3 scripts/smoke_retrieval.py --fast
```

Observed stable result shape:
- query path keeps `market + news + transcripts + pmt`
- ticker path keeps `market + transcripts + pmt`
- recurring Trump fallback title remains human-readable

Expected direct Kalshi ticker 404 fallback handling remained intact.

---

## What still remains in Block E

### Still active work inside provider/sourcing layer
- fallback search branch is still inline in `build_candidate_market_pool(...)`
- market-pool merge/filter sequencing is still concentrated in one function
- broader Kalshi provider limitations remain unresolved:
  - fragile exact-market fetch for some tickers
  - broad weekly surface scans still not honestly supported by the current provider path

### Not yet done
- final Block E checkpoint
- deeper provider/API semantics cleanup
- separate broad market-surface scanner work

---

## Practical assessment

### Block E status right now
- **intermediate-checkpoint-ready**

### Why
- the provider layer now has multiple explicit sourcing seams instead of one monolithic candidate-pool block
- fetch-level search fallback semantics are slightly clearer
- retrieval smoke stayed stable through the extraction sequence
- more work is still justified, so this is not a final stop

### What this means
Block E now has a safe intermediate marker. Work can continue later without losing the current provider-layer cleanup gains or forgetting which sourcing seams were already separated.

---

## Rule from here

If Block E continues later:
1. keep separating sourcing branches before attempting broader redesign
2. keep search/fallback semantics explicit
3. preserve human-readable market/event shaping on the active path
4. keep every provider-layer cleanup guarded by retrieval smoke
5. do not pretend current provider limits are solved when they are only better isolated
