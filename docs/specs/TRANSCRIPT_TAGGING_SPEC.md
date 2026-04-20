# Transcript Tagging Spec

## Goal

Provide a minimal practical tagging schema for transcript-backed retrieval in V1.

The purpose is not generic NLP completeness.
The purpose is to improve:
- topic-relevant speaker-event retrieval
- transcript-backed historical context
- mention-market usefulness
- retrieval quality for market URL -> context -> report

## Design principle

Transcript tags are a retrieval aid and evidence-shaping layer.
They must help answer:
- is this transcript/event relevant to the current market topic?
- is this the same speaker?
- is the format similar enough to matter?
- is this transcript useful for mention-market analysis?

## Required tag groups

### 1. Speaker tags
Required fields:
- `speaker_primary`
- `speaker_aliases[]`
- `speaker_family[]`

Examples:
- `Donald Trump`
- aliases: `Trump`, `DJT`
- family: `trump`, `gop`, `candidate`

### 2. Topic tags
Required fields:
- `topic_tags[]`
- `topic_family_tags[]`

Examples:
- `iran`
- `oil`
- `nuclear`
- `middle-east`
- `fed`
- `inflation`
- `rates`

Rules:
- both specific and family-level tags are allowed
- topic tags should be normalized, not just copied raw from text

### 3. Format tags
Required fields:
- `format_tags[]`

Examples:
- `speech`
- `interview`
- `press-conference`
- `q-and-a`
- `prepared-remarks`
- `debate`
- `rally`

### 4. Event tags
Required fields:
- `event_tags[]`

Examples:
- `geopolitics`
- `macro`
- `campaign`
- `policy-comment`
- `media-hit`
- `earnings-call`

### 5. Mention-market usefulness tags
Required fields:
- `mention_tags[]`

Examples:
- `direct-mention`
- `indirect-reference`
- `topic-discussion`
- `prepared-remarks-mention`
- `q-and-a-mention`
- `theme-only-no-direct-mention`

Purpose:
- indicate whether this transcript is useful for mention-market analog reasoning

### 6. Quality tags
Required fields:
- `quality_tags[]`

Examples:
- `official-transcript`
- `manual-transcript`
- `partial-transcript`
- `needs-review`
- `low-confidence-tagging`

## Minimal V1 requirements

For V1, transcript tagging is good enough if it supports:
- same-speaker filtering
- topic-relevant filtering
- format-relevant filtering
- transcript-backed prior-event retrieval
- rejection of generic non-relevant speaker history

## Non-goals for V1

V1 transcript tagging does NOT need:
- perfect ontology design
- perfect hierarchical taxonomy
- universal entity linking
- complete semantic role labeling
- graph-native document modeling

## Suggested storage shape

At minimum, store transcript tags in structured form.

Suggested fields per transcript/event:
- `speaker_primary`
- `speaker_aliases_json`
- `speaker_family_json`
- `topic_tags_json`
- `topic_family_tags_json`
- `format_tags_json`
- `event_tags_json`
- `mention_tags_json`
- `quality_tags_json`
- `tagging_confidence`
- `tagging_source`

## Tagging policy

Preferred order:
1. deterministic/manual tags when available
2. schema-first extraction
3. LLM structured outputs only under a constrained schema
4. store both raw transcript and structured tags

## Canonical V1 rule

Historical speaker context is valid for V1 only if:
- same-speaker
- transcript-backed
- topic-relevant
- and preferably format-relevant

Transcript tags are the main mechanism for enforcing that rule reliably.
