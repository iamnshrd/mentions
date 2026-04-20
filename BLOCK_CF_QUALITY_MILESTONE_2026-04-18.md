# Block C/F quality milestone (Evidence contracts -> semantics)

## Scope
This note records the first meaningful quality milestone across the current Block F and Block C work.

The key shift is that evidence-shape improvements are no longer only structural. News and transcript intelligence contracts now affect live event-level reasoning and confidence semantics in the active speaker-event runtime path.

---

## What changed before this milestone

### Block F: intelligence contracts became explicit
In `agents/mentions/modules/news_context/builder.py`:
- `_typed_news_contract(...)`

The typed-news layer now exposes contract-level signals such as:
- `has_event_core`
- `has_topic_expansion`
- `has_ambient_regime`
- `coverage_state`

In `agents/mentions/modules/transcript_intelligence/ml_builder.py`:
- `_transcript_intelligence_contract(...)`

The transcript-intelligence layer now exposes contract-level signals such as:
- `has_core_support`
- `has_spillover_support`
- `has_generic_regime`
- `support_shape`

This means the two intelligence layers now behave more like aligned evidence contracts rather than two unrelated raw dict payloads.

---

## What changed at this milestone

### Block C: semantics now consume those evidence contracts
In `agents/mentions/runtime/synthesize_speaker.py`:
- `_event_context_reasoning(...)`
- `_build_evidence_view(...)`
- `_evidence_conclusion_note(...)`
- `_compute_confidence(...)`

The active speaker-event synthesis path now reads:
- news `coverage_state`
- transcript `support_shape`

---

## Practical effect on reasoning

### Before
The runtime could often say some form of:
- fresh news exists
- transcript support exists

without strongly distinguishing whether that support was:
- direct event grounding
- adjacent-topic grounding
- ambient regime noise
- core analog support
- spillover analog support
- generic regime context

### After
The reasoning layer now distinguishes between:
- `event-led` news
- `topic-led` news
- `ambient-only` news

and between:
- `core-led` transcript support
- `spillover-led` transcript support
- `generic-only` transcript support

This makes the event-level interpretation more honest about what kind of support is actually present.

---

## Practical effect on confidence

### Before
Confidence depended mostly on broad presence checks such as:
- market present
- news present
- transcripts present
- tendency / analog counts

### After
Confidence now also reacts to evidence shape:
- `event-led` news can increase grounding/confidence
- `core-led` transcript support can increase grounding/confidence
- `ambient-only` news reduces grounding/confidence
- `generic-only` transcript support reduces grounding/confidence
- `spillover-led` transcript support gets a lighter downgrade
- bad combined cases (for example ambient/empty news plus generic/empty transcript support) get penalized more clearly

This moves confidence closer to **analysis-context honesty**, not just evidence-presence counting.

---

## Why this matters for V1

The V1 goal is event-level market analysis with honest grounding.

This milestone helps because the system is now better at separating:
- true event support
- adjacent but weaker support
- generic contextual noise

That directly improves:
- abstain honesty
- confidence honesty
- event-level interpretation quality

This is a more meaningful quality improvement than another purely structural cleanup pass.

---

## Validation
The active runtime path remained stable after these changes:

```bash
PYTHONPATH=. python3 scripts/smoke_text_query.py --fast
PYTHONPATH=. python3 scripts/smoke_speaker_url.py --fast
```

Observed stable outputs included:
- response present
- synthesis present
- reasoning present
- report present on speaker URL path
- expected Kalshi direct-market fallback behavior still intact

---

## Practical conclusion

This is the first clear point where the Block F contract work and the Block C semantic work became behaviorally linked:

- Block F improved evidence shape
- Block C began consuming that shape in reasoning
- Block C then consumed it in confidence semantics

That means the codebase now has a real **evidence-contract -> reasoning/confidence** path in the active runtime.

This should be treated as a meaningful quality milestone, not just another cleanup note.

---

## Rule from here

If this line of work continues:
1. prefer making evidence contracts affect interpretation and confidence, not just output labels
2. preserve the distinction between event-direct support and ambient/generic support
3. avoid flattening weak/adjacent context back into fake direct grounding
4. keep validating through the stable active runtime smoke paths after each semantic pass
