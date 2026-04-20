# NOTES.md — Mentions Development Log

## Status
**v0.14.7 — Temporal retrieval + latency analytics + section tagging**

Three orthogonal wins layered onto the v0.14.6 foundation: retrieval
now respects recency, the eval layer can ask *when* a heuristic
resolves, and transcript chunks carry a section label
(intro/prepared/qa/closing) instead of an empty string.

### T4 — Temporal-aware retrieval (exponential half-life)

Retrieval previously treated a 2016 speech and yesterday's briefing
as equally current. New module
``library/_core/retrieve/recency.py`` applies a multiplicative
exponential decay to ``score_final`` based on
``transcript_documents.event_date``:

```
weight = exp(-ln(2) × Δdays / half_life_days)
```

Default half-life 365 days; floor 0.1 so seminal old sources never
lose their BM25 signal entirely. Missing / future dates → neutral
1.0 (no penalty, no boost). ``RetrievalHit`` gains
``score_recency: float = 1.0`` so callers can inspect the multiplier.
``hybrid_retrieve`` accepts ``recency_half_life_days=None`` to
disable.

17 new tests in ``tests/test_recency.py``.

### D1 — ``decision_cases.outcome_resolved_at`` (schema v10)

The posterior mean told you *how often* a heuristic works; the
counterfactual layer told you whether it *adds signal*. Neither
answered *when* — is this a 2-day edge or a 3-week drift? New
column + analytics module closes that gap.

``_v10`` adds ``decision_cases.outcome_resolved_at TEXT`` + index.
``library/_core/eval/resolution_latency.py`` exposes:

* ``set_case_outcome(conn, case_id, outcome, *, resolved_at=None)``
  — atomic two-column write; the canonical path for outcome writes
  going forward (enforces ``outcome IS NULL ↔ outcome_resolved_at IS NULL``).
* ``case_latency_days(conn, case_id)`` — days between ``created_at``
  and ``outcome_resolved_at``; None for corrupt rows
  (resolved < created).
* ``heuristic_latency_stats(conn, heuristic_id)`` —
  ``{win: {n, mean, median}, loss: {...}}`` in days, joined via
  ``case_principles``.

12 new tests in ``tests/test_resolution_latency.py``.

### T2 — Section tagging (intro / prepared / qa / closing)

The v1 schema carried ``transcript_chunks.section`` but no writer
ever populated it — every row was the empty string. Wasted slot:
Q&A answers are reactive and historically where policy surprises
happen, while prepared remarks are scripted. A heuristic that
works on prepared-remarks Fed language may systematically fail on
Q&A answers.

New module ``library/_core/ingest/section_tagger.py`` with a pure
function ``tag_sections(chunks) -> list[str]``:

* ``intro`` — first chunk (unless it opens cold with a question)
* ``qa``   — from the first chunk matching a Q&A trigger onward
  (latch: Q&A doesn't return to prepared mid-session)
* ``closing`` — only the last chunk, and only if it's still
  prepared AND matches a closing phrase
* ``prepared`` — everything else

Triggers are regex: "question from", "next question", "Mr.
Chairman", "reporter:", line-start "Q:", "thanks for taking my
question", etc. No LLM, no DB access — safe to re-run on
rechunk. Wired into ``_insert_chunks`` so ``section`` is populated
from ingest onward.

18 new tests in ``tests/test_section_tagger.py``.

### Totals

**635 tests passing** (+47 over v0.14.6: 17 recency + 12 latency +
18 section tagger). LATEST_VERSION 9 → 10 (additive, nullable).

### Next steps

* **T3 — Cross-encoder rerank** — pipeline is now cheap enough
  (D7/D2) to afford the extra latency.
* **P1 — Latency-aware posteriors** — split the Beta posterior by
  resolution horizon (≤3d / ≤14d / long) using D1's new column.
* **A1 — ``regime='qa'`` promotion** — T2 now labels chunks; plumb
  ``section`` into ``record_application`` so Q&A utterances get
  their own posterior slice.

---

## v0.14.6 — DB foundations + canonical speaker attribution

Three improvements across the transcript and DB blocks. Cheap +
infrastructural — they set the groundwork for the next retrieval /
analysis passes (cross-encoder rerank, temporal decay in retrieval,
latency-aware posteriors).

### D7 — WAL + synchronous=NORMAL on every connection

``library/db.py`` now issues ``PRAGMA journal_mode = WAL`` and
``PRAGMA synchronous = NORMAL`` on each ``connect()``. Default
``DELETE`` + ``FULL`` cost an fsync per commit; on Windows this was
tens of ms each, and the test suite paid it hundreds of times per
run.

Effect: full suite dropped **61s → 15s** (≈4× speedup). Ingest paths
(batch ``record_application``, transcript writes) benefit
proportionally. Durability window shrinks from "zero" to "last WAL
checkpoint" — acceptable for an analytical DB whose inputs (Kalshi,
news, transcripts) are all re-fetchable.

5 new tests in ``tests/test_db_pragmas.py`` verify WAL persists
across connections and FK enforcement still holds.

### D2 — FTS5 sync via triggers (schema v8)

Before: ``transcript_chunks_fts`` required explicit ``sync_document`` /
``sync_chunks`` calls after every write. Any path that skipped
those calls (admin SQL, future modules forgetting) left FTS quietly
stale and BM25 returned zero hits with no error.

``_v8`` installs three AFTER triggers on ``transcript_chunks``
(insert / delete / update) using SQLite's standard external-content
pattern. The ``sync_*`` helpers in ``fts_sync.py`` remain as
emergency rebuild tools; normal writes no longer need them.

8 new tests in ``tests/test_fts_triggers.py`` cover insert, delete,
update, cascade-on-document-delete, and backcompat with the old
sync helper (no duplicates).

### T1 — Canonical speaker attribution per chunk (schema v9)

Panel transcripts produce surface-name drift — "Chair Powell",
"Jerome Powell", "J. Powell" — that silently broke the
reliability-weighted retrieval layer's join on
``speaker_profiles.canonical_name``.

New module ``library/_core/analysis/speaker_canonicalize.py``
resolves a surface name to the canonical profile through a
conservative match policy:

1. Exact case-insensitive match on ``canonical_name``
2. Exact match on any entry in the profile's ``aliases`` JSON array
3. Unique last-name suffix — only fires when exactly one canonical
   shares that final token. Prevents "Powell" → Jerome-or-Colin
   ambiguity collapse.

Explicitly no fuzzy/Levenshtein matching — false collapse risk
outweighs a few unresolved names. Profiles are cached in-process;
``invalidate_cache()`` busts it after profile writes.

Schema v9 adds ``transcript_chunks.speaker_canonical TEXT`` (indexed).
The ingest path (``_insert_chunks``) resolves per chunk and writes
the canonical; NULL when no match. ``RetrievalHit`` gains a
``speaker_canonical`` field carried through from the BM25 SELECT,
and ``reliability.apply_weights`` / hybrid's reliability path now
prefer canonical over raw surface.

17 new tests across ``test_speaker_canonicalize.py`` (exact / alias /
suffix / ambiguous / batch / cache) and
``test_chunk_canonical_attribution.py`` (hit shape, weight lookup,
column nullability).

### Totals

588 tests passing (+30 over v0.14.5: 5 pragmas + 8 FTS triggers +
11 canonicalize + 3 chunk attribution + 3 hit/weight).
LATEST_VERSION 7 → 9 (additive, nullable, backfill-free).

