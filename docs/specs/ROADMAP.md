# ROADMAP.md — Mentions Refactoring & Enhancement Plan

> Historical note: parts of this roadmap were written before the final
> architecture cleanup. When old paths appear below, interpret
> them as historical placeholders for the current canonical owners under
> `mentions_core/`, `mentions_domain/`, and `agents/mentions/`.

> Working from v0.14.7 baseline (635 tests green, schema v10, WAL+FTS
> triggers, canonical speaker attribution, recency retrieval,
> resolution-latency, section tagging).
>
> Each item has: **What / Why / How / Risk / Tests / Depends on**.
> Sized T-shirt style (S ≤ half-day, M ≤ 1 day, L ≤ 2–3 days).
> Priorities: **P0** ship next / **P1** within 2 versions / **P2** backlog.

---

## Executive summary

The v0.14.x line closed three loops: *retrieval slicing* (regime, recency,
canonical speakers), *DB hygiene* (WAL, FTS triggers, migrations to v10),
*ingest enrichment* (section tags, canonical attribution). The remaining
gaps cluster into four themes:

1. **Posterior richness** — slice Beta(α,β) by more axes (section,
   latency bucket) and decay priors over time.
2. **Retrieval quality** — cross-encoder rerank, answer-focused
   reranking for Q&A, duplicate suppression.
3. **Operational hardening** — typed public API, error taxonomy,
   structured logging, config centralisation, migration dry-run.
4. **Developer ergonomics** — faster tests, typed DB layer, Ruff+mypy
   in CI, docs generation.

No item on this list is a rewrite; everything is additive or
narrowly-scoped refactor. The schema side is intentionally quiet
(two additive columns at most) to avoid migration thrash.

---

## Theme 1 — Posterior & evaluation depth

### P1-1 — Latency-aware posterior slices  `[M, P0]`

**What.** Split the Beta posterior on a heuristic by resolution horizon
(`≤3d`, `≤14d`, `>14d`) using `decision_cases.outcome_resolved_at`
(shipped in D1). Expose `posterior(h, horizon='short'|'medium'|'long')`.

**Why.** A heuristic with mean 0.62 overall may actually be 0.71 on
sub-week resolutions and 0.48 on longer ones. Kalshi edges live in
the short tail; averaging across horizons hides the tradeable signal.

**How.** New evaluation module for posterior-by-horizon slices. Join
`case_principles → decision_cases` filtered by
`julianday(outcome_resolved_at) - julianday(created_at)` bucket. Reuse
existing Beta accumulator helpers. Optional sibling
`horizon_mix(h)` returning the `(short%, medium%, long%)` distribution
so consumers can detect coverage skew.

**Risk.** Sparse buckets — need `n < 5` "insufficient evidence" guard
to avoid posting misleading posteriors on 1–2 cases. Consumers must
consult the guard, not the mean.

**Tests.** `test_posterior_by_horizon.py` — bucket boundaries, sparse
guard, unresolved cases excluded, cross-check aggregate = union of
buckets.

**Depends on.** D1 (done).

---

### P1-2 — Section-aware posterior slices  `[S, P0]`

**What.** Pipe `transcript_chunks.section` into `record_application` so
a heuristic can carry separate posteriors for `prepared` vs `qa`.
Currently `regime` is the only axis; `section` is captured at ingest
but never read.

**Why.** Q&A answers are reactive, unrehearsed, and empirically where
FOMC-style surprises leak. A "hawkish-pivot" heuristic that fires 0.58
on prepared remarks may fire 0.78 on Q&A — that's a 20-point edge
being averaged away.

