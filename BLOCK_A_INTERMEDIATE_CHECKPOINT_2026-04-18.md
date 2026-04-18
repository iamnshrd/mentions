# Block A intermediate checkpoint (Runtime orchestration)

## Scope
This note records the current **intermediate** state of Block A after the first controlled cleanup passes across the active runtime orchestration layer.

This is not a final Block A checkpoint. It is a stable intermediate marker showing that orchestration result shaping and turn-state responsibilities have started to separate into clearer pieces, and that the two main active runtime paths now each have an explicit use-case seam.

---

## Canonical active surfaces in this phase

### Main orchestration path
- `agents/mentions/runtime/orchestrator.py`

### Related active runtime surfaces
- `agents/mentions/runtime/frame.py`
- `agents/mentions/runtime/respond.py`
- `agents/mentions/runtime/routes.py`

This intermediate cleanup focused mainly on `runtime/orchestrator.py`.

---

## What changed in this cleanup sequence

### 1. Direct-answer fallback result was isolated
In `runtime/orchestrator.py`:
- `_direct_answer_result(...)`

This separated the no-KB direct-answer fallback result shape from `_orchestrate_inner(...)`.

### 2. Main success result payload was isolated
Also in `runtime/orchestrator.py`:
- `_success_result(...)`

This separated the common success payload assembly for the main text-query flow.

### 3. URL success result payload was isolated
Also in `runtime/orchestrator.py`:
- `_url_success_result(...)`

This separated the success payload assembly for the active URL/speaker-event flow.

### 4. Shared session/checkpoint turn-state work was isolated
Also in `runtime/orchestrator.py`:
- `_record_turn_state(...)`

This moved out the shared responsibility for:
- `update_session(...)`
- `log_checkpoint(...)`
- common turn-state payload fields

It is now reused by both the text-query flow and the URL flow.

### 5. LLM prompt result finishing was isolated
Also in `runtime/orchestrator.py`:
- `_llm_prompt_result(...)`

This separated the final prompt-result finishing step inside `orchestrate_for_llm(...)`.

### 6. Frame-selection error result was isolated
Also in `runtime/orchestrator.py`:
- `_frame_error_result(...)`

This separated the frame-selection error branch from inline orchestration control flow.

### 7. Shared text use-case seam was introduced
Also in `runtime/orchestrator.py`:
- `_text_use_case(...)`

This created a shared text runtime scenario for:
- frame selection
- retrieval bundle assembly
- synthesis kickoff

It is now reused by:
- `_orchestrate_inner(...)`
- `orchestrate_for_llm(...)`

### 8. Shared URL use-case seam was introduced
Also in `runtime/orchestrator.py`:
- `_url_use_case(...)`

This created a shared URL/speaker-event runtime scenario for:
- Kalshi URL parsing
- ticker extraction
- speaker resolution
- ticker retrieval
- transcript/news/market bundle preparation
- speaker-market synthesis kickoff
- synthesis enrichment from the retrieval bundle

It is now used by:
- `_orchestrate_url_inner(...)`

---

## Practical effect

### Before
`runtime/orchestrator.py` mixed together:
- mode detection
- branching
- retrieval/analysis orchestration
- result dict shaping
- session/checkpoint updates
- prompt finishing
- fallback result shaping
- duplicated active-path orchestration chains across text and URL flows

### After
The file still orchestrates the flow, but several repeated or branch-specific responsibilities are now explicit:
- direct-answer fallback result
- main success result
- URL success result
- frame-selection error result
- shared turn-state persistence/checkpoint work
- LLM prompt result finishing
- shared text use-case orchestration seam
- shared URL use-case orchestration seam

This makes the orchestration layer easier to inspect, reduces return-dict/persistence duplication, and starts to move the runtime closer to an application/use-case shape rather than only a collection of helper extractions.

---

## Validation
Focused runtime smoke remained stable after the Block A cleanup passes:

```bash
PYTHONPATH=. python3 scripts/smoke_text_query.py --fast
PYTHONPATH=. python3 scripts/smoke_speaker_url.py --fast
```

Observed stable result shape:
- text-query path still returns response/synthesis/reasoning/sources
- URL path still returns speaker-event analysis data
- expected Kalshi direct-market 404 fallback handling remained intact

---

## What still remains in Block A

### Still active work inside the block
- `orchestrator.py` still carries a lot of branch sequencing inline
- `_resolve_frame_and_bundle(...)` still mixes several responsibilities and may itself want a clearer contract later
- `orchestrate_for_llm(...)` still has more orchestration logic that could be separated
- the text and URL use-case seams are still function-level seams, not yet fuller service objects/protocol-backed contracts
- neighboring runtime modules are still more concrete than ideal from a clean-architecture perspective

### Not yet done
- final Block A checkpoint
- deeper runtime orchestration cleanup
- broader runtime path simplification across neighboring runtime modules

---

## Practical assessment

### Block A status right now
- **intermediate-checkpoint-ready**

### Why
- result branches are no longer purely inline
- turn-state persistence/checkpoint work is now centralized
- both primary active runtime paths now have explicit use-case seams
- both text-query and URL active flows remained stable under smoke
- more work is still justified, so this is not a final stop

### What this means
Block A now has a safe intermediate marker. Work can continue later without losing the current orchestration cleanup gains or forgetting which runtime responsibilities have already been separated.

---

## Rule from here

If Block A continues later:
1. keep separating orchestration control flow from payload/result shaping
2. centralize repeated persistence/checkpoint responsibilities before deeper rewrites
3. preserve the currently stable text-query and URL paths with smoke after each step
4. avoid mixing presentation logic back into runtime orchestration
5. prefer shared use-case seams over isolated helper extraction when a real scenario boundary exists
6. prefer small contract/boundary steps over one large orchestrator rewrite
