# Architecture checkpoint (2026-04-18)

## Purpose

This file captures the current post-refactor architecture of `mentions` so future cleanup and feature work can start from an explicit map instead of inferred repo lore.

---

## 1. Canonical active path

The canonical active runtime path now lives in:

- `agents/mentions/runtime/*`
- `agents/mentions/modules/*`
- `mentions_core/*`

The system should be reasoned about as:

1. **input / routing**
   - `runtime/orchestrator.py`
   - `runtime/frame.py`
   - `runtime/llm_prompt.py`

2. **retrieval spine**
   - `runtime/retrieve.py`
   - `runtime/context_retrieval.py`
   - `runtime/ticker_retrieval.py`
   - `runtime/retrieval_fallbacks.py`

3. **module layer**
   - `modules/market_data/*`
   - `modules/news_context/*`
   - `modules/transcript_intelligence/*`
   - `modules/market_prior/*`
   - `modules/pmt_legacy_kb/*`
   - `modules/pmt_selector/*`
   - `modules/text_evidence_assessor/*`
   - `modules/posterior_update/*`
   - `modules/challenge_layer/*`
   - `modules/evidence_fusion/*`
   - `modules/workflow_policy/*`

4. **analysis / synthesis**
   - `modules/analysis_engine/*`
   - `runtime/synthesize.py`
   - `runtime/synthesize_speaker.py`
   - `runtime/speaker_report.py`
   - `runtime/speaker_paths.py`

5. **presentation**
   - `presentation/profile_renderers.py`
   - `presentation/header_renderer.py`
   - `modules/output_profiles/*`

---

## 2. Synthesis layer status

`runtime/synthesize_speaker.py` was a large monolith and is now decomposed into:

- `runtime/synthesize_speaker.py`
  - synthesis assembly / orchestration
- `runtime/speaker_report.py`
  - report rendering / wording helpers / flatten sharpening
- `runtime/speaker_paths.py`
  - topic-path logic / strike baskets / interpretation block

This is the current canonical split for the event-level speaker synthesis path.

---

## 3. Retrieval layer status

The retrieval layer is now partially cleaned up and should be treated as three related but distinct pieces:

- `runtime/context_retrieval.py`
  - query-oriented context acquisition
- `runtime/ticker_retrieval.py`
  - ticker/family-specific acquisition and fallback logic
- `runtime/retrieve.py`
  - shared retrieval assembly / evidence composition

Shared retrieval fallback/default shapes are now centralized in:

- `runtime/retrieval_fallbacks.py`

Ticker-path persistence side-effects inside `runtime/retrieve.py` are now isolated behind:

- `_persist_ticker_side_effects(...)`

Shared market payload shaping inside `runtime/retrieve.py` is now isolated behind:

- `_build_market_payload(...)`

---

## 4. Kalshi provider status

The canonical modular Kalshi-facing layer is:

- `modules/kalshi_provider/*`

Interpret it as:

- `fetch/kalshi.py`
  - low-level transport / raw API calls
- `modules/kalshi_provider/provider.py`
  - normalized provider bundle layer
- `modules/kalshi_provider/sourcing.py`
  - higher-level candidate sourcing

Current code should prefer `modules/kalshi_provider/*` over direct new dependencies on `fetch/kalshi.py` whenever possible.

---

## 5. ML transcript retrieval status

ML-first transcript retrieval is now the intended main direction.

But the package contains both active runtime code and research tooling.

### Main-path ML runtime files

- `modules/transcript_semantic_retrieval/client.py`
- `modules/transcript_semantic_retrieval/family_taxonomy.py`
- `modules/transcript_semantic_retrieval/strategy.py`
- `modules/transcript_semantic_retrieval/prototype.py`
- plus integration via:
  - `modules/transcript_intelligence/ml_builder.py`

### Research / perimeter tooling

- `ab_compare.py`
- `cluster_discovery.py`
- `corpus_discovery.py`
- `experimental_path.py`
- `family_inspection.py`
- `family_rollout.py`
- `family_completion_plan.py`
- `candidate_sourcing_plan.py`
- `family_evaluation.py`

See also:

- `modules/transcript_semantic_retrieval/PACKAGE_MAP.md`

Important: not every file in `transcript_semantic_retrieval/*` is production-path code.

---

## 6. Compatibility / legacy layers

`library/*` is now explicitly compatibility-only.

This includes:

- `library/_core/fetch/*`
- `library/_core/analysis/*`
- `library/_core/runtime/*`

These layers have been cleaned up so their exports are more explicit and less wildcard-driven, but they still exist to preserve compatibility.

Current development should avoid routing new logic through `library/*`.

---

## 7. Removed / narrowed surfaces

Recent cleanup already removed or narrowed several dead or compatibility-only surfaces, including:

- legacy unused analysis helpers in:
  - `agents/mentions/analysis/history.py`
  - `agents/mentions/analysis/speaker.py`
- retired presentation compatibility implementation in:
  - `agents/mentions/presentation/render_analysis.py`
- unused persistence helpers in:
  - `runtime/persistence_helpers.py`
- broad current-path wildcard compatibility shims across:
  - `library/_core/fetch/*`
  - `library/_core/analysis/*`
  - `library/_core/runtime/*`

---

## 8. Guardrails now available

Repeatable smoke scripts now exist in:

- `scripts/smoke_speaker_url.py`
- `scripts/smoke_text_query.py`
- `scripts/smoke_retrieval.py`

These are the preferred fast regression guardrails during ongoing refactor work.

Suggested fast check set:

```bash
PYTHONPATH=. python3 scripts/smoke_speaker_url.py --fast
PYTHONPATH=. python3 scripts/smoke_text_query.py --fast
PYTHONPATH=. python3 scripts/smoke_retrieval.py --fast
```

---

## 9. Current refactor posture

The project is no longer in a good phase for broad blind repo-wide cleanup.

The recommended mode now is:

- **stabilization + targeted cleanup**
- use smoke harnesses after structural changes
- avoid re-expanding compatibility layers
- prefer small boundary cleanups over giant rewrites unless a hotspot clearly justifies it

---

## 10. Best next refactor target

The next best structural target after this checkpoint is:

- continued **retrieval boundary cleanup** in `runtime/retrieve.py`

Focus there should be:

- cleaner separation between acquisition, shaping, composition, and side-effects
- preserving current smoke coverage while continuing cleanup
