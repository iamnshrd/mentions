#!/usr/bin/env python3
import sqlite3
from collections import OrderedDict

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

queries=[
    ('mentions', 'mentions OR "mention markets"'),
    ('execution', 'entry OR chase OR price OR odds OR "limit order"'),
    ('timing', 'clip OR headline OR before OR after OR "market moved"'),
    ('uncertainty', '"not sure" OR probably OR likely OR "I don''t know"'),
]

conn=sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

for label,q in queries:
    print(f'=== {label.upper()} :: {q} ===')
    rows=conn.execute('''
      SELECT c.video_id, v.title, c.text
      FROM transcript_chunks_fts f
      JOIN transcript_chunks c ON c.id = f.rowid
      JOIN videos v ON v.video_id = c.video_id
      WHERE transcript_chunks_fts MATCH ?
      LIMIT 80
    ''',(q,)).fetchall()
    uniq = OrderedDict()
    for r in rows:
        if r['video_id'] not in uniq:
            uniq[r['video_id']] = r
        if len(uniq) >= 5:
            break
    if not uniq:
        print('NO_HITS\n')
        continue
    for r in uniq.values():
        snippet = ' '.join(r['text'].split())[:320]
        print(f"- {r['video_id']} :: {r['title']}")
        print('  ', snippet)
    print()
