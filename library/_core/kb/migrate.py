"""Schema migrations for mentions_data.db.

Versioned, idempotent migrations applied in order.
Current latest version: 2

Migration policy
----------------
* Each _vN() function is idempotent — safe to re-run against a partially
  applied DB (CREATE TABLE IF NOT EXISTS, ALTER on ignore-if-exists pattern).
* PRAGMA user_version is bumped at the end of each _vN as the authoritative
  marker.
* Never edit a past _vN once shipped. Add _vN+1 instead.
"""
from __future__ import annotations

import logging

log = logging.getLogger('mentions')

LATEST_VERSION = 10


def get_schema_version(conn) -> int:
    """Return the current schema version stored in user_version pragma."""
    row = conn.execute('PRAGMA user_version').fetchone()
    return row[0] if row else 0


def migrate_up(conn) -> None:
    """Apply all pending migrations up to LATEST_VERSION."""
    current = get_schema_version(conn)
    if current < 1:
        _v1(conn)
    if current < 2:
        _v2(conn)
    if current < 3:
        _v3(conn)
    if current < 4:
        _v4(conn)
    if current < 5:
        _v5(conn)
    if current < 6:
        _v6(conn)
    if current < 7:
        _v7(conn)
    if current < 8:
        _v8(conn)
    if current < 9:
        _v9(conn)
    if current < 10:
        _v10(conn)
    log.info('Schema migrated to version %d', LATEST_VERSION)


def _v1(conn) -> None:
    """Initial schema: markets, history, analysis cache, news cache, transcripts."""
    cur = conn.cursor()

    cur.executescript('''
        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL,
            title TEXT,
            category TEXT,
            status TEXT,
            yes_price REAL,
            no_price REAL,
            volume REAL,
            open_interest REAL,
            close_time TEXT,
            fetched_at TEXT
        );

        CREATE TABLE IF NOT EXISTS market_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            yes_price REAL,
            volume REAL,
            timestamp TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_market_history_ticker
            ON market_history(ticker);

        CREATE TABLE IF NOT EXISTS analysis_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            ticker TEXT,
            frame TEXT,
            reasoning TEXT,
            conclusion TEXT,
            confidence TEXT,
            sources TEXT,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_cache_ticker
            ON analysis_cache(ticker);

        CREATE TABLE IF NOT EXISTS news_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT,
            summary TEXT,
            source TEXT,
            published_at TEXT,
            fetched_at TEXT,
            category TEXT
        );

        CREATE TABLE IF NOT EXISTS transcript_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker TEXT,
            event TEXT,
            event_date TEXT,
            source_file TEXT UNIQUE,
            status TEXT DEFAULT 'indexed',
            added_at TEXT
        );

        CREATE TABLE IF NOT EXISTS transcript_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER REFERENCES transcript_documents(id)
                ON DELETE CASCADE,
            chunk_index INTEGER,
            text TEXT,
            speaker TEXT,
            section TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS transcript_chunks_fts
            USING fts5(
                text,
                speaker,
                section,
                content='transcript_chunks',
                content_rowid='id'
            );

        PRAGMA user_version = 1;
    ''')
    log.info('Schema v1 applied')


# ── Column existence helper ────────────────────────────────────────────────

def _has_column(conn, table: str, column: str) -> bool:
    rows = conn.execute(f'PRAGMA table_info({table})').fetchall()
    return any(r[1] == column for r in rows)


def _add_column_if_missing(conn, table: str, column: str, ddl_type: str) -> None:
    """ALTER TABLE ADD COLUMN, no-op if the column already exists."""
    if not _has_column(conn, table, column):
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}')


# ── v2: structured knowledge layer + richer chunk/document metadata ────────