### Next steps

* **T3 — Cross-encoder rerank** (now a better next move: D7/D2
  made the pipeline cheaper, so the extra latency budget buys more).
* **T4 — Temporal-aware retrieval** (half-life boost on
  ``event_date``).
* **D1 — ``decision_cases.outcome_resolved_at``** (unlocks
  resolution-latency stats per heuristic).
* **T2 — Section tagging (intro / Q&A / prepared)** — paves the
  way for ``regime='qa'`` promotion in the posterior path.

---

## v0.14.5 — Auto-regime detection (closes the tagging loop)

v0.14.4 made posteriors sliceable by regime but left the tag itself
as a caller obligation — every ``record_application`` site had to
hand-label the context. That's how regime columns end up full of
``NULL`` in practice. v0.14.5 auto-classifies.

### Regime detector

New module ``library/_core/analysis/regime.py`` with two entry
points:

* ``detect_regime(bundle) -> str | None`` — one canonical label for
  the caller's ``regime=`` kwarg.
* ``detect_regime_tags(bundle) -> list[str]`` — full multi-label set
  for offline analysis.

Priority order (calendar → vol → trend → calm):

* ``pre_fomc`` — ticker prefix ``KXFED`` / ``FED`` / ``FOMC`` closing
  within 3 days
* ``event_day`` — any ticker closing within 24 h
* ``high_vol`` — YES-price range ≥ 20 ¢ across the retrieved history
* ``low_vol`` — range ≤ 5 ¢
* ``trending_up`` / ``trending_down`` — |last − first| ≥ 15 ¢
* ``calm`` — fallback when any bundle input exists but no tag fires

An empty bundle returns ``None`` so callers leave the column NULL
rather than fabricating a context. Pure / synchronous / no I/O —
safe to call on every synthesis pass.

### Synthesize wiring

``library/_core/runtime/synthesize.py`` now calls ``detect_regime``
and attaches ``synthesis['regime']`` to the returned dict. Downstream
learners (``record_application``, ``record_speaker_application``)
can now pick this up without the caller having to know the current
market context — the classification already happened during synthesis.

### Tests

``tests/test_regime.py`` — 27 tests covering:

* ISO / Z-suffix / naive / date-only timestamp parsing
* Price extraction from mixed-shape history rows
* Pre-FOMC across prefix variants + past-close rejection
* Event-day generic calendar tag
* High-vol / low-vol / calm range thresholds
* Trend detection in both directions
* Priority (calendar beats price) + coexistence tags
* Degenerate bundles (empty, non-dict, single-price) → sensible defaults

### Totals

558 tests passing (+27 over v0.14.4: regime module).
LATEST_VERSION still 7 — no schema change this cycle.

### Next steps

* **Regime-posterior promotion path** — today the auto-detected
  regime just gets stored; a future pass should prefer
  ``top_confident_for_regime(current)`` when building the heuristic
  context for synthesis, not regime-agnostic ``top_confident``.
* **NLI-based evidence-conflict upgrade** (carried forward).
* **Retrieval cost/latency observation** under the reliability join.

---

## v0.14.4 — Regime-conditioned posteriors + counterfactual heuristic lift

Two analytical upgrades on the posterior infrastructure. The first
lets posteriors be sliced by market regime; the second asks a
question the posteriors alone can't answer — *are the heuristics
that fire actually driving wins, or just riding along?*

### Regime-conditioned heuristic + speaker posteriors

Schema v7 adds a nullable ``regime`` TEXT column to both
``heuristic_applications`` and ``speaker_stance_applications``
(indexed). ``record_application`` / ``record_speaker_application``
gain a ``regime`` kwarg so callers can tag each outcome with the
regime active at decision time (``'high_vol'``, ``'bull'``,
``'pre_fomc'`` — free-form strings, no enum yet).

On the read side, two new helpers in ``heuristic_learn``:

* ``posterior_by_regime(conn, heuristic_id)`` — walks the audit log
  and returns ``{regime: Beta stats}`` starting from Beta(1, 1) per
  bucket. Answers "is this heuristic strong under high-vol but
  noise elsewhere?".
* ``top_confident_for_regime(conn, regime, ...)`` — ranks heuristics
  by their *conditional* posterior for the specified regime.
  Heuristics with only regime-agnostic history are correctly
  excluded — no evidence for this regime, no ranking.

Tests: 12 new (schema + record persistence + slicer + ranked
queries).

### Counterfactual heuristic-lift analysis

Schema v7 also adds a binary ``outcome`` INTEGER column to
``decision_cases`` (NULL = unresolved). Separate from the existing
free-form ``outcome_note`` so analysis can key on a
machine-readable column.

``library/_core/eval/counterfactual.py`` uses the resolved
``decision_cases`` rows as ground truth to compare:

* ``p_with``    — win rate when the heuristic was in ``case_principles``
* ``p_without`` — win rate when it wasn't
* ``lift``      — ``p_with − p_without``, with Wilson 95 % CIs on
                  each rate and a conservative additive CI on the
                  delta.

Why this matters: the Bayesian posterior on
``heuristics.alpha/beta`` answers "when we applied it, how often
did it work?" — which conflates heuristic quality with decision
quality. A heuristic only invoked when the call was already easy
looks excellent by posterior and contributes nothing by lift.

Surfaces:

* ``heuristic_lift(conn, id)`` — per-heuristic counterfactual.
  Returns ``None`` when either the with-or-without side is empty
  (no comparison possible).
* ``all_heuristic_lifts(conn, min_n_with=3)`` — sorted descending
  by lift; the top of the list is where signal comes from.
* ``kill_list(conn, min_n_with=5, lift_threshold=0.0)`` — heuristics
  whose *upper* CI bound is ≤ 0. Uses the bound, not the point
  estimate, so only heuristics we're confident aren't helping get
  flagged. Quarterly-audit tool for retiring noise.

Tests: 14 new (Wilson edge cases, positive/negative lift, unresolved
rows skipped, ranking, kill-list confidence).

### Totals

**Tests:** 531 passing (+26 over v0.14.3: 12 regime + 14
counterfactual).

**LATEST_VERSION:** 7 (was 6). Additive migration — two TEXT
columns and one INTEGER column, all nullable. Existing rows are
untouched.

**Next steps:** NLI-based evidence-conflict upgrade (swap keyword
lexicon for sentence-pair entailment on a small local model),
regime *detection* (auto-classify current market conditions so
callers don't have to hand-tag every ``record_application``
invocation), cost/latency budget on retrieval (observe the new
reliability join under load).

**v0.14.3 — Analytical block round three: reliability-weighted
retrieval, time-decayed posteriors, cross-market hedge detection**

Three more backlog items landed on top of v0.14. Theme: make the
posterior machinery built in v0.13/v0.14 actually *do work* for
decisions, not just sit in storage.

### Reliability-weighted retrieval

The v5 ``speaker_profiles.alpha/beta`` were read-only until now.
``library/_core/retrieve/reliability.py`` closes the loop: after
RRF fusion in ``hybrid_retrieve``, each hit's ``score_final`` is
multiplied by a per-speaker reliability weight in ``[0.5, 1.5]``
derived from the Beta posterior::

    weight = 0.5 + α / (α + β)

