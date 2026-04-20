# Block C intermediate checkpoint (Analysis / synthesis semantics)

## Scope
This note records the current **intermediate** state of Block C after the first controlled cleanup passes across the active event-level interpretation and synthesis semantics path.

This is not a final Block C checkpoint. It is a stable intermediate marker showing that the semantics layer has started to separate into clearer, more manageable pieces.

---

## Canonical active surfaces in this phase

### Interpretation side
- `agents/mentions/runtime/speaker_paths.py`

### Synthesis / reasoning side
- `agents/mentions/runtime/synthesize_speaker.py`

---

## What changed in this cleanup sequence

### 1. Event support-state derivation was isolated
In `runtime/speaker_paths.py`:
- `_event_support_profile(...)`

This now collects the main interpretation support state in one place, instead of leaving it fully interleaved inside `build_interpretation_block(...)`.

### 2. Base interpretation dimensions were isolated
Also in `speaker_paths.py`:
- `_event_structure(...)`
- `_current_grounding(...)`
- `_topic_centrality(...)`

This made the most basic interpretation dimensions explicit and separately editable.

### 3. A real semantic wording bug was corrected
Also in `speaker_paths.py`:
- late-branch wording now uses the correct `filtered_late` family preview instead of incorrectly leaking `filtered_overextended`
- weak-hit late-preview wording was also guarded so it only appears when the late-preview state actually exists

This was not just structural cleanup. It improved interpretation correctness.

### 4. Conclusion support-state wording was isolated
In `runtime/synthesize_speaker.py`:
- `_conclusion_support_state(...)`

This separated the support-state phrase construction from the main market conclusion builder.

### 5. Evidence conclusion-note semantics were isolated
Also in `synthesize_speaker.py`:
- `_evidence_conclusion_note(...)`

This moved out the conclusion-note decision logic for:
- fresh news + historical transcript analogs
- fresh news only
- transcript analogs only
- empty case

### 6. Event-context reasoning was isolated
Also in `synthesize_speaker.py`:
- `_event_context_reasoning(...)`

This moved out:
- event setup line
- likely-topics line
- news-context line / thin-news fallback

### 7. Interpretation tail reasoning was isolated
Also in `synthesize_speaker.py`:
- `_interpretation_reasoning(...)`

This moved out:
- interpretive takeaway line
- signal-line assembly

---

## Practical effect

### Before
The active semantics path mixed together:
- support-state derivation
- interpretation-state judgments
- event-context reasoning
- evidence conclusion wording
- final interpretive tail assembly

### After
The same path is still not minimal, but several meaningful semantics seams are now explicit:
- support-state derivation
- interpretation dimensions
- conclusion support-state wording
- evidence conclusion-note logic
- event-context reasoning
- interpretation/signal tail reasoning

This makes the active event-level interpretation flow easier to inspect and safer to refine.

---

## Validation
Focused speaker synthesis smoke remained stable after the Block C cleanup passes:

```bash
PYTHONPATH=. python3 scripts/smoke_speaker_url.py --fast
```

Observed stable result shape:
- `action = respond-with-data`
- `confidence = medium`
- `has_data = true`
- `report_present = true`
- `reasoning_present = true`

Expected Kalshi direct-market 404 fallback handling remained intact.

---

## What still remains in Block C

### Still active work inside the block
- `build_interpretation_block(...)` still carries a lot of interpretive judgment assembly
- `synthesize_speaker.py` still contains dense reasoning/conclusion orchestration
- some final wording still mixes semantic decisions with string assembly

### Not yet done
- final Block C checkpoint
- deeper semantics-quality pass on event-level interpretation sharpness
- broader refinement of abstain / thin-context / weak-path semantics

---

## Practical assessment

### Block C status right now
- **intermediate-checkpoint-ready**

### Why
- the active semantics path now has several explicit, meaningful seams
- at least one real semantic bug was corrected, not just structure moved around
- speaker synthesis smoke stayed stable through the extraction sequence
- more semantics work is still justified, so this is not a final stop

### What this means
Block C now has a safe intermediate marker. Work can continue later without losing the current semantics cleanup gains or forgetting which interpretation/reasoning seams have already been separated.

---

## Rule from here

If Block C continues later:
1. keep separating semantics decisions from string assembly
2. prefer explicit interpretation dimensions over inline decision blobs
3. preserve event-level analysis semantics over strike-first regressions
4. keep every semantics cleanup guarded by speaker smoke
5. treat wording bugs as semantic bugs when they distort the actual read
