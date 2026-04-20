# Transcript ↔ Mentions Pipeline Contract (V1)

## Goal

Define how transcript intelligence should interact with the main `mentions` pipeline for V1.

Core principle:
- transcripts are a **historical intelligence layer**
- transcripts are **not** a direct strike predictor
- transcripts should improve:
  - same-speaker context
  - format-aware context
  - topic-aware context
  - market readiness assessment
  - confidence / abstain quality

## Non-goals

For V1, transcripts should **not** be treated as:
- a direct generator of final trade calls
- a substitute for live event/news grounding
- a per-strike pricing engine
- a free-form dump of generic old quotes

## Retrieval target

The main pipeline should build a transcript retrieval target from market/event context.

Minimum target fields:
- `speaker`
- `event_title`
- `event_format`
- `topic_candidates`
- `market_family`
- `strike_list`

Example:
```json
{
  "speaker": "Donald Trump",
  "event_title": "Roundtable on No Tax on Tips",
  "event_format": "roundtable",
  "topic_candidates": ["No Tax on Tips"],
  "market_family": "KXTRUMPMENTION",
  "strike_list": ["Trump Account", "Newscum", "Tariff"]
}
```

## Transcript retrieval rules

A transcript candidate is useful only if it satisfies strong relevance.

Preferred signals:
1. same speaker
2. same format
3. same topic
4. recency
5. transcript-backed quote availability

Operational rule:
- a candidate should usually satisfy at least **2 of 3**:
  - same speaker
  - same format
  - same topic

Otherwise it is likely noise.

## Candidate scoring dimensions

Each transcript candidate should expose structured reasons, not just text.

Required fields per candidate:
```json
{
  "transcript_id": 123,
  "speaker_match": true,
  "format_match": true,
  "topic_match": false,
  "recency_score": 0.62,
  "relevance_score": 0.81,
  "match_reasons": [
    "same-speaker",
    "same-format"
  ],
  "quote": "...",
  "event_title": "Participates in a Roundtable",
  "event_date": "",
  "format": "roundtable"
}
```

## Transcript module outputs

The transcript layer should return a structured bundle like:

```json
{
  "status": "ok",
  "query_target": {
    "speaker": "Donald Trump",
    "event_format": "roundtable",
    "topic_candidates": ["No Tax on Tips"]
  },
  "speaker_context": {
    "speaker": "Donald Trump",
    "same_speaker_hits": 12,
    "support_strength": "medium",
    "tendency_summary": "broad-ranging in roundtable settings, often digresses beyond core topic"
  },
  "format_analogs": [ ... ],
  "topic_analogs": [ ... ],
  "counterevidence": [ ... ],
  "top_candidates": [ ... ],
  "retrieval_summary": "Found same-speaker roundtable analogs but only weak direct topic overlap.",
  "context_risks": [
    "same-topic coverage thin",
    "format match stronger than topic match"
  ]
}
```

## Structured features extracted from transcripts

The pipeline should prefer transcript-derived features over raw transcript dumps.

### Speaker-level features
- breadth vs narrowness
- scripted vs improvisational style
- tendency to riff / digress
- directness vs evasiveness in Q&A
- frequency of broad mention scatter in comparable settings

### Format-level features
- roundtable
- press conference
- prepared remarks
- announcement
- interview
- cabinet meeting
- bill signing

### Topic-level features
- economy
- energy
- Iran
- tariffs
- Social Security
- inflation
- taxes
- etc.

## How fusion should use transcript outputs

Transcripts should update:
- `speaker_tendency`
- `format_confidence`
- `topic_accessibility`
- `market_readiness`
- `confidence`
- `abstain_reasons`

Transcripts should not directly determine:
- strike resolution probability
- per-strike pricing
- final trade action without support from event/news layer

## Fusion guidance

### If transcripts are strong and live event/news is also strong
- increase confidence
- allow stronger market-level read

### If transcripts are strong but live event/news is weak
- use transcripts for historical context only
- keep low or medium confidence
- avoid overclaiming

### If transcripts are weak but live event/news is strong
- do not invent speaker-history confidence
- rely on event/news but surface missing transcript support

### If both are weak
- abstain / no-trade / low-confidence market read

## User-facing rendering rules

Transcript evidence should be rendered as:
- short tendency summary
- a few transcript-backed supporting quotes
- explicit caveats when analog quality is weak

Avoid:
- giant quote dumps
- generic biography/history padding
- pretending transcript analogs imply exact strike hits

## V1 rendering preference

Good user-facing transcript contribution:
- "In prior Trump roundtables, he ranged broadly and often drifted into adjacent economic talking points, which makes this event structurally more open-ended."

Bad V1 contribution:
- "Trump once said X in another transcript, therefore strike Y should resolve YES."

## Implementation priority

For V1, transcript work should improve in this order:
1. same-speaker retrieval quality
2. format-aware analog selection
3. topic-aware analog selection
4. transcript-derived tendency summaries
5. counterevidence and abstain support

## Current accepted design decision

For `mentions` V1:
- the final analysis target is the **market/event as a whole**
- transcripts are a **historical intelligence layer** feeding that market-level analysis
- strikes remain supporting structure only
- transcript evidence should sharpen event-level reasoning, not pull the system into strike-by-strike prediction