Speakers with fewer than 3 recorded outcomes (or no profile at all)
get weight 1.0 — no cold-start penalty for unknowns. Hits now carry
a ``score_reliability`` field for introspection, and a
``reliability_weight=False`` kwarg on ``hybrid_retrieve`` disables
the multiplier for regression-stable tests.

Integration test: two identical chunks by two different speakers
with identical BM25 scores — the high-posterior speaker's chunk
ranks first. Tests: 18 new.

### #4 — Time-decayed Bayesian posteriors

Pre-v0.14.2 α/β counters grew monotonically forever. In a
non-stationary market that's wrong: a 2020 outcome is not evidence
about today. ``library/_core/analysis/time_decay.py`` introduces
read-time exponential weighting — we walk the audit log and
accumulate ``α = 1 + Σ outcome × exp(-ln(2) × Δt / half_life)``
instead of using the stored cumulative counts.

Both ``top_confident`` (heuristics) and ``top_confident_speakers``
gain a ``half_life_days`` kwarg. Default half-life is 180 days, so
a one-year-old outcome weighs ~0.25 of a fresh one. Setting
``half_life_days=0`` explicitly disables decay; omitting it
preserves pre-v0.14.2 behaviour (stored counts).

Write path stays untouched — the audit log is the source of truth
and can be re-weighted with any λ offline. Tests: 22 new (parsing,
weight math, DB integration, ranking inversion for stale winners).

### #10 — Cross-market hedge detection

Schema v6 adds ``market_ticker`` to ``decision_cases`` (indexed,
backfill omitted). ``library/_core/analysis/hedge_check.py`` uses
Kalshi's ticker convention — ``KXFED-25MAR-T25`` and
``KXFED-25MAR-PAUSE`` share prefix ``KXFED-25MAR`` and resolve the
same event — to detect two risk classes:

* ``contradiction`` — same ticker, opposite decision within the
  lookback window (default 30 days). The agent flipped its call.
* ``stacked_yes`` / ``stacked_no`` — sibling outcome, same
  direction. At most one can resolve YES; stacking is incoherent.

``check_hedge_conflict(conn, ticker, decision)`` returns a
synthesis-friendly dict (``conflicts``, ``flags``, ``any_triggered``)
mirroring the anti-patterns / evidence-conflict shape so callers
fold it into the same ``warnings`` machinery. Ticker parsing
(``ticker_prefix``, ``ticker_outcome``) is case-insensitive and
tolerant of short/malformed inputs. Tests: 23 new.

### Totals

**Tests:** 505 passing (+63 over v0.14: 18 reliability + 22
time-decay + 23 hedge-check).

**LATEST_VERSION:** 6 (was 5). Additive migration — existing DBs
get a nullable ``market_ticker`` column and a new index.

**Next steps:** regime-conditioned heuristics (split α/β by
``market_type`` or vol regime), counterfactual eval on
``decision_cases`` audit log (what would P&L have been without
heuristic X?), NLI-based evidence-conflict upgrade (replace the
keyword lexicon with sentence-pair entailment once the corpus
justifies the cost).

**v0.14 — Analytical block round two: LLM-vs-rules calibration,
evidence-conflict detection, speaker-stance posterior**

Three more backlog items landed on top of v0.13. All of them tighten
the feedback loop between what the agent *says* and what it *gets
right*.

### #3 — LLM vs rules-baseline calibration diff

The harness always ran a single pass: whatever client was injected,
that's what drove intent classification. If the LLM path silently
degraded (temperature drift, schema changes, API outage fallback),
we'd only notice when route accuracy dipped aggregate. v0.14 adds a
``compare_paths=True`` kwarg to ``run_eval`` (and a ``--compare-paths``
CLI flag) that runs a shadow pass with :class:`NullClient` forcing
the deterministic rules path, then emits a ``path_comparison`` block
with ``llm`` / ``rules`` / ``delta`` summaries per metric.

Delta convention: positive on ``intent_accuracy`` / ``auc_roc`` /
``resolution`` / ``sharpness`` means LLM wins; positive on ``brier`` /
``log_loss`` / ``ece`` means LLM is worse. A regression test asserts
that a "liar" FakeClient returning confidently wrong answers shows up
with worse Brier than the rules baseline.

New helpers factored out: ``_calibration_summary``,
``_shadow_rules_pass``, ``_path_comparison_delta``. Tests: 12 new
(TestCalibrationSummary, TestDelta, TestShadowRulesPass,
TestRunEvalCompare).

### #9 — Evidence-conflict detection folded into p_signal

Pre-v0.14 ``synthesize`` fed retrieved transcripts + news into the
analytical path without checking whether they *agreed*. A hawkish
Powell quote and a dovish Powell quote in the same bundle would
produce a confident directional call on contradictory inputs.

``library/_core/analysis/evidence_conflict.py`` adds a cheap
keyword-based stance classifier (domain lexicon tuned to Fed / macro /
Kalshi rate markets) and a bundle-level ``detect_conflict`` that
counts bullish vs bearish snippets across ``transcripts`` + ``news``.
When the minority side is ≥ 30 % of polarised signals, the bundle is
flagged ``conflicted`` with a downweight ``factor_p`` given by
``0.50 − 0.40 × conflict_ratio`` (so perfect 50/50 → 0.30).

``synthesize.py`` folds the factor through the same
``warnings['factor_ps']`` dict that anti-patterns use, so one call to
``apply_to_p_signal`` combines everything. Warnings now carry a
``conflict`` sub-dict with stances / counts / flag for rendering.
Tests: 17 new (classifier, detector, apply_to_p_signal, synthesize
integration).

### #7 — Bayesian posterior for speaker stance

Schema v5 extends the v4 pattern from heuristics to speakers.
``speaker_profiles`` gains ``alpha`` / ``beta`` columns (Beta(1, 1)
prior), and a new ``speaker_stance_applications`` audit table logs
each time a speaker's stance was an input to a decision that
resolved, along with the ``stance`` label for later slicing.

``library/_core/analysis/speaker_learn.py`` mirrors the
``heuristic_learn`` API: ``get_counts``, ``posterior_p``,
``posterior_ci``, ``top_confident_speakers`` (ranked by CI lower
bound), ``record_speaker_application``, ``reset_posterior``. Bonus
helper ``posterior_by_stance(conn, speaker_id)`` walks the audit log
and returns per-stance Beta parameters without committing a
per-(speaker, stance) schema — a useful slicer for offline questions
like "is Powell-hawkish reliable even when Powell-overall isn't?".
Tests: 14 new.

### Totals

**Tests:** 442 passing (+43 over v0.13: 12 compare-paths + 17
evidence-conflict + 14 speaker-learn).

**LATEST_VERSION:** 5 (was 4). Additive migration — existing DBs
get the two α/β columns at default 1.0 and an empty applications
table.

**Next steps** (from the improvement backlog): #4 (time-decay for
heuristic confidence — older outcomes weigh less), #10 (cross-market
hedge detection), reliability-weighted retrieval (multiply
BM25/semantic score by source posterior), regime-conditioned
heuristics (split α/β by market_type), counterfactual eval on the
``decision_cases`` audit log.

**v0.13 — Analytical block: probabilities, anti-patterns, richer eval,
Bayesian heuristic learning**

v0.12 closed the infrastructure debts. v0.13 is the first release that
meaningfully improves *how the agent reasons*, not how it operates.
Four backlog items landed in a single batch.

