#!/usr/bin/env python3
import sqlite3

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

conn=sqlite3.connect(DB)
conn.executescript('''
PRAGMA foreign_keys=ON;

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

CREATE TABLE IF NOT EXISTS heuristic_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  heuristic_id INTEGER NOT NULL,
  video_id TEXT NOT NULL,
  chunk_id INTEGER,
  quote_text TEXT NOT NULL,
  evidence_strength REAL,
  context_note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(heuristic_id) REFERENCES heuristics(id) ON DELETE CASCADE,
  FOREIGN KEY(video_id) REFERENCES videos(video_id) ON DELETE CASCADE,
  FOREIGN KEY(chunk_id) REFERENCES transcript_chunks(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS decision_cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT NOT NULL,
  chunk_id INTEGER,
  market_context TEXT,
  setup TEXT,
  decision TEXT,
  reasoning TEXT,
  risk_note TEXT,
  outcome_note TEXT,
  tags TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(video_id) REFERENCES videos(video_id) ON DELETE CASCADE,
  FOREIGN KEY(chunk_id) REFERENCES transcript_chunks(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_heuristics_type ON heuristics(heuristic_type);
CREATE INDEX IF NOT EXISTS idx_heuristic_evidence_heuristic_id ON heuristic_evidence(heuristic_id);
CREATE INDEX IF NOT EXISTS idx_heuristic_evidence_video_id ON heuristic_evidence(video_id);
CREATE INDEX IF NOT EXISTS idx_decision_cases_video_id ON decision_cases(video_id);
''')
conn.commit()
print('Extended schema in', DB)
for table in ['heuristics','heuristic_evidence','decision_cases']:
    count=conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(table, count)
