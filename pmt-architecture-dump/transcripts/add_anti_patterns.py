#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

def now():
    return datetime.now(timezone.utc).isoformat()

conn=sqlite3.connect(DB)
conn.executescript('''
CREATE TABLE IF NOT EXISTS anti_patterns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pattern_text TEXT NOT NULL,
  why_bad TEXT NOT NULL,
  example_video_id TEXT,
  example_chunk_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(example_video_id) REFERENCES videos(video_id) ON DELETE SET NULL,
  FOREIGN KEY(example_chunk_id) REFERENCES transcript_chunks(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_anti_patterns_video_id ON anti_patterns(example_video_id);
''')

SEEDS = [
    {
        'pattern_text': 'Chasing a strike after it has already steamed far beyond your original edge.',
        'why_bad': 'A thesis can stay directionally correct while the current price becomes terrible. Late followers inherit the worst EV and confuse idea quality with trade quality.',
        'example_video_id': '0f3Bws_klco',
        'example_chunk_id': 3754,
    },
    {
        'pattern_text': 'Copying someone else\'s position without matching their entry price or timing.',
        'why_bad': 'Prediction markets are extremely path-dependent. Buying the same side at a much worse fill can turn a good trade into a bad one.',
        'example_video_id': '0SQ1N4o2cLQ',
        'example_chunk_id': 3724,
    },
    {
        'pattern_text': 'Using blind market buys or dollar orders in thin, wide-spread event markets.',
        'why_bad': 'You donate spread and fees immediately, lose price control, and often end up entering exactly at the worst part of the book.',
        'example_video_id': '0f3Bws_klco',
        'example_chunk_id': 3756,
    },
    {
        'pattern_text': 'Leaving stale resting orders up right as the live event begins.',
        'why_bad': 'Once the event goes live, a spoken word or fresh information can instantly pick you off. Go-live order risk is much higher than static-book risk.',
        'example_video_id': '6gNeabkXq8k',
        'example_chunk_id': 4357,
    },
    {
        'pattern_text': 'Treating partial triggers or almost-events as if they are already fully resolved.',
        'why_bad': 'Live sequence trading can be profitable, but partial progression carries dispute risk. Confusing “nearly happened” with “cleanly happened” is a fast way to get trapped.',
        'example_video_id': '0LssiD1TVdM',
        'example_chunk_id': 3685,
    }
]

now_ts = now()
for seed in SEEDS:
    row = conn.execute('SELECT id FROM anti_patterns WHERE pattern_text=?', (seed['pattern_text'],)).fetchone()
    if row:
        conn.execute('''
            UPDATE anti_patterns
            SET why_bad=?, example_video_id=?, example_chunk_id=?, updated_at=?
            WHERE id=?
        ''', (seed['why_bad'], seed['example_video_id'], seed['example_chunk_id'], now_ts, row[0]))
    else:
        conn.execute('''
            INSERT INTO anti_patterns (pattern_text, why_bad, example_video_id, example_chunk_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (seed['pattern_text'], seed['why_bad'], seed['example_video_id'], seed['example_chunk_id'], now_ts, now_ts))
conn.commit()
print('anti_patterns total:', conn.execute('SELECT COUNT(*) FROM anti_patterns').fetchone()[0])
for row in conn.execute('SELECT id, substr(pattern_text,1,100) FROM anti_patterns ORDER BY id'):
    print(row)