### #1 — Probabilities instead of labels

The analytical path used to speak in three-bucket labels
(`confidence ∈ {low, medium, high}`,
`signal_strength ∈ {strong, moderate, weak, unknown}`). Coarse labels
make calibration impossible — the v0.10 harness measures Brier / ECE
against a probability, so a "medium" answer collapses to one bin
and is never sharply calibrated. v0.11 baseline: `ece = 0.20`.

**New:** `library/_core/analysis/probability.py` —
- `clamp01`, `logit`, `sigmoid`
- `label_from_p` / `p_from_label` (only used at UI/back-compat edges)
- `combine_independent(prior, factors)` — log-odds combinator,
  symmetric around 0.5, stacks cleanly
- `kelly_fraction(p, q, fractional=0.25, cap=0.25)` — fractional
  Kelly for binary Kalshi-style markets; returns 0 when `p ≤ q`.

**Refactored:**
- `analysis/signal.py`: every factor (price_move, volume_ratio,
  route) now returns a `p ∈ [0,1]`; `combine_independent` folds them
  into `p_signal`. Legacy `verdict` / `signal_strength` / `score`
  are derived from `p_signal` so the two views are always
  consistent.
- `analysis/trade_params.py`: the 3×3 `(confidence, difficulty)`
  sizing lookup is gone. Size is now `kelly_fraction(p_yes, q)` with
  `kelly_cap` / `kelly_fraction` controlling conservatism (tunable
  via `thresholds.json`). Output dict carries `p_yes`, `q_market`,
  `p_edge`, `sizing_method` (`kelly` | `kelly_from_label`).

**Tests (+31):** `test_probability.py` (16) covers clamp, logit round-
trip, combinator symmetry & compounding, Kelly math incl.
negative-edge skip, cap, extreme-q zero. `test_signal.py` (7)
verifies p_signal direction, legacy field presence, factor
attribution. `test_trade_params.py` (8) checks Kelly path +
legacy-label fallback.

### #6 — Anti-patterns wired into synthesis

Schema v2 imported `anti_patterns`, `crowd_mistakes`, and
`dispute_patterns` from the PMT dump, but **no code in `analysis/`
or `runtime/` read them**. Pre-paid data sitting idle.

**New:** `library/_core/analysis/anti_patterns.py`:
- `check_anti_patterns(bundle)` — scans the retrieve bundle's
  `doc_ids` for rows in each of the three tables. Returns
  structured warnings plus per-category factor probabilities
  (`anti_pattern → 0.42`, `crowd_mistake → 0.44`,
  `dispute_pattern → 0.40`).
- `apply_to_p_signal(p, warnings)` — folds the factor ps into an
  existing `p_signal` via `combine_independent`.

**Wired into `synthesize.py`:** after `assess_signal`, active
warnings downweight `p_signal`, verdict/strength are re-derived, and
the final synthesis dict now carries a top-level `warnings` key with
the flag bullets and per-category row lists. A single anti-pattern
shaves ~5pp; three stack to ~15pp — defensive, not punishing.

**Tests (+9):** `test_anti_patterns.py` covers empty bundle, all
three categories surfacing, unrelated docs not matching, and
`apply_to_p_signal` compounding.

### #8 — Eval harness: resolution, sharpness, AUC, profit-sim

The v0.10 calibration report was `{brier, log_loss, ece, bins}`.
That tells you *how miscalibrated* but not *how discriminating* or
*how profitable*. v0.13 adds four more axes to `calibration`:

- `base_rate` — unconditional P(correct) across the gold set.
- `resolution` — weighted variance of bin accuracies around the
  base rate. From the Brier decomposition:
  `Brier = Reliability − Resolution + Uncertainty`.
- `sharpness` — mean `|p − 0.5|`. High = willing to commit; low =
  hedging near 0.5. Orthogonal to calibration.
- `auc_roc` — Mann-Whitney U implementation with tie-aware ranks.
  0.5 = no discrimination; 1.0 = perfect separation.

Plus a top-level `profit_sim` field (only active when gold entries
carry `market_price` and `expected_outcome`):
- `n`, `n_bet`, `wins`, `losses`, `pnl`, `roi`
- Uses `kelly_fraction` at default `fractional=0.25, cap=0.25`.
- This is the honest bottom line for a trading agent: calibration
  in service of dollars.

**Tests (+19):** `test_eval_metrics.py` — resolution (perfect split
→ 0.25, all-at-base → 0), sharpness (hedging → 0, extremes → 0.5),
AUC (perfect / perfectly-wrong / all-tied / one-class-missing /
monotone in quality), profit-sim (no-edge skips, winning/losing
bets, ROI relation), and `run_eval` integration.

### #5 — Bayesian heuristic learning

`heuristics.confidence` was static: set once at import, never
updated. A heuristic that systematically failed in practice
continued to rank at its original confidence.

**Schema v4** (`_v4` in `library/_core/kb/migrate.py`):
- `heuristics.alpha`, `heuristics.beta` — Beta(α, β) posterior.
  Initialised to Beta(1, 1) (uniform prior). Successes → α += 1,
  failures → β += 1.
- New table `heuristic_applications(id, heuristic_id,
  predicted_direction, outcome, market_ticker, case_id, note,
  applied_at)` — an audit log of every application, outcome-
  tagged. Indexed on `heuristic_id` and `applied_at`.

**Module** `library/_core/analysis/heuristic_learn.py`:
- `posterior_p(α, β)` — posterior mean `α / (α+β)`.
- `posterior_ci(α, β, z=1.96)` — Wilson-score interval.
  Widens with small n (new heuristic = `[0, 1]`), tightens as
  evidence accumulates.
- `record_application(conn, hid, outcome, ...)` — atomic: audit
  insert + α/β update in one transaction.
- `top_confident(conn, limit, min_applications=3)` — ranks by
  **lower bound of CI** so a heuristic with 10 confirmations beats
  a heuristic with 1 lucky hit.
- `record_case_outcomes(conn, case_id, outcome)` — batch helper
  that updates every heuristic linked via the `case_principles`
  junction table when a `decision_case` resolves.
- `reset_posterior(conn, hid)` — admin tool for when a heuristic's
  text changes and its old history no longer applies.

**Tests (+19):** `test_heuristic_learn.py` covers schema defaults,
posterior math edges (uniform, zero-counts, CI widening), record
paths (success/failure/audit/invalid-outcome/missing-heuristic),
convergence after 20 successes, reset, top-confident ranking with
min-applications filter and limit, and `record_case_outcomes`
batch update via `case_principles`.

### Totals

**Tests:** 399 passing (+38 over v0.12: 16 probability + 7 signal + 8
trade_params + 9 anti_patterns + 19 eval_metrics + 19 heuristic_learn
− adjustments for renamed tests).

**LATEST_VERSION:** 4 (was 3). Migration is additive — existing DBs
get α/β columns with default 1.0 and the new applications table
empty.

**Next steps** (from the improvement backlog): #2 (Anthropic prompt
caching for cost savings), #3 (measure LLM-path calibration against
the rules baseline), #7 (Bayesian updates extended to speaker
stance), #9 (evidence-conflict detection).

**v0.12 — Kalshi client, orchestrate integration, embedding cache**

Three-step batch closing out v0.12: integration coverage for the
orchestrator, production-grade Kalshi API client, and a persistent
chunk-embedding cache that takes semantic retrieval from O(corpus)
to O(1) encode calls on warm queries.

