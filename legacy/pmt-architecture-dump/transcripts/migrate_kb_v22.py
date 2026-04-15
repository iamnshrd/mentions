#!/usr/bin/env python3
import sqlite3

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

conn=sqlite3.connect(DB)
conn.executescript('''
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS speaker_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  speaker_name TEXT NOT NULL UNIQUE,
  speaker_type TEXT,
  description TEXT,
  behavior_style TEXT,
  favored_topics TEXT,
  avoid_topics TEXT,
  qna_style TEXT,
  adaptation_notes TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crowd_mistakes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mistake_name TEXT NOT NULL UNIQUE,
  mistake_type TEXT,
  description TEXT,
  why_it_happens TEXT,
  how_to_exploit TEXT,
  example_video_id TEXT,
  example_chunk_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(example_video_id) REFERENCES videos(video_id) ON DELETE SET NULL,
  FOREIGN KEY(example_chunk_id) REFERENCES transcript_chunks(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS dispute_patterns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pattern_name TEXT NOT NULL UNIQUE,
  dispute_type TEXT,
  description TEXT,
  common_confusion TEXT,
  market_impact TEXT,
  mitigation TEXT,
  example_video_id TEXT,
  example_chunk_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(example_video_id) REFERENCES videos(video_id) ON DELETE SET NULL,
  FOREIGN KEY(example_chunk_id) REFERENCES transcript_chunks(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS live_trading_tells (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tell_name TEXT NOT NULL UNIQUE,
  tell_type TEXT,
  description TEXT,
  interpretation TEXT,
  typical_response TEXT,
  risk_note TEXT,
  example_video_id TEXT,
  example_chunk_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(example_video_id) REFERENCES videos(video_id) ON DELETE SET NULL,
  FOREIGN KEY(example_chunk_id) REFERENCES transcript_chunks(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS case_speaker_profiles (
  case_id INTEGER NOT NULL,
  speaker_profile_id INTEGER NOT NULL,
  PRIMARY KEY(case_id, speaker_profile_id),
  FOREIGN KEY(case_id) REFERENCES decision_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(speaker_profile_id) REFERENCES speaker_profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS case_crowd_mistakes (
  case_id INTEGER NOT NULL,
  crowd_mistake_id INTEGER NOT NULL,
  PRIMARY KEY(case_id, crowd_mistake_id),
  FOREIGN KEY(case_id) REFERENCES decision_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(crowd_mistake_id) REFERENCES crowd_mistakes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS case_dispute_patterns (
  case_id INTEGER NOT NULL,
  dispute_pattern_id INTEGER NOT NULL,
  PRIMARY KEY(case_id, dispute_pattern_id),
  FOREIGN KEY(case_id) REFERENCES decision_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(dispute_pattern_id) REFERENCES dispute_patterns(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS case_live_trading_tells (
  case_id INTEGER NOT NULL,
  live_trading_tell_id INTEGER NOT NULL,
  PRIMARY KEY(case_id, live_trading_tell_id),
  FOREIGN KEY(case_id) REFERENCES decision_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(live_trading_tell_id) REFERENCES live_trading_tells(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_speaker_profiles_type ON speaker_profiles(speaker_type);
CREATE INDEX IF NOT EXISTS idx_crowd_mistakes_type ON crowd_mistakes(mistake_type);
CREATE INDEX IF NOT EXISTS idx_dispute_patterns_type ON dispute_patterns(dispute_type);
CREATE INDEX IF NOT EXISTS idx_live_trading_tells_type ON live_trading_tells(tell_type);
''')
conn.commit()

print('Migrated v2.2 schema in', DB)
for table in [
    'speaker_profiles',
    'crowd_mistakes',
    'dispute_patterns',
    'live_trading_tells',
    'case_speaker_profiles',
    'case_crowd_mistakes',
    'case_dispute_patterns',
    'case_live_trading_tells',
]:
    count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(table, count)
