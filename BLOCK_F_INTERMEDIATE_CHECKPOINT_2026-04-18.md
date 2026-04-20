# Block F intermediate checkpoint (Transcript / news intelligence)

## Scope
This note records the current **intermediate** state of Block F after the first controlled cleanup passes across:
- news intelligence assembly
- transcript intelligence ML retrieval / selection assembly

This is **not** a final Block F checkpoint. It is a stable intermediate marker showing that the block has started to structurally untangle.

---

## Canonical active surfaces in this phase

### News side
- `agents/mentions/modules/news_context/builder.py`

### Transcript side
- `agents/mentions/modules/transcript_intelligence/ml_builder.py`
- related semantic retrieval clients/utilities under:
  - `agents/mentions/modules/transcript_semantic_retrieval/*`

---

## What changed in this cleanup sequence

### 1. News-source merge logic was isolated
In `modules/news_context/builder.py`:
- `_merge_live_news_sources(...)`

This now holds the common live-source merge / status-promotion logic for:
- base news provider results
- Google News RSS results
- curated RSS fallback results

This slightly reduced status/merge glue embedded directly in `build_news_context_bundle(...)`.

### 2. Transcript row bookkeeping was isolated
In `modules/transcript_intelligence/ml_builder.py`:
- `_register_transcript_row(...)`

This separated the repeated bookkeeping for:
- transcript id registration
- title capture into `title_by_id`

### 3. Transcript id pool extension was isolated
Also in `ml_builder.py`:
- `_extend_transcript_ids(...)`

This now centralizes the repeated pattern:
- iterate candidate rows
- register transcript ids
- stop at a local cap

This reduced repeated discovery/selection accumulation glue.

### 4. Media analog shaping was isolated
Also in `ml_builder.py`:
- `_media_analog_row(...)`

This separated media-format analog row construction from the main selection loop.

### 5. Candidate-hit shaping was isolated
Also in `ml_builder.py`:
- `_candidate_hit(...)`

This removed the main `top_candidates` row-shaping dict from the family loop body.

### 6. Family-level scoring/fallback shaping was isolated
Also in `ml_builder.py`:
- `_score_family_rows(...)`

This moved out:
- `remote_family_score(...)` call
- remote result shaping
- local fallback row shaping
- evidence-type classification fallback

### 7. Family-level hit accumulation was isolated
Also in `ml_builder.py`:
- `_accumulate_family_hits(...)`

This now handles:
- appending per-family rows
- adjusted score computation
- top-candidate accumulation

---

## Practical effect

### Before
`ml_builder.py` especially mixed together:
- transcript discovery
- transcript id bookkeeping
- media analog shaping
- family scoring
- fallback row shaping
- top-candidate shaping
- per-family accumulation

### After
That file is still not small, but several repeated seams are now explicit and separable:
- row bookkeeping
- pool extension
- analog shaping
- hit shaping
- scoring/fallback shaping
- family accumulation

This makes the remaining orchestration easier to see and reduces future cleanup risk.

---

## Validation
Focused smoke remained stable after the Block F cleanup passes:

```bash
PYTHONPATH=. python3 scripts/smoke_text_query.py --fast
```

Observed stable result shape:
- `action = respond-with-data`
- `confidence = medium`
- `has_response = true`
- `has_synthesis = true`
- `has_reasoning = true`
- `has_sources = true`

---

## What still remains in Block F

### Still active work inside transcript side
- family-loop orchestration is still in `ml_builder.py`
- transcript discovery / family seeding can likely be separated further
- final bundle assembly is still fairly dense

### Still active work inside news side
- `news_context/builder.py` still contains multiple responsibilities:
  - provider acquisition
  - typed-news shaping
  - path-map shaping
  - sufficiency/freshness interpretation

### Not yet done
- final Block F checkpoint
- deeper transcript/news semantics quality pass
- broader corpus-quality improvements (separate from code cleanup)

---

## Practical assessment

### Block F status right now
- **intermediate-checkpoint-ready**

### Why
- both news and transcript sides have been touched
- transcript selection/discovery logic is visibly cleaner than before
- smoke stayed stable through the extraction sequence
- further work is still clearly justified, so this is not a final stop

### What this means
Block F now has a safe intermediate marker. Work can continue later without losing the current structural gains or forgetting where the cleanup boundaries have started to emerge.

---

## Rule from here

If Block F continues later, keep pushing the same direction:
1. isolate repeated shaping/bookkeeping seams first
2. separate orchestration from row/dict shaping
3. keep transcript/news cleanup incremental and smoke-guarded
4. avoid mixing presentation concerns back into intelligence builders