### Step 3 — Persistent chunk-embedding cache

**Problem**: `hybrid_retrieve` was calling
`backend.encode([query, *candidate_texts])` on every query. With
a 400-chunk corpus and pool=40, that's 40 redundant model
invocations per query, dominating CPU cost for
sentence-transformers on commodity hardware.

**Fix**:
- Schema **v3** (`_v3` in `library/_core/kb/migrate.py`) adds
  `chunk_embeddings(chunk_id, model, dim, vec BLOB, created_at)`
  with PK `(chunk_id, model)` and `ON DELETE CASCADE` to
  `transcript_chunks`. `LATEST_VERSION` bumped 2 → 3.
- New **`library/_core/retrieve/embed_cache.py`** —
  `_pack/_unpack` (little-endian float32 via `array('f')`;
  byte-swap guard for big-endian hosts), `get_many`,
  `put_many` (ON CONFLICT upsert, rejects mixed dims in one
  batch), `count`, `clear`. All SQLite errors degrade to debug
  log + no-op; the cache cannot break retrieval.
- **`hybrid_retrieve`** refactored:
  - Reads cached vectors for candidate chunks keyed by
    `backend.model_name` (falls back to class name).
  - Encodes only `[query] + missing_texts` — warm queries pay
    O(1) (just the query).
  - Writes newly computed vectors back to cache.
  - Emits `retrieve.embed_cache_hit` / `retrieve.embed_cache_miss`
    counters so operators can spot cold corpora / misconfigured
    model names.

**Tests (+14):**
- `test_embed_cache.py` (11) — pack/unpack round-trip, 4-byte
  stride, dim-mismatch rejection; DB: put/get, partial hit,
  model-namespace isolation, upsert overwrite, empty-input
  safety, mixed-dim rejection, count/clear/count-by-model.
- `test_hybrid_embed_cache.py` (3) — `_CountingEmbed` records
  every input list:
  - Cold run encodes query + N candidates; second identical
    query encodes 1 item (just the query).
  - Adding a new chunk after warmup forces encode=2 (query +
    that one chunk), strictly less than the warm-cache count.
  - Switching `model_name` forces a cold re-encode.
- `test_kb_v2.py::test_schema_version_is_two` renamed to
  `test_schema_version_is_latest` — pins against
  `LATEST_VERSION` so future migrations don't need test
  updates here.

### Step 1 — orchestrate integration test

`tests/test_orchestrate_integration.py` (9 tests) seeds a small
transcript corpus (`_CORPUS`: Powell FOMC + Alice Trader Podcast)
and exercises `orchestrate()` end-to-end through the rules path:

- `TestHappyPath` (3) — asserts non-empty answer, non-zero
  confidence, and that cited chunks round-trip through KB.
- `TestKbBypass` (2) — `use_kb=False` short-circuits retrieval;
  still returns a structured envelope.
- `TestUrlPath` (1) — `orchestrate_url` smoke.
- `TestObservability` (2) — a `trace.start` / `trace.end` pair
  brackets every run; `orchestrate.calls` counter increments.
- `TestFailureIsolation` (1) — `_RaisingClient` proves an LLM
  layer crash does not take down the rules pipeline.

Uses `load_continuity()` (raw v4 buckets) not `read_continuity()`
(summary dict with `top_intents` etc.) — these two had collided
during Phase 5 and the test now pins the distinction.

### Step 2 — Kalshi client: cache + rate limit + retry + metrics

Three new modules under `library/_core/fetch/`:

**`rate_limit.py`** — `TokenBucket(capacity, refill_per_sec,
clock=time.monotonic, sleep=time.sleep)`. Continuous refill
capped at `capacity`. `try_acquire(n) -> bool`, `acquire(n)
-> float` (blocking, returns total wait; raises if n > capacity).
Injectable clock + sleep for deterministic tests.

**`http_cache.py`** — SQLite-backed JSON response cache with TTL.
Schema-less (`CREATE TABLE IF NOT EXISTS` on the caller's
connection). `get / put / purge_expired / clear`. Zero-TTL writes
are no-ops; empty keys are rejected. `ON CONFLICT DO UPDATE`
upsert. All sqlite errors log at debug and degrade to miss — the
cache must never break a live request.

**`kalshi.py`** (rewrote `_get`):
- Module-global `_LIMITER` sized from `KALSHI_RATE_CAPACITY` /
  `KALSHI_RATE_LIMIT` env (defaults 10 / 10 rps, the public
  ceiling). Tests monkeypatch it with a fast bucket.
- `_cache_key(path, params)` — `kalshi:{env}:GET:{path}?{sorted
  params}` so prod/demo never collide.
- `_cache_cm()` returns the `library.db.connect()` context
  manager (or None); callers do `with cm as conn: …`.
- Request flow: cache read → `kalshi.cache_hit` (+ trace, return)
  → `kalshi.cache_miss` → `_LIMITER.acquire(1)` (emits
  `kalshi.rate_limit_wait_ms` observation if it slept) →
  `with_retry(_do_request, max_attempts=KALSHI_MAX_ATTEMPTS=3)`
  → cache write (if TTL > 0) → `kalshi.call_ok` + trace.
- `_HTTPStatusError(status_code, url, body)` wraps
  `urllib.error.HTTPError` so `is_retryable` sees the code and
  retries 5xx / 429 / 408 / 425 while immediately failing 4xx.

**Step-2 tests (+26):**
- `test_rate_limit.py` (12) — init validation, drain/refill,
  blocking sleep accounting, capacity cap, zero-n free.
- `test_http_cache.py` (9) — hit/miss, TTL expiry, upsert,
  empty-key / zero-TTL rejection, purge_expired, clear.
- `test_kalshi_client.py` (5) — second call hits cache;
  `use_cache=False` bypass; 500 → retry → 200 (patching
  `library._core.llm.retry.time` to skip sleeps); 4xx not
  retried; rate-limit `acquire` called once per request.

### Totals

**Tests:** 310 passing (+40 over v0.11: +9 orchestrate + 26 Kalshi
stack + 11 embed_cache + 3 hybrid cache integration, minus one
test renamed but still passing).

**v0.11 — LLM cost tracking**

Two pieces that turn the v0.11 scaffold into something that can
hit a real API without melting.

### Step 1 — orchestrate integration test

`tests/test_orchestrate_integration.py` (9 tests) seeds a small
transcript corpus (`_CORPUS`: Powell FOMC + Alice Trader Podcast)
and exercises `orchestrate()` end-to-end through the rules path:

- `TestHappyPath` (3) — asserts non-empty answer, non-zero
  confidence, and that cited chunks round-trip through KB.
- `TestKbBypass` (2) — `use_kb=False` short-circuits retrieval;
  still returns a structured envelope.
- `TestUrlPath` (1) — `orchestrate_url` smoke.
- `TestObservability` (2) — a `trace.start` / `trace.end` pair
  brackets every run; `orchestrate.calls` counter increments.
- `TestFailureIsolation` (1) — `_RaisingClient` proves an LLM
  layer crash does not take down the rules pipeline.

Uses `load_continuity()` (raw v4 buckets) not `read_continuity()`
(summary dict with `top_intents` etc.) — these two had collided
during Phase 5 and the test now pins the distinction.

### Step 2 — Kalshi client: cache + rate limit + retry + metrics

