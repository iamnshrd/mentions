#!/usr/bin/env python3
import sqlite3

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

conn=sqlite3.connect(DB)
conn.executescript('''
PRAGMA foreign_keys=ON;

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

CREATE TABLE IF NOT EXISTS execution_patterns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pattern_name TEXT NOT NULL UNIQUE,
  execution_type TEXT,
  description TEXT,
  best_used_when TEXT,
  avoid_when TEXT,
  risk_note TEXT,
  example_video_id TEXT,
  example_chunk_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(example_video_id) REFERENCES videos(video_id) ON DELETE SET NULL,
  FOREIGN KEY(example_chunk_id) REFERENCES transcript_chunks(id) ON DELETE SET NULL
);

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

CREATE TABLE IF NOT EXISTS phase_logic (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phase_name TEXT NOT NULL,
  event_format_id INTEGER,
  description TEXT,
  what_becomes_more_likely TEXT,
  what_becomes_less_likely TEXT,
  common_pricing_errors TEXT,
  execution_notes TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(phase_name, event_format_id),
  FOREIGN KEY(event_format_id) REFERENCES event_formats(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS case_principles (
  case_id INTEGER NOT NULL,
  heuristic_id INTEGER NOT NULL,
  PRIMARY KEY(case_id, heuristic_id),
  FOREIGN KEY(case_id) REFERENCES decision_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(heuristic_id) REFERENCES heuristics(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS case_anti_patterns (
  case_id INTEGER NOT NULL,
  anti_pattern_id INTEGER NOT NULL,
  PRIMARY KEY(case_id, anti_pattern_id),
  FOREIGN KEY(case_id) REFERENCES decision_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(anti_pattern_id) REFERENCES anti_patterns(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS case_pricing_signals (
  case_id INTEGER NOT NULL,
  pricing_signal_id INTEGER NOT NULL,
  PRIMARY KEY(case_id, pricing_signal_id),
  FOREIGN KEY(case_id) REFERENCES decision_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(pricing_signal_id) REFERENCES pricing_signals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS case_execution_patterns (
  case_id INTEGER NOT NULL,
  execution_pattern_id INTEGER NOT NULL,
  PRIMARY KEY(case_id, execution_pattern_id),
  FOREIGN KEY(case_id) REFERENCES decision_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(execution_pattern_id) REFERENCES execution_patterns(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_market_archetypes_type ON market_archetypes(archetype_type);
CREATE INDEX IF NOT EXISTS idx_event_formats_domain ON event_formats(domain);
CREATE INDEX IF NOT EXISTS idx_execution_patterns_type ON execution_patterns(execution_type);
CREATE INDEX IF NOT EXISTS idx_pricing_signals_type ON pricing_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_sizing_lessons_type ON sizing_lessons(lesson_type);
CREATE INDEX IF NOT EXISTS idx_phase_logic_event_format ON phase_logic(event_format_id);
''')
conn.commit()

print('Migrated v2 schema in', DB)
for table in [
    'market_archetypes',
    'event_formats',
    'execution_patterns',
    'pricing_signals',
    'sizing_lessons',
    'phase_logic',
    'case_principles',
    'case_anti_patterns',
    'case_pricing_signals',
    'case_execution_patterns',
]:
    count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(table, count)