def _v2(conn) -> None:
    """Structured knowledge layer imported from the PMT architecture dump.

    Adds: speaker_profiles, heuristics + evidence, decision_cases,
    pricing_signals, phase_logic, crowd_mistakes, anti_patterns,
    market_archetypes, sizing_lessons, execution_patterns, dispute_patterns,
    live_trading_tells, event_formats, plus case_* join tables.

    Extends transcript_documents with external_id/summary/sha256/language/
    token_count, and transcript_chunks with char_start/char_end/token_count/
    timestamps/speaker_turn_id/text_sha1.
    """
    cur = conn.cursor()

    # ── Extend existing tables (idempotent per-column) ─────────────────────
    for col, ddl in (
        ('external_id',    'TEXT'),
        ('source_type',    "TEXT DEFAULT 'file'"),
        ('language',       "TEXT DEFAULT 'en'"),
        ('sha256',         'TEXT'),
        ('duration_sec',   'INTEGER'),
        ('summary',        'TEXT'),
        ('char_count',     'INTEGER'),
        ('token_count',    'INTEGER'),
        ('title',          'TEXT'),
        ('source_url',     'TEXT'),
        ('channel',        'TEXT'),
    ):
        _add_column_if_missing(conn, 'transcript_documents', col, ddl)

    for col, ddl in (
        ('char_start',       'INTEGER'),
        ('char_end',         'INTEGER'),
        ('token_count',      'INTEGER'),
        ('timestamp_start',  'REAL'),
        ('timestamp_end',    'REAL'),
        ('speaker_turn_id',  'INTEGER'),
        ('text_sha1',        'TEXT'),
    ):
        _add_column_if_missing(conn, 'transcript_chunks', col, ddl)

    cur.executescript('''
        CREATE INDEX IF NOT EXISTS idx_transcript_documents_external_id
            ON transcript_documents(external_id);
        CREATE INDEX IF NOT EXISTS idx_transcript_documents_sha256
            ON transcript_documents(sha256);
        CREATE INDEX IF NOT EXISTS idx_transcript_chunks_document_id
            ON transcript_chunks(document_id);
        CREATE INDEX IF NOT EXISTS idx_transcript_chunks_text_sha1
            ON transcript_chunks(text_sha1);
        CREATE INDEX IF NOT EXISTS idx_transcript_chunks_speaker
            ON transcript_chunks(speaker);
    ''')

    # ── Speaker profiles (canonical lookup for names) ──────────────────────
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS speaker_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL UNIQUE,
            speaker_type TEXT,
            aliases TEXT,              -- JSON array of alternate names
            description TEXT,
            behavior_style TEXT,
            favored_topics TEXT,
            avoid_topics TEXT,
            qna_style TEXT,
            adaptation_notes TEXT,
            domain TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_speaker_profiles_canonical
            ON speaker_profiles(canonical_name);

        CREATE TABLE IF NOT EXISTS event_formats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            format_name TEXT NOT NULL UNIQUE,
            domain TEXT,
            description TEXT,
            has_prepared_remarks INTEGER,
            has_qna INTEGER,
            qna_probability TEXT,
            usual_market_effects TEXT,
            format_risk_notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS market_archetypes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            archetype_type TEXT,
            description TEXT,
            pricing_drivers TEXT,
            common_edges TEXT,
            common_traps TEXT,
            liquidity_profile TEXT,
            repeatability TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS heuristics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            heuristic_text TEXT NOT NULL,
            heuristic_type TEXT NOT NULL,
            market_type TEXT,
            confidence REAL,
            recurring_count INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_heuristics_type
            ON heuristics(heuristic_type);
        CREATE INDEX IF NOT EXISTS idx_heuristics_market_type
            ON heuristics(market_type);

        CREATE TABLE IF NOT EXISTS heuristic_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            heuristic_id INTEGER NOT NULL REFERENCES heuristics(id) ON DELETE CASCADE,
            document_id INTEGER REFERENCES transcript_documents(id) ON DELETE CASCADE,
            chunk_id INTEGER REFERENCES transcript_chunks(id) ON DELETE SET NULL,
            quote_text TEXT NOT NULL,
            evidence_strength REAL,
            context_note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_heuristic_evidence_heuristic
            ON heuristic_evidence(heuristic_id);

        CREATE TABLE IF NOT EXISTS pricing_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_name TEXT NOT NULL UNIQUE,
            signal_type TEXT,
            description TEXT,
            interpretation TEXT,
            typical_action TEXT,
            confidence REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS phase_logic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phase_name TEXT NOT NULL,
            event_format_id INTEGER REFERENCES event_formats(id) ON DELETE CASCADE,
            description TEXT,
            what_becomes_more_likely TEXT,
            what_becomes_less_likely TEXT,
            common_pricing_errors TEXT,
            execution_notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(phase_name, event_format_id)
        );

        CREATE TABLE IF NOT EXISTS crowd_mistakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mistake_name TEXT NOT NULL UNIQUE,
            mistake_type TEXT,
            description TEXT,
            why_it_happens TEXT,
            how_to_exploit TEXT,
            example_document_id INTEGER REFERENCES transcript_documents(id) ON DELETE SET NULL,
            example_chunk_id INTEGER REFERENCES transcript_chunks(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS anti_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_text TEXT NOT NULL,
            why_bad TEXT NOT NULL,
            example_document_id INTEGER REFERENCES transcript_documents(id) ON DELETE SET NULL,
            example_chunk_id INTEGER REFERENCES transcript_chunks(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS execution_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_name TEXT NOT NULL UNIQUE,
            execution_type TEXT,
            description TEXT,
            best_used_when TEXT,
            avoid_when TEXT,
            risk_note TEXT,
            example_document_id INTEGER REFERENCES transcript_documents(id) ON DELETE SET NULL,
            example_chunk_id INTEGER REFERENCES transcript_chunks(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dispute_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_name TEXT NOT NULL UNIQUE,
            dispute_type TEXT,
            description TEXT,
            common_confusion TEXT,
            market_impact TEXT,
            mitigation TEXT,
            example_document_id INTEGER REFERENCES transcript_documents(id) ON DELETE SET NULL,
            example_chunk_id INTEGER REFERENCES transcript_chunks(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS live_trading_tells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tell_name TEXT NOT NULL UNIQUE,
            tell_type TEXT,
            description TEXT,
            interpretation TEXT,
            typical_response TEXT,
            risk_note TEXT,
            example_document_id INTEGER REFERENCES transcript_documents(id) ON DELETE SET NULL,
            example_chunk_id INTEGER REFERENCES transcript_chunks(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sizing_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_text TEXT NOT NULL UNIQUE,
            lesson_type TEXT,
            description TEXT,
            applies_to TEXT,
            risk_note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS decision_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER REFERENCES transcript_documents(id) ON DELETE CASCADE,
            chunk_id INTEGER REFERENCES transcript_chunks(id) ON DELETE SET NULL,
            market_context TEXT,
            setup TEXT,
            decision TEXT,
            reasoning TEXT,
            risk_note TEXT,
            outcome_note TEXT,
            tags TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_decision_cases_document
            ON decision_cases(document_id);

        -- ── Case join tables ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS case_principles (
            case_id INTEGER NOT NULL REFERENCES decision_cases(id) ON DELETE CASCADE,
            heuristic_id INTEGER NOT NULL REFERENCES heuristics(id) ON DELETE CASCADE,
            PRIMARY KEY(case_id, heuristic_id)
        );
        CREATE TABLE IF NOT EXISTS case_anti_patterns (
            case_id INTEGER NOT NULL REFERENCES decision_cases(id) ON DELETE CASCADE,
            anti_pattern_id INTEGER NOT NULL REFERENCES anti_patterns(id) ON DELETE CASCADE,
            PRIMARY KEY(case_id, anti_pattern_id)
        );
        CREATE TABLE IF NOT EXISTS case_crowd_mistakes (
            case_id INTEGER NOT NULL REFERENCES decision_cases(id) ON DELETE CASCADE,
            crowd_mistake_id INTEGER NOT NULL REFERENCES crowd_mistakes(id) ON DELETE CASCADE,
            PRIMARY KEY(case_id, crowd_mistake_id)
        );
        CREATE TABLE IF NOT EXISTS case_dispute_patterns (
            case_id INTEGER NOT NULL REFERENCES decision_cases(id) ON DELETE CASCADE,
            dispute_pattern_id INTEGER NOT NULL REFERENCES dispute_patterns(id) ON DELETE CASCADE,
            PRIMARY KEY(case_id, dispute_pattern_id)
        );
        CREATE TABLE IF NOT EXISTS case_execution_patterns (
            case_id INTEGER NOT NULL REFERENCES decision_cases(id) ON DELETE CASCADE,
            execution_pattern_id INTEGER NOT NULL REFERENCES execution_patterns(id) ON DELETE CASCADE,
            PRIMARY KEY(case_id, execution_pattern_id)
        );
        CREATE TABLE IF NOT EXISTS case_live_trading_tells (
            case_id INTEGER NOT NULL REFERENCES decision_cases(id) ON DELETE CASCADE,
            live_trading_tell_id INTEGER NOT NULL REFERENCES live_trading_tells(id) ON DELETE CASCADE,
            PRIMARY KEY(case_id, live_trading_tell_id)
        );
        CREATE TABLE IF NOT EXISTS case_pricing_signals (
            case_id INTEGER NOT NULL REFERENCES decision_cases(id) ON DELETE CASCADE,
            pricing_signal_id INTEGER NOT NULL REFERENCES pricing_signals(id) ON DELETE CASCADE,
            PRIMARY KEY(case_id, pricing_signal_id)
        );
        CREATE TABLE IF NOT EXISTS case_speaker_profiles (
            case_id INTEGER NOT NULL REFERENCES decision_cases(id) ON DELETE CASCADE,
            speaker_profile_id INTEGER NOT NULL REFERENCES speaker_profiles(id) ON DELETE CASCADE,
            PRIMARY KEY(case_id, speaker_profile_id)
        );

        PRAGMA user_version = 2;
    ''')
    log.info('Schema v2 applied')


# ── v3: chunk embedding cache ──────────────────────────────────────────────

def _v3(conn) -> None:
    """Persistent chunk-embedding cache.

    Semantic retrieval was re-embedding every candidate chunk on every
    query in v0.11. This table caches the vectors keyed by (chunk_id,
    model) so a second query over the same corpus pays only for the
    query text itself.

    Vectors are stored as little-endian float32 BLOBs (4 bytes * dim)
    via :mod:`library._core.retrieve.embed_cache`, which also owns the
    (un)pack helpers. Chunks deleted via CASCADE clean up their
    embeddings automatically.
    """
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS chunk_embeddings (
            chunk_id   INTEGER NOT NULL REFERENCES transcript_chunks(id)
                                                ON DELETE CASCADE,
            model      TEXT    NOT NULL,
            dim        INTEGER NOT NULL,
            vec        BLOB    NOT NULL,
            created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chunk_id, model)
        );
        CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model
            ON chunk_embeddings(model);

        PRAGMA user_version = 3;
    ''')
    log.info('Schema v3 applied')


# ── v4: Bayesian heuristic learning ───────────────────────────────────────

def _v4(conn) -> None:
    """Bayesian posterior for heuristic confidence.

    Each heuristic gains ``alpha`` and ``beta`` columns representing a
    Beta(α, β) posterior over "how often this heuristic is right". At
    insert we use Beta(1, 1) (uniform prior). Each time a heuristic
    is *applied* to a real market, the outcome is recorded in
    ``heuristic_applications``: success → α += 1, failure → β += 1.
    The posterior mean α/(α+β) replaces the static ``confidence``
    column for downstream ranking; the old column is kept for
    back-compat (legacy imports) and updated lazily via trigger or
    manual sync.

    ``heuristic_applications`` also doubles as an audit log — you can
    ask "where did heuristic X get applied and what happened?" long
    after the posterior has moved.
    """
    _add_column_if_missing(conn, 'heuristics', 'alpha', 'REAL NOT NULL DEFAULT 1.0')
    _add_column_if_missing(conn, 'heuristics', 'beta',  'REAL NOT NULL DEFAULT 1.0')

    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS heuristic_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            heuristic_id INTEGER NOT NULL
                REFERENCES heuristics(id) ON DELETE CASCADE,
            -- One of: 'yes', 'no', or NULL when the heuristic is
            -- directional-agnostic. Kept for audit / later analysis.
            predicted_direction TEXT,
            -- Binary outcome for this application: 1 = heuristic was
            -- borne out by market resolution, 0 = it wasn't.
            outcome INTEGER NOT NULL CHECK (outcome IN (0, 1)),
            -- Market / case context, free-form.
            market_ticker TEXT,
            case_id INTEGER REFERENCES decision_cases(id) ON DELETE SET NULL,
            note TEXT,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_heuristic_applications_heuristic
            ON heuristic_applications(heuristic_id);
        CREATE INDEX IF NOT EXISTS idx_heuristic_applications_applied_at
            ON heuristic_applications(applied_at);

        PRAGMA user_version = 4;
    ''')
    log.info('Schema v4 applied')


def _v5(conn) -> None:
    """Bayesian posterior for speaker stance.

    Mirrors v4 (heuristics) one level up: ``speaker_profiles`` gain an
    α / β pair and a sibling ``speaker_stance_applications`` table
    records every time a speaker's stance was used as input to a
    market decision. Success → α += 1, failure → β += 1.

    Why per-speaker, not per-(speaker, stance)? The ``stance`` is
    logged on every application row so callers can slice the audit
    log later and compute conditional posteriors ("Powell, hawkish
    only"). The canonical posterior on ``speaker_profiles`` captures
    the speaker's overall signal-to-noise ratio — a speaker whose
    every directional call flops should bubble to the bottom of any
    ranking regardless of stance.
    """
    _add_column_if_missing(conn, 'speaker_profiles', 'alpha',
                           'REAL NOT NULL DEFAULT 1.0')
    _add_column_if_missing(conn, 'speaker_profiles', 'beta',
                           'REAL NOT NULL DEFAULT 1.0')

    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS speaker_stance_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker_profile_id INTEGER NOT NULL
                REFERENCES speaker_profiles(id) ON DELETE CASCADE,
            -- Free-form stance tag: 'hawkish' | 'dovish' | 'bullish'
            -- | 'bearish' | domain-specific labels. NULL allowed for
            -- agnostic applications.
            stance TEXT,
            predicted_direction TEXT,
            outcome INTEGER NOT NULL CHECK (outcome IN (0, 1)),
            market_ticker TEXT,
            case_id INTEGER REFERENCES decision_cases(id) ON DELETE SET NULL,
            note TEXT,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_ssa_speaker
            ON speaker_stance_applications(speaker_profile_id);
        CREATE INDEX IF NOT EXISTS idx_ssa_stance
            ON speaker_stance_applications(stance);
        CREATE INDEX IF NOT EXISTS idx_ssa_applied_at
            ON speaker_stance_applications(applied_at);

        PRAGMA user_version = 5;
    ''')
    log.info('Schema v5 applied')


def _v6(conn) -> None:
    """Market-ticker column on ``decision_cases``.

    Cross-market hedge detection needs to answer "has the agent
    recently committed to an opposing or mutually-exclusive market
    outcome?". Pre-v6 ``decision_cases`` stored only a free-form
    ``market_context`` string; we now persist the canonical Kalshi
    ticker so we can index on it.

    Backfill is NOT attempted — old rows keep ``market_ticker = NULL``
    and are ignored by :mod:`hedge_check`. New writes should populate
    the column when a ticker is available.
    """
    _add_column_if_missing(conn, 'decision_cases', 'market_ticker', 'TEXT')
    cur = conn.cursor()
    cur.executescript('''
        CREATE INDEX IF NOT EXISTS idx_decision_cases_market_ticker
            ON decision_cases(market_ticker);
        PRAGMA user_version = 6;
    ''')
    log.info('Schema v6 applied')


def _v7(conn) -> None:
    """Regime tagging + binary decision outcomes.

    Three additive columns:

    * ``heuristic_applications.regime`` TEXT — free-form regime tag
      (e.g. ``'high_vol'``, ``'bull'``, ``'pre_fomc'``). NULL means
      regime-agnostic. Enables per-regime conditional posteriors
      computed at read time in
      :mod:`library._core.analysis.heuristic_learn`.
    * ``speaker_stance_applications.regime`` TEXT — same for speaker
      posteriors, mirrored for consistency.
    * ``decision_cases.outcome`` INTEGER — binary 0/1 win marker
      (NULL = unresolved). Separate from the free-form
      ``outcome_note`` so counterfactual analysis can use a
      machine-readable column.

    All three columns default to NULL and existing rows are
    untouched. Indexes on ``regime`` so per-regime ranking queries
    stay cheap as the audit log grows.
    """
    _add_column_if_missing(conn, 'heuristic_applications', 'regime', 'TEXT')
    _add_column_if_missing(conn, 'speaker_stance_applications',
                           'regime', 'TEXT')
    _add_column_if_missing(conn, 'decision_cases', 'outcome', 'INTEGER')
    cur = conn.cursor()
    cur.executescript('''
        CREATE INDEX IF NOT EXISTS idx_heuristic_apps_regime
            ON heuristic_applications(regime);
        CREATE INDEX IF NOT EXISTS idx_ssa_regime_v7
            ON speaker_stance_applications(regime);
        CREATE INDEX IF NOT EXISTS idx_decision_cases_outcome
            ON decision_cases(outcome);
        PRAGMA user_version = 7;
    ''')
    log.info('Schema v7 applied')


def _v8(conn) -> None:
    """FTS5 sync via triggers (v0.14.6 — D2).

    Until now ``transcript_chunks_fts`` was kept in sync by explicit
    ``sync_document`` / ``sync_chunks`` calls after ingest. Any write
    path that skipped those calls (direct backfill, admin SQL, future
    modules forgetting the call) left the FTS index quietly stale —
    BM25 retrieval returned zero hits with no error, the most insidious
    kind of bug.

    This migration installs ``AFTER INSERT / UPDATE / DELETE`` triggers
    on ``transcript_chunks`` that mirror each row into the FTS table
    using SQLite's standard external-content pattern (see FTS5 docs
    §4.4.3). The ``sync_*`` helpers remain as emergency rebuild tools;
    normal writes no longer need them.

    We ``DROP TRIGGER IF EXISTS`` first so re-running v8 on a partial
    migration is idempotent.
    """
    cur = conn.cursor()
    cur.executescript('''
        DROP TRIGGER IF EXISTS transcript_chunks_ai;
        DROP TRIGGER IF EXISTS transcript_chunks_ad;
        DROP TRIGGER IF EXISTS transcript_chunks_au;

        CREATE TRIGGER transcript_chunks_ai
        AFTER INSERT ON transcript_chunks
        BEGIN
            INSERT INTO transcript_chunks_fts(rowid, text, speaker, section)
            VALUES (new.id,
                    COALESCE(new.text, ''),
                    COALESCE(new.speaker, ''),
                    COALESCE(new.section, ''));
        END;

        CREATE TRIGGER transcript_chunks_ad
        AFTER DELETE ON transcript_chunks
        BEGIN
            INSERT INTO transcript_chunks_fts(transcript_chunks_fts, rowid,
                                              text, speaker, section)
            VALUES ('delete', old.id,
                    COALESCE(old.text, ''),
                    COALESCE(old.speaker, ''),
                    COALESCE(old.section, ''));
        END;

        CREATE TRIGGER transcript_chunks_au
        AFTER UPDATE ON transcript_chunks
        BEGIN
            INSERT INTO transcript_chunks_fts(transcript_chunks_fts, rowid,
                                              text, speaker, section)
            VALUES ('delete', old.id,
                    COALESCE(old.text, ''),
                    COALESCE(old.speaker, ''),
                    COALESCE(old.section, ''));
            INSERT INTO transcript_chunks_fts(rowid, text, speaker, section)
            VALUES (new.id,
                    COALESCE(new.text, ''),
                    COALESCE(new.speaker, ''),
                    COALESCE(new.section, ''));
        END;

        PRAGMA user_version = 8;
    ''')
    log.info('Schema v8 applied')


def _v9(conn) -> None:
    """Per-chunk canonical speaker attribution (v0.14.6 — T1).

    Panel / multi-speaker transcripts are chunked with the *dominant*
    speaker of each chunk attached to ``transcript_chunks.speaker``
    (see chunker ``_dominant_speaker``). That name is the raw
    surface string as it appeared in the transcript — "Chair Powell",
    "Jerome Powell", "J. Powell" all produce different rows. The
    reliability-weighted retrieval layer (v0.14.1) joins on
    ``speaker_profiles.canonical_name``; surface-name drift breaks
    that join silently.

    v9 adds ``transcript_chunks.speaker_canonical`` TEXT. The ingest
    path populates it by resolving each detected surface name
    against ``speaker_profiles.canonical_name`` + its ``aliases``
    JSON array (see ``library._core.analysis.speaker_canonicalize``).
    Unresolvable names stay NULL — callers fall back to the raw
    ``speaker`` field.

    The FTS triggers from v8 continue to index the raw ``speaker``
    column; adding canonical to the FTS shape would require dropping
    and recreating the virtual table, and raw-name hits are still
    useful for free-form search.
    """
    _add_column_if_missing(conn, 'transcript_chunks',
                           'speaker_canonical', 'TEXT')
    cur = conn.cursor()
    cur.executescript('''
        CREATE INDEX IF NOT EXISTS idx_transcript_chunks_speaker_canonical
            ON transcript_chunks(speaker_canonical);
        PRAGMA user_version = 9;
    ''')
    log.info('Schema v9 applied')


def _v10(conn) -> None:
    """Decision-case resolution timestamp (v0.14.7 — D1).

    ``decision_cases.outcome`` (v7) records the 0/1 win marker but
    not *when* it resolved. Without a timestamp we can't ask
    "does heuristic X work on short-horizon markets but not long?",
    or "what's the median time-to-resolution across heuristic Y's
    winning applications?". Both are orthogonal to the regime and
    lift axes — a heuristic can have positive lift overall but fail
    systematically on fast-resolving markets.

    This migration adds ``decision_cases.outcome_resolved_at TEXT``
    (ISO 8601, nullable). Writers populate it when they set
    ``outcome``; existing rows stay NULL and are gracefully skipped
    by the latency-stats helper.

    An index on the column lets time-range queries ("resolutions in
    the last 30 days") stay cheap as the audit grows.
    """
    _add_column_if_missing(conn, 'decision_cases',
                           'outcome_resolved_at', 'TEXT')
    cur = conn.cursor()
    cur.executescript('''
        CREATE INDEX IF NOT EXISTS idx_decision_cases_outcome_resolved_at
            ON decision_cases(outcome_resolved_at);
        PRAGMA user_version = 10;
    ''')
    log.info('Schema v10 applied')