Three new modules under `library/_core/fetch/`:

**`rate_limit.py`** — `TokenBucket(capacity, refill_per_sec,
clock=time.monotonic, sleep=time.sleep)`. Continuous refill
capped at `capacity`. `try_acquire(n) -> bool`, `acquire(n)
-> float` (blocking, returns total wait; raises if n > capacity).
Injectable clock + sleep for deterministic tests.

**`http_cache.py`** — SQLite-backed JSON response cache with TTL.
Schema-less (`CREATE TABLE IF NOT EXISTS` on the caller's
connection). `get / put / purge_expired / clear`. Zero-TTL writes
are no-ops; empty keys are rejected. `ON CONFLICT DO UPDATE`
upsert. All sqlite errors log at debug and degrade to miss — the
cache must never break a live request.

**`kalshi.py`** (rewrote `_get`):
- Module-global `_LIMITER` sized from `KALSHI_RATE_CAPACITY` /
  `KALSHI_RATE_LIMIT` env (defaults 10 / 10 rps, the public
  ceiling). Tests monkeypatch it with a fast bucket.
- `_cache_key(path, params)` — `kalshi:{env}:GET:{path}?{sorted
  params}` so prod/demo never collide.
- `_cache_cm()` returns the `library.db.connect()` context
  manager (or None); callers do `with cm as conn: …`.
- Request flow: cache read → `kalshi.cache_hit` (+ trace, return)
  → `kalshi.cache_miss` → `_LIMITER.acquire(1)` (emits
  `kalshi.rate_limit_wait_ms` observation if it slept) →
  `with_retry(_do_request, max_attempts=KALSHI_MAX_ATTEMPTS=3)`
  → cache write (if TTL > 0) → `kalshi.call_ok` + trace.
- `_HTTPStatusError(status_code, url, body)` wraps
  `urllib.error.HTTPError` so `is_retryable` sees the code and
  retries 5xx / 429 / 408 / 425 while immediately failing 4xx.

**Tests (+26):**
- `test_rate_limit.py` (12) — init validation, drain/refill,
  blocking sleep accounting, capacity cap, zero-n free.
- `test_http_cache.py` (9) — hit/miss, TTL expiry, upsert,
  empty-key / zero-TTL rejection, purge_expired, clear.
- `test_kalshi_client.py` (5) — second call hits cache;
  `use_cache=False` bypass; 500 → retry → 200 (patching
  `library._core.llm.retry.time` to skip sleeps); 4xx not
  retried; rate-limit `acquire` called once per request.

**Tests:** 296 passing (+26 over v0.11).

**v0.11 — LLM cost tracking**
Turns the token counters landed in v0.9 into actual dollars.

New `library/_core/llm/pricing.py`:
- `PRICING: dict[model, {input, output, cache_read, cache_write}]`
  in USD per million tokens. Ships with defaults for Haiku 4.5,
  Sonnet 4.5, and Opus 4; callers that need exact numbers can
  mutate the dict at import time.
- `cost_usd(model, input_tokens, output_tokens, cache_read_tokens,
  cache_create_tokens) -> float` — unknown models return 0.0
  (never raises), negative / None counts clamp to zero so a
  flaky SDK response can't blow up the metric.

`AnthropicClient.complete` computes per-call cost and records:
- `observe('llm.cost_usd', call_cost, tags={'model': model})` —
  per-call observation, so `metrics summary` gives p50/p95 cost
  per call.
- `incr('llm.cost_micro_usd', n=int(cost*1e6), tags={'model': ...})`
  — integer micro-USD counter for exact cumulative totals
  (floating-point drift over millions of calls is a real thing).
- `trace_event('llm.call', cost_usd=...)` so per-trace drill-down
  includes the dollar figure.

New CLI:
- `python -m library cost summary` — breakdown by model
  (tokens per category + cost) plus grand total from the live
  collector.
- `python -m library cost summary --history [--limit N]` —
  aggregate historical snapshots from `METRICS_LOG`.

The breakdown helper `_cost_breakdown_from_counters` is exported
from `library.__main__` and tested independently so the CLI stays
a thin shell around library code.

**Tests:** 261 passing (+13 new: test_llm_pricing covers known
model math, unknown → zero, negative / None clamping, cache
read/write asymmetry, Sonnet > Haiku relative pricing, and the
CLI breakdown helper bucketing tokens + cost by model).

Trace-log ordering fix: on Windows `time.time()` has ~16 ms
resolution, so two back-to-back `trace_event` calls can tie and a
sort key would shuffle them. `events_for_trace` now relies on the
JSONL append order (chronological by construction) instead of
sorting by `ts`.

**v0.10 — Trace IDs, LLM retry, calibration**
Three improvements on top of the Phase 7 observability base:

*Trace propagation (`library/_core/obs/trace.py`)*
- `contextvars.ContextVar` carries a `trace_id` through the whole
  request — no argument threading. `new_trace()`, `current_trace()`,
  `with_trace(id=None)` context manager.
- `trace_event(name, **fields)` appends one JSONL line to
  `TRACE_LOG = workspace/traces.jsonl`, tagged with the current
  trace id and wall-clock ts. Never raises.
- Hot paths instrumented: `intent.classify`, `llm.call`, `llm.retry`,
  `retrieve.hybrid`, `extract.chunk`, plus `trace.start` / `trace.end`
  emitted by `orchestrate` and `orchestrate_url`.
- Result dicts now carry `_trace_id` so a downstream UI can link
  back to the per-request event stream.
- New CLI: `python -m library trace list [--limit N]` summarises
  recent traces (id / duration / n_events / first-last names);
  `python -m library trace show <trace_id>` dumps the full event
  sequence for one request.

*LLM retry + circuit breaker (`library/_core/llm/retry.py`)*
- `is_retryable(exc)` — true for 408/425/429/5xx + SDK transient
  classes (`RateLimitError`, `APIConnectionError`, timeouts …).
  Matched by class name so this module stays anthropic-free.
- `with_retry(fn, max_attempts=3, base_delay=1.0, max_delay=30.0,
  sleep=time.sleep, on_retry=None)` — exponential backoff,
  injectable sleep for instant tests, non-retryable exceptions
  propagate immediately.
- `CircuitBreaker(threshold=3, cooldown_seconds=30)` —
  closed→open→half-open state machine, thread-safe, injectable
  clock. Only retryable failures count against the breaker; a
  programming bug won't trip it. Half-open probe: one success
  closes, one failure re-opens with a fresh cooldown.
- `AnthropicClient.complete` wraps the SDK call in both layers,
  emitting `llm.retry` / `llm.circuit_open` metrics and trace
  events so you can see rate-limiting in flight without attaching
  a debugger.

*Calibration in the eval harness*
- `_brier_score`, `_log_loss`, `_reliability_bins` (10 bins),
  `_ece` (expected calibration error) added to
  `library/_core/eval/harness.py`. Reports now carry a
  `calibration: {n, brier, log_loss, ece, bins: [...]}` block.
- Baseline rules-only on the 15-query gold set:
  `brier=0.2745, log_loss=0.7442, ece=0.2033`. The 0.3-bin has
  4 queries with 50% accuracy (so confidence≈0.3 is calibrated);
  the 0.45-bin has 7 queries at 71% (under-confident by ~25 pp);
  the 0.6-bin has 4 queries at 50% (over-confident by ~10 pp).
  These are the numbers the LLM path needs to beat.

