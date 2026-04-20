#!/usr/bin/env python3
import json
import sqlite3
from collections import OrderedDict
from pathlib import Path

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'
OUT='/root/.openclaw/workspace/transcripts/extraction_candidates_timing_mentions.json'

QUERIES = OrderedDict([
    ('timing_core', 'clip OR headline OR before OR after OR timing OR "market moved" OR moved OR reaction'),
    ('mentions_core', 'mentions OR "mention markets" OR strike OR speech OR stream OR press briefing'),
    ('execution_timing', 'limit order OR fill OR spread OR price OR odds'),
    ('uncertainty_setup', 'probably OR likely OR "not sure" OR thesis OR vibes'),
])

conn=sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

all_candidates=[]
seen=set()
per_video_count={}

for bucket, query in QUERIES.items():
    rows=conn.execute('''
      SELECT c.id as chunk_id, c.video_id, v.title, c.chunk_index, c.text
      FROM transcript_chunks_fts f
      JOIN transcript_chunks c ON c.id = f.rowid
      JOIN videos v ON v.video_id = c.video_id
      WHERE transcript_chunks_fts MATCH ?
      LIMIT 250
    ''',(query,)).fetchall()
    for r in rows:
        key = (r['chunk_id'])
        vid = r['video_id']
        if key in seen:
            continue
        if per_video_count.get(vid,0) >= 3:
            continue
        text=' '.join(r['text'].split())
        if len(text) < 160:
            continue
        lowered = text.lower()
        score = 0
        for token in ['mentions','market','price','odds','clip','headline','limit order','fair value','overbought','discount','late','speech']:
            if token in lowered:
                score += 1
        all_candidates.append({
            'bucket': bucket,
            'score': score,
            'chunk_id': r['chunk_id'],
            'video_id': vid,
            'title': r['title'],
            'chunk_index': r['chunk_index'],
            'text': text,
        })
        seen.add(key)
        per_video_count[vid] = per_video_count.get(vid,0) + 1

all_candidates.sort(key=lambda x: (-x['score'], x['video_id'], x['chunk_index']))
Path(OUT).write_text(json.dumps(all_candidates[:120], ensure_ascii=False, indent=2), encoding='utf-8')
print('wrote', OUT, 'count', min(120, len(all_candidates)))
print('top 15:')
for c in all_candidates[:15]:
    print('-', c['bucket'], c['video_id'], c['title'])