**How.** Extend `record_application(section=…)` kwarg, defaulting to
inferred value (look up the source chunk's section). Add optional
`section` column to the applications table (additive, nullable). No
migration risk — NULL means "unspecified" and behaves like today.

**Risk.** Minor — writers that don't know their source section leave
NULL, which matches current behaviour.

**Tests.** `test_section_posterior.py` — round-trip write/read,
backfill behaviour for NULL, interaction with `regime` slice.

**Depends on.** T2 (done).

---

### P1-3 — Time-decayed priors  `[M, P1]`

**What.** In addition to recency boost on retrieval (T4 — done), decay
the *evidence itself* when computing posteriors: a case from 3 years
ago counts for less than a case from last month. Exponential with
half-life (config, default 730d).

**Why.** Macro regimes shift. A heuristic that was 0.70 during
2020 QE is not necessarily 0.70 today. A decayed posterior stays
honest to the current regime without discarding history entirely.

**How.** New `posterior_decayed(h, *, half_life_days)` which walks
case rows, weights each by `exp(-ln(2) × age_days / half_life)`, and
accumulates fractional α/β. Keep the undecayed version in place —
many consumers (audit, backtesting) still want raw counts.

**Risk.** Numerical — fractional Beta with very small weights drifts
toward prior. Clamp weight floor at 0.05. Add a `min_effective_n`
guard.

**Tests.** `test_posterior_decayed.py` — identity under half_life=∞,
monotonic-decreasing weight, floor behaviour, prior dominance when
all evidence ancient.

**Depends on.** None.

---

### P1-4 — Per-speaker reliability priors  `[S, P1]`

**What.** `speaker_profiles` already exists; the reliability layer
currently treats every speaker symmetrically. Add a per-profile
`reliability_prior` column (α₀, β₀) so senior / track-record speakers
start closer to their empirical mean instead of the universal 1/1.

**Why.** Cold-start for a new Powell-tier speaker is noisy. Seeding
their prior from a small editorial curation (e.g. α=8 β=4 for known
reliable voices) cuts warm-up from ~50 cases to ~10.

**How.** Schema v11: add
`speaker_profiles.reliability_alpha`, `.reliability_beta`
(REAL, defaults 1.0). `apply_weights` reads these before falling
through to the global prior.

**Risk.** Editorial hazard — fake priors bias the system. Mitigate:
document only, never programmatically set; add `reliability_source`
TEXT column recording "manual"/"inherited" for auditability.

**Tests.** `test_reliability_priors.py`.

**Depends on.** T1 (done).

---

## Theme 2 — Retrieval quality

### P2-1 — Cross-encoder rerank (T3 from v0.14.6 plan)  `[L, P0]`

**What.** After BM25+FTS → RRF → MMR, run the top-K (K=20) through a
cross-encoder reranker (e.g. `bge-reranker-base`, or OpenAI's
`rerank-english-v3` if permitted). Replace `score_final` with the
reranker score (normalised) blended 0.7×reranker + 0.3×hybrid.

**Why.** BM25+dense RRF gives ~good recall, but the top-3 ordering
still hits the precision ceiling of bag-of-words+ANN. Cross-encoders
understand "does this passage answer this query" in a way lexical
overlap cannot.

**How.** New retrieval rerank module with a pluggable
backend (local ONNX via `sentence-transformers`, or HTTP). Add
`hybrid_retrieve(rerank=True|False)` kwarg, default False until tuned.
Cache reranker scores keyed on `(query_hash, chunk_text_sha1)` in a new
`retrieval_rerank_cache` table (schema v12, auto-expire 30d).

**Risk.** Latency — batch of 20 is ~200ms on CPU, ~20ms on GPU. Mark
as opt-in. Model weights — local models add a dependency and RAM
footprint (≈300MB). Offer HTTP backend as escape hatch for low-RAM
environments.

**Tests.** `test_rerank.py` — mock backend, score shape, cache
round-trip, blend formula, graceful degradation when backend fails
(fall back to hybrid score).

**Depends on.** Hybrid retrieval (exists).

---

### P2-2 — Duplicate / near-duplicate suppression  `[M, P1]`

**What.** Same passage appearing in both transcript and press-kit
PDF pollutes top-K. Compute minhash signatures per chunk at ingest;
in retrieval, collapse hits whose signatures have Jaccard ≥ 0.85
onto the highest-scored representative.

**Why.** Currently the ranker happily returns 3 near-duplicate chunks
that crowd out diverse context. MMR helps but uses embedding distance,
which doesn't catch literal copy-paste between docs.

**How.** Add `transcript_chunks.minhash BLOB` (schema v12). At ingest
compute 64-bit minhash over shingles. In retrieval, post-process the
top-50 with a Jaccard-based dedup pass before MMR.

**Risk.** Minhash on short chunks is noisy; only apply dedup when
`token_count ≥ 40`.

**Tests.** `test_dedup.py` — exact duplicate collapse, near-dup
threshold, short-chunk bypass.

**Depends on.** None.

---

### P2-3 — Q&A-answer extraction  `[M, P1]`

**What.** When `section='qa'`, a chunk often contains *both* the
reporter's question and the speaker's answer. For downstream
reliability scoring we want the *answer* text specifically (the
speaker said X, not "the reporter asked Y").

**How.** Rule-based split on `Q:` / `A:` markers, or speaker turn
changes inside a chunk. Store as sibling rows
`transcript_chunks.answer_text_offset_start/end` (schema v13) —
nullable; when set, downstream analysis uses that span instead of
the full chunk.

**Risk.** Transcripts vary wildly in Q/A marker convention. Start
conservative — only extract when markers are unambiguous; leave NULL
otherwise so consumers gracefully fall through to full-chunk text.

**Tests.** `test_qa_extract.py` — Q:/A: markers, speaker turn
switch, no-marker fallback.

**Depends on.** T2 (done).

---

### P2-4 — Query expansion via speaker alias graph  `[S, P2]`

**What.** Query "Powell rates" should implicitly expand to include
"Jerome Powell", "Chair Powell", "J. Powell" via `speaker_profiles.aliases`.

**How.** Pre-query pass: tokenize query, detect speaker mentions,
expand with canonical + aliases as OR-clauses in the BM25 query.

**Risk.** Over-expansion recalls junk; cap to top-1 canonical per
detected token.

**Tests.** `test_query_expansion.py`.

**Depends on.** T1 (done).

---

## Theme 3 — Operational hardening

### P3-1 — Typed public API boundary  `[M, P0]`

**What.** Introduce a single typed public import surface for
external callers (CLI, future HTTP, notebooks). Re-export the
curated set of functions with full type hints and keep deep internal
modules out of consumer code.

**Why.** Right now callers can still reach too far into internal
retrieval and orchestration modules. When internals move, those
callers break. A stable façade lets internals evolve freely.

**How.** List the ~15 functions that are de-facto public
(`synthesize`, `register_transcript`, `hybrid_retrieve`,
`record_application`, `posterior`, `detect_regime`, …), re-export,
add type aliases for core returns (`RetrievalHit`, `SynthesisResult`).

**Risk.** Scope creep — resist the urge to "also refactor this one
thing while we're here".

**Tests.** `test_public_api.py` — import surface stable, every
exported name has a docstring.

**Depends on.** None.

---

### P3-2 — Error taxonomy  `[S, P1]`

**What.** Replace `{'status': 'error', 'error': str}` dicts with
typed exceptions (`IngestError`, `RetrievalError`, `SchemaError`,
`ConfigError`). Public API wrappers catch at the boundary and
return dicts for callers that expect today's shape.

**Why.** `return {'error': '...'}` hides stack traces and makes
tests assert on string content. Exceptions are greppable, typed,
and cleanly testable.

**How.** New canonical error module with the hierarchy. Migrate one
module per PR (ingest first — most error paths).

**Risk.** Old CLI commands expect dict shape. Boundary wrappers
preserve it.

**Tests.** Update existing tests site-by-site.

**Depends on.** P3-1.

---

### P3-3 — Structured logging  `[S, P1]`

**What.** Swap `log.info('foo %s %d', x, y)` for `log.info('foo', extra={'x': x, 'y': y})`
or a lightweight JSON formatter so log lines are grep+parse friendly.

**Why.** Current logs are human-readable but not machine-queryable.
When the synthesis pipeline runs at scale we'll want to slice by
regime, document, latency.

**How.** Add an optional `MENTIONS_LOG_JSON=1` env switch. Keep
default human-readable for interactive use.

**Risk.** Low.

**Tests.** `test_logging_shape.py`.

**Depends on.** None.

---

### P3-4 — Config centralisation  `[S, P1]`

**What.** Settings are currently scattered across config modules and
call sites; magic numbers (half-life 365d, MMR λ=0.5, RRF k=60)
still live inline. Consolidate into a single settings object
(dataclass or Pydantic) with env overrides.

**Why.** Tuning half-life currently requires grep+edit across 3 files.
A single Settings object means "change default, run A/B, commit".

**How.** `@dataclass(frozen=True) class Settings` with defaults;
`get_settings()` reads env once and memoises. Gradual migration —
start with new modules, sweep old ones opportunistically.

**Risk.** None if additive.

**Tests.** `test_settings.py` — env override, default values,
immutability.

**Depends on.** None.

---

### P3-5 — Migration dry-run + down-migrations  `[M, P1]`

**What.** `migrate.py` is forward-only. Add `migrate.dry_run()` that
prints what *would* run, and `migrate.down_to(version)` for each
`_vN` where rollback is safe (additive columns → `ALTER TABLE DROP`;
index changes → `DROP INDEX`). Non-reversible steps (data
transforms) explicitly raise.

**Why.** v0.14.x added 4 columns across 4 migrations. A botched
release needs a rollback path, or operators will stay on the old
version forever.

**How.** Parallel `_v8_down`, `_v9_down`, … Declare reversibility
via a module-level list. `down_to` walks backwards applying them.

**Risk.** Reversibility discipline — every new `_vN` must ship with
`_vN_down` or an explicit "irreversible" marker. Enforce via a test
that iterates the migration list and asserts each has one or the
other.

**Tests.** `test_migration_roundtrip.py` — `up()` → `down_to(prev)`
leaves schema byte-identical (modulo column order, which SQLite
doesn't preserve anyway).

**Depends on.** None.

---

### P3-6 — Integrity check job  `[S, P2]`

**What.** A weekly-cron-friendly integrity check that asserts: every `transcript_chunks.document_id` resolves;
every `case_principles.heuristic_id` resolves; FTS row count matches
chunk row count; `outcome IS NULL ↔ outcome_resolved_at IS NULL`;
no orphaned `applications` rows.

**Why.** WAL + FTS triggers reduce drift risk but don't eliminate
it — admin SQL or future bugs can still leave inconsistencies.
Periodic check + alert keeps the DB honest.

**Tests.** `test_integrity.py` — each assertion catches a
deliberately corrupted row.

**Depends on.** None.

---

## Theme 4 — Developer ergonomics

### P4-1 — Ruff + mypy + pre-commit  `[S, P0]`

**What.** `pyproject.toml` with Ruff (lint+format) and mypy (strict
on the public API boundary, gradual elsewhere). Pre-commit hook
runs both on staged files.

**Why.** Catches the 80% of bugs type-hints can catch. Consistent
formatting ends bikeshedding.

**How.** Start with `mypy --strict` only on the public API boundary
and canonical error module. Relax `--ignore-missing-imports`
for deep internal modules and tighten one module per PR.

**Risk.** Initial cleanup pass creates noise; contain it to one PR.

**Tests.** CI green.

**Depends on.** P3-1 (api surface exists).

---

### P4-2 — Parallel test execution  `[S, P1]`

**What.** `pytest-xdist` with `-n auto`. WAL already makes this safe
across separate `tmp_db` fixtures.

**Why.** 635 tests in 18s is fine now but will degrade as we layer
P1/P2 items. Parallel typically buys 2–3× on 8-core.

**Risk.** Any global-state test (e.g. module-level caches in
`speaker_canonicalize`) leaks across workers. Audit once, add
`pytest.fixture(autouse=True)` resetters where needed.

**Tests.** Suite green with `-n auto`.

**Depends on.** None.

---

### P4-3 — Fixture rationalisation  `[M, P2]`

**What.** Consolidate `tmp_db`, `fresh_conn`, `seeded_db` variants
into a single factory in `conftest.py` with explicit kwargs for
"what data does this test need". Current fixtures drifted.

**Why.** Test authors copy the nearest existing fixture, accumulating
divergence. A factory with named preset bundles (`empty`,
`with_transcripts`, `with_cases`, `full`) means one place to fix
when schema changes.

**Tests.** Migration of existing tests to the factory is the test.

**Depends on.** None.

---

### P4-4 — Docstrings → generated reference docs  `[S, P2]`

**What.** Wire `mkdocs` + `mkdocstrings` to auto-generate a
`/docs/reference/` from the public API docstrings. Commit built
HTML to `docs/` or publish to GH Pages.

**Why.** We already write long, essay-style docstrings (v0.14.x
modules are exemplary). Parsing them once into browsable docs costs
~1 hour and unlocks onboarding / code review.

**Depends on.** P3-1.

---

### P4-5 — Bench harness  `[M, P2]`

**What.** `bench/` directory with scripted scenarios: ingest 100
docs, run 50 synthesis passes, measure p50/p95 latency per stage.
Regression-detect in CI (fail if any stage degrades >20% vs main).

**Why.** Perf drift is silent. Rerank (P2-1) specifically will
introduce a big latency delta — we want to see it quantified.

**How.** `pytest-benchmark` or a homegrown harness writing to
`bench/results.jsonl`. Compare against `origin/main` in CI.

**Depends on.** P2-1 (for the measurement target).

---

## Theme 5 — Future-facing (speculative)

### P5-1 — Embedding model versioning  `[M, P2]`

Currently embeddings are computed once at ingest with whatever model
was loaded. No record of *which* model. When we switch models, old
vectors silently mix with new ones.

Add `transcript_chunks.embedding_model TEXT` (schema v14). Retrieval
filters on a target model; a background reindexer upgrades rows
lazily.

### P5-2 — Multi-language support  `[L, P2]`

`meta['language']` is detected and stored but unused. If we ingest
non-English transcripts (ECB, BOJ), retrieval should route to a
language-appropriate BM25 analyser and a multilingual embedding
model. Non-trivial; parked until a concrete multi-language corpus
exists.

### P5-3 — Streaming ingest  `[L, P2]`

Live transcription feed (e.g. Fed broadcast) → per-chunk commits with
incremental FTS + posterior updates. Current batch model is fine for
historicals; streaming is a product question, not an infrastructure
one, so parked.

### P5-4 — Counterfactual backtesting harness  `[L, P2]`

"If we had held heuristic X in Jan 2024, what would its posterior
have been?" requires replaying `record_application` deterministically
from the historical record. Would benefit from P1-3 (decayed priors)
and P3-5 (down-migrations). Large; staged later.

---

## Ordering — proposed next 3 versions

**v0.14.8 — Evaluation depth (P1-1, P1-2, P3-4)**
Ships: latency-aware posteriors + section-aware posteriors +
Settings dataclass. All additive, no new schema except reusing
existing columns. Estimated 2–3 days.

**v0.14.9 — Retrieval quality (P2-1, P3-1)**
Ships: cross-encoder rerank + typed public API boundary. Schema v12
for rerank cache. Estimated 3–4 days.

**v0.15.0 — Hardening (P3-2, P3-5, P4-1, P4-2)**
Ships: error taxonomy + migration rollback + Ruff/mypy + pytest-xdist.
No new features; explicit "hardening" version. Estimated 2 days.

After v0.15 the list reorders based on what the retrieval eval
surfaces as the next weakest link.

---

## Non-goals (explicit)

* **No LLM calls in ingest.** Section tagging, canonicalization,
  regime — all rule-based. LLMs stay in synthesis only.
* **No external DB.** SQLite + WAL is sufficient for the foreseeable
  corpus size (<10M chunks). No Postgres port.
* **No framework adoption.** FastAPI / Celery / Pydantic-first —
  resist until concrete demand. Current plain-Python-+-SQLite stack
  is readable and portable.
* **No speculative embedding upgrades.** Wait for a measured
  retrieval regression before swapping embedding models.

---

## How to use this document

* Pick the next **P0** item, read the *How / Risk / Tests* block, open a
  branch named for it (e.g. `p1-1-latency-posterior`).
* If scope creeps beyond the *What* paragraph, stop and update this file
  first — roadmap drift is the tell that you're building something else.
* When shipped, move the item into `NOTES.md` with the actual
  line-counts / test-counts / perf deltas. Delete it from here.