**Tests:** 248 passing (+51 new: test_trace 13 — ContextVar
semantics, scoped/nested traces, per-thread isolation, event
log round-trip, junk-line handling, hook-integration smoke;
test_llm_retry 20 — is_retryable rules, backoff sequencing,
max-delay cap, on_retry callback, CircuitBreaker state machine,
non-retryable doesn't trip, success resets; test_calibration 18 —
Brier / log-loss edge cases, reliability-bin shape, ECE math,
run_eval integration).

**v0.9 — Observability (Phase 7)**
New `library/_core/obs/` package providing an in-process metrics
collector + JSONL event log. Zero new deps.

`MetricsCollector`:
- `incr(name, n=1, tags={})` — integer counters keyed by (name, tag-key).
- `observe(name, value, tags={})` — numeric observations kept sorted
  via `bisect.insort`, so `snapshot()` can hand back count / min /
  max / mean / p50 / p95 / p99 in O(1).
- `timed(name, tags={})` — context manager wrapping wall-time in ms.
- `snapshot()` — JSON-safe dict (counters + histogram summaries).
- Thread-safe (single `threading.Lock`).

Process-global singleton via `get_collector()` / `reset_collector()`.
JSONL persistence via `persist_event` (append-only) +
`load_events` / `summarize_events` for historical aggregation.

Hooks landed in four hot paths (each wrapped so a collector bug can
never break the caller):
- **intent classifier** — `intent.llm_attempt`,
  `intent.llm_latency_ms`, `intent.llm_success`, `intent.llm_failure`,
  `intent.rules_fallback`, tagged `intent.result`.
- **LLM client** — `llm.call_attempt`, `llm.latency_ms`,
  `llm.call_ok`, `llm.call_err`, plus token counters:
  `llm.input_tokens` / `llm.output_tokens` /
  `llm.cache_read_tokens` / `llm.cache_create_tokens` (all tagged
  by model, so Haiku vs Sonnet cost breakdown is trivial).
- **hybrid retrieve** — `retrieve.calls`, `retrieve.bm25_ms`,
  `retrieve.candidates` (histogram of pool size),
  `retrieve.returned`, `retrieve.tokens_used`, `retrieve.empty`.
- **extract pipeline** — `extract.calls`, `extract.skipped_no_llm`.

New CLI (`METRICS_LOG = workspace/metrics.jsonl`):
- `python -m library metrics summary` — dump current snapshot.
- `python -m library metrics summary --history [--limit N]` —
  current + aggregated historical snapshots.
- `python -m library metrics flush` — append snapshot to JSONL.
- `python -m library metrics reset` — clear the in-process store.

**Tests:** 197 passing (+21 new: test_obs_metrics covers helpers,
counter accumulation + tag separation, histogram percentiles,
`timed`, singleton identity + reset swap, JSONL persist / load /
junk-line skip / limit / aggregation, and hook integration for
intent classifier / extract pipeline / hybrid retrieve).

With Phase 7 complete the 8-phase refactor (0–7) is closed.

**v0.8 — Eval harness (Phase 6)**
New `library/_core/eval/harness.py` runs a gold-standard query set
against the live intent classifier (and, optionally, hybrid
retrieval), producing a machine-diffable metrics report:
- `intent_accuracy`, `route_accuracy` — exact-match vs gold labels.
- `ticker_prf`, `speaker_prf` — precision / recall / F1 with
  case-insensitive substring matching (handles normalization wobble
  like 'KXBTCD-25DEC' vs 'kxbtcd-25dec').
- `retrieval.recall_at_k` and `retrieval.mrr_at_k` — computed only
  for queries that specify `expected_doc_ids`; skipped otherwise so
  the eval is useful even before retrieval ground truth exists.

Gold set lives at `library/eval_queries.json` (15 seed entries
covering market analysis, speaker lookup, historical case,
heuristic lookup, breaking news, portfolio check, comparison,
general chat, and a Russian-language query).

CLI:
- `python -m library eval run` — runs the harness, writes the full
  report to `EVAL_REPORT`, prints the summary (strips per-query
  detail for readability).
- `python -m library eval run --verbose` — include per-query rows.
- `python -m library eval run --retrieve` — also compute
  recall@k / MRR@k.
- `python -m library eval run --limit N` — cost/debug cap.

Current rules-only baseline on the 15-query gold set:
- `intent_accuracy = 0.60`
- `route_accuracy = 0.40`
- `ticker_prf.f1 = 1.00`
- `speaker_prf.f1 = 0.86`

These are the numbers to beat once `ANTHROPIC_API_KEY` is set and
the LLM path kicks in.

**Tests:** 176 passing (+18 new: test_eval_harness covers PRF math,
recall@k / MRR@k, gold validation, perfect-run / wrong-intent /
spurious-entity / NullClient / limit / retrieval-skip paths,
case-insensitive entity matching, stable report shape).

**v0.7 — State consolidation (Phase 5)**
Continuity gets a v4 schema adding three new buckets, populated from
the intent-classifier output that Phase 4 landed in the runtime
frame:
- `intents`  — tally of classified intents (market_analysis,
  speaker_lookup, …)
- `speakers` — named speakers referenced across turns (Powell, Musk,
  Infantino, …)
- `tickers`  — Kalshi tickers referenced

Migrations cover v1→v4 and v3→v4. `_build_summary_dict` surfaces
`top_intents` / `top_speakers` / `top_tickers` alongside the existing
slices, so downstream consumers (prompt builder, dashboard) see
them without extra wiring.

`session_state` gains `last_intent` / `last_intent_confidence` /
`last_intent_source` / `last_speaker` / `last_ticker` fields.

`_orchestrate_inner` now calls `continuity.update(...)` on every
turn, carrying `intent / speaker / ticker` drawn from the frame. The
URL (speaker-event) path does the same with `intent='speaker_lookup'`
and the speaker pulled from the URL metadata. The continuity call is
wrapped in a best-effort try/except so a bug in state persistence
can never break the main analysis response.

Latent bug fix: `continuity.load()` used to do `dict(_DEFAULT)`
(shallow copy), so the bucket lists inside `_DEFAULT` leaked across
callers. Switched to `copy.deepcopy(_DEFAULT)` — the v4 tests
flushed this out immediately when each test saw another test's
data despite pointing at fresh stores.

**Tests:** 158 passing (+11 new: test_continuity_v4 covers default
shape, v1→v4 + v3→v4 migrations, intent/speaker/ticker bump
semantics, empty-value no-ops, mixed-bump integration, summary
slices, session_state intent fields).

**v0.6 — LLM extraction pipeline (Phase 4 part 2)**
New `library/_core/extract/` package:
- `prompts.py` — single static `EXTRACT_SYSTEM` prompt declaring a
  combined JSON schema for heuristics / decision_cases /
  pricing_signals. Designed for `cache_system=True`, so the whole
  system block is paid once and cache-hit on every subsequent chunk.
- `pipeline.py` — `extract_from_chunk(chunk, client)` (pure, no DB)
  plus `run_extraction(document_id=..., all=..., client=..., conn=...,
  chunk_limit=...)` that walks chunks and upserts into the structured
  KB with full provenance.

Idempotency contract:
- Heuristics de-duped on normalized text (lowercase, punctuation
  stripped, whitespace collapsed). On conflict: `recurring_count`
  bumps and a new `heuristic_evidence` row is added.
