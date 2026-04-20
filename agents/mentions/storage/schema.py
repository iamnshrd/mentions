from __future__ import annotations

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS speakers (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    event_date TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL DEFAULT '',
    source_ref TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    speaker_id INTEGER,
    event_id INTEGER,
    event_date TEXT NOT NULL DEFAULT '',
    raw_text TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_ref),
    FOREIGN KEY (speaker_id) REFERENCES speakers(id),
    FOREIGN KEY (event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id INTEGER PRIMARY KEY,
    transcript_id INTEGER NOT NULL,
    segment_index INTEGER NOT NULL,
    speaker_id INTEGER,
    start_ts TEXT NOT NULL DEFAULT '',
    end_ts TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(transcript_id, segment_index),
    FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE,
    FOREIGN KEY (speaker_id) REFERENCES speakers(id)
);

CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL UNIQUE,
    headline TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    body_text TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    speaker_id INTEGER,
    event_id INTEGER,
    dedupe_hash TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (speaker_id) REFERENCES speakers(id),
    FOREIGN KEY (event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    event_ticker TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    market_json TEXT NOT NULL DEFAULT '{}',
    history_json TEXT NOT NULL DEFAULT '[]',
    provider_status_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_ticker_fetched_at
ON market_snapshots(ticker, fetched_at DESC);

CREATE TABLE IF NOT EXISTS market_resolution_runs (
    id INTEGER PRIMARY KEY,
    query TEXT NOT NULL,
    resolved_ticker TEXT NOT NULL DEFAULT '',
    confidence TEXT NOT NULL DEFAULT 'low',
    score_margin REAL NOT NULL DEFAULT 0,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    sourcing_json TEXT NOT NULL DEFAULT '{}',
    candidates_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_reports (
    id INTEGER PRIMARY KEY,
    query TEXT NOT NULL,
    ticker TEXT NOT NULL DEFAULT '',
    workflow_decision TEXT NOT NULL DEFAULT '',
    output_mode TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    analysis_json TEXT NOT NULL DEFAULT '{}',
    rendered_text TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcript_knowledge_artifacts (
    id INTEGER PRIMARY KEY,
    transcript_id INTEGER,
    category TEXT NOT NULL,
    speaker_id INTEGER,
    event_id INTEGER,
    score REAL NOT NULL DEFAULT 0,
    hits_json TEXT NOT NULL DEFAULT '[]',
    artifact_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE,
    FOREIGN KEY (speaker_id) REFERENCES speakers(id),
    FOREIGN KEY (event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS transcript_tags (
    id INTEGER PRIMARY KEY,
    transcript_id INTEGER NOT NULL UNIQUE,
    speaker_primary TEXT NOT NULL DEFAULT '',
    speaker_aliases_json TEXT NOT NULL DEFAULT '[]',
    speaker_family_json TEXT NOT NULL DEFAULT '[]',
    topic_tags_json TEXT NOT NULL DEFAULT '[]',
    topic_family_tags_json TEXT NOT NULL DEFAULT '[]',
    format_tags_json TEXT NOT NULL DEFAULT '[]',
    event_tags_json TEXT NOT NULL DEFAULT '[]',
    mention_tags_json TEXT NOT NULL DEFAULT '[]',
    quality_tags_json TEXT NOT NULL DEFAULT '[]',
    user_topic_tags_json TEXT NOT NULL DEFAULT '[]',
    user_format_tags_json TEXT NOT NULL DEFAULT '[]',
    user_event_tags_json TEXT NOT NULL DEFAULT '[]',
    user_mention_tags_json TEXT NOT NULL DEFAULT '[]',
    user_quality_tags_json TEXT NOT NULL DEFAULT '[]',
    suggested_topic_tags_json TEXT NOT NULL DEFAULT '[]',
    suggested_format_tags_json TEXT NOT NULL DEFAULT '[]',
    suggested_event_tags_json TEXT NOT NULL DEFAULT '[]',
    suggested_mention_tags_json TEXT NOT NULL DEFAULT '[]',
    suggested_quality_tags_json TEXT NOT NULL DEFAULT '[]',
    accepted_suggested_topic_tags_json TEXT NOT NULL DEFAULT '[]',
    accepted_suggested_format_tags_json TEXT NOT NULL DEFAULT '[]',
    accepted_suggested_event_tags_json TEXT NOT NULL DEFAULT '[]',
    accepted_suggested_mention_tags_json TEXT NOT NULL DEFAULT '[]',
    accepted_suggested_quality_tags_json TEXT NOT NULL DEFAULT '[]',
    rejected_suggested_topic_tags_json TEXT NOT NULL DEFAULT '[]',
    rejected_suggested_format_tags_json TEXT NOT NULL DEFAULT '[]',
    rejected_suggested_event_tags_json TEXT NOT NULL DEFAULT '[]',
    rejected_suggested_mention_tags_json TEXT NOT NULL DEFAULT '[]',
    rejected_suggested_quality_tags_json TEXT NOT NULL DEFAULT '[]',
    review_status TEXT NOT NULL DEFAULT 'unreviewed',
    tagging_confidence REAL NOT NULL DEFAULT 0,
    tagging_source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_links (
    id INTEGER PRIMARY KEY,
    document_type TEXT NOT NULL,
    document_id INTEGER NOT NULL,
    speaker_id INTEGER,
    topic_id INTEGER,
    event_id INTEGER,
    link_type TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (speaker_id) REFERENCES speakers(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id),
    FOREIGN KEY (event_id) REFERENCES events(id)
);
"""