- `heuristic_evidence` de-dupes on
  `(heuristic_id, document_id, chunk_id, quote_text_prefix)`.
- `decision_cases` de-duped on
  `(document_id, chunk_id, sha1(normalized_setup))` — the sha prefix
  is stashed in the `tags` column so no schema change is needed.
- `pricing_signals` already UNIQUE on `signal_name`; on conflict
  keeps the higher confidence.

LLM-only: when `default_client()` returns `NullClient`,
`run_extraction` short-circuits with `status='skipped_no_llm'`. The
structured KB is already populated from the PMT dump; extraction is
purely an enrichment path.

New CLI:
- `python -m library extract run <doc_id>` — one document
- `python -m library extract run --all [--chunk-limit N]` — every
  ingested document

**Tests:** 147 passing (+15 new: test_extract covers empty-input +
NullClient short-circuits, shape coercion, exception-safety,
normalizers, end-to-end row creation with provenance, idempotent
re-run, signal-confidence upgrade, all=True iteration, chunk_limit).

**v0.5 — LLM intent classifier + pluggable client (Phase 4 part 1)**
New `library/_core/llm/` package:
- `client.py` — `LLMClient` Protocol, `NullClient` default, `AnthropicClient`
  (lazy-imports `anthropic`, supports prompt caching via
  `cache_control: {"type": "ephemeral"}` on the system block, parses
  `input_tokens` / `output_tokens` / `cache_read_input_tokens` /
  `cache_creation_input_tokens` into `LLMResponse`). `default_client()`
  degrades to `NullClient` if either the SDK or `ANTHROPIC_API_KEY`
  is absent — never raises.
- `_parse_json_text` — best-effort JSON extraction (direct, fenced
  block, balanced-brace scan), arrays rejected.

New `library/_core/intent/classifier.py`:
- `classify_intent(query, client=None) -> IntentResult` with fields
  `intent / route / confidence / source / entities / raw`.
- LLM-preferred (static system prompt, cached) with rules fallback.
  Invalid intents or raising clients silently fall back to rules.
- `_ROUTE_TO_INTENT` repair: unknown LLM route → mapped from intent.
- Default model: `claude-haiku-4-5`.

`runtime/frame.select_frame` now surfaces `intent`,
`intent_confidence`, `intent_source`, `entities`, `speaker`. Speaker
entity always forces `needs_transcript=True`. Non-breaking: when the
classifier is a `NullClient`, frame behaviour matches v0.4.

**Tests:** 132 passing (+34 new: test_llm_client 13, test_intent_classifier 18, test_frame_integration 3).

**v0.4 — Hybrid retrieval live (Phase 3 of refactor)**
New `library/_core/retrieve/` package:
- `hybrid.py` — BM25 (FTS5 rank) + optional semantic embeddings +
  Reciprocal Rank Fusion + MMR diversity rerank + explicit token
  budget. Returns `RetrievalHit` objects that carry every intermediate
  score (`score_bm25`, `score_semantic`, `score_final`) for
  observability.
- `embed.py` — pluggable `EmbedBackend` protocol. `NullEmbed` is the
  dep-free default (lexical-only); `SentenceTransformerEmbed` enables
  semantic scoring when `sentence-transformers` is installed.
- `retrieve_bundle(query)` also joins heuristics + decision_cases
  anchored to the matched documents, so the caller gets a coherent
  chunks + structured-knowledge bundle in one call.

`runtime/retrieve.py` now delegates transcript search to
`hybrid_retrieve`, with a token budget governed by the new
`transcript_token_budget` threshold.

**v0.3 — Chunker v2 + ingest pipeline rewrite (Phase 2 of refactor)**
Structure-aware, token-based chunker (`library/_core/ingest/chunker.py`)
using tiktoken cl100k_base. Speaker turns, SRT/VTT timestamps, and
stage directions (`[Music]`, `[Applause]` …) are detected and handled.
Every chunk carries char offsets, token count, speaker turn id, and
sha1 for dedup. Ingest pipeline (`library/_core/ingest/transcript.py`)
rewritten to populate all v2 columns, with idempotent doc upsert and
incremental per-doc FTS sync via `library/_core/kb/fts_sync.py`. New
CLI: `python -m library ingest rechunk <doc_id|--all>` replays the
new chunker over previously indexed documents.

Fixed a subtle FTS5 external-content corruption bug: raw `DELETE FROM
fts WHERE rowid = X` on a never-indexed rowid produces `database disk
image is malformed`; fix guards DELETE via the `_docsize` shadow table.

**v0.2 — Structured KB restored (Phase 1)**
KB v2 schema live. Historical PMT architecture dump (109 transcripts,
4498 chunks, 23 heuristics, 27 decision cases, 6 speaker profiles,
12 pricing signals, 8 phase-logic rows) imported into
`library/mentions_data.db`. Structured query layer (heuristics,
decision_cases, speaker_profile, pricing_signals, phase_logic,
case_context, heuristic_evidence) in place.

**Tests:** 98 passing (chunker, ingest, kb_v2, hybrid_retrieve, smoke).

Phase 7 (observability / structured logs / metrics) pending.

### v0.4 addendum — base/pack split
Local runtime lives under `mentions_core`, while `openclaw` is
reserved for the upstream Gateway/transport layer. Legacy
PMT/skill dump moved to `legacy/pmt-architecture-dump/`. `library/`
now acts as a compatibility façade.

## Evolution
This project evolved from the `mentions` skill into:
- reusable `OpenClaw base`
- pluggable `Mentions` agent pack
- capability-layer split: transcripts / wording / news_context / analysis

## Architecture Notes
- Base layer now lives in `mentions_core/`
- Mentions runtime and capabilities now live in `agents/mentions/`
- Legacy PMT/skill architecture moved to `legacy/pmt-architecture-dump/`
- SQLite DB now lives under `workspace/mentions/`
- `library/` now acts as a compatibility facade instead of a second runtime
- Package-level legacy imports are covered by tests
- `gateway/` now holds local config templates for the official OpenClaw Gateway

## TODO
- [x] **Phase 2:** token/structure-aware chunking (tiktoken, speaker turns, timestamps) ✅ v0.3
- [x] **Phase 3:** hybrid retrieval (FTS + embeddings + MMR rerank + explicit token budget) ✅ v0.4
- [ ] **Phase 4:** LLM intent classifier + extraction pipeline (rebuild heuristics/cases from new corpus)
- [ ] **Phase 5:** consolidate session state (workspace JSON → DB), speaker normalization, news
- [ ] **Phase 6:** golden eval set + calibration tracking (Brier, log loss)
- [x] **Phase 7:** observability (metrics collector + JSONL event log + hooks) ✅ v0.9
- [ ] Connect Kalshi API client (requires `KALSHI_API_KEY`)
- [ ] Configure cron schedule for autonomous market monitoring
- [ ] Build dashboard output pipeline
- [ ] Seed initial transcript corpus (Fed speeches, relevant earnings calls)
- [ ] Expand test coverage around autonomous scan and capability wrappers
- [ ] Add embedding support for transcript semantic search
- [ ] Wire Telegram bot binding (separate from main assistant)
- [ ] Decide when to formally deprecate `python -m library ...`
- [ ] Wire the official OpenClaw Gateway to this workspace and validate Telegram pairing end-to-end
