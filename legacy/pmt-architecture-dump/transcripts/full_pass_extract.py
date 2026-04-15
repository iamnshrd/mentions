#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path
from collections import OrderedDict

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'
OUT='/root/.openclaw/workspace/transcripts/full_pass_candidates.json'
SUMMARY='/root/.openclaw/workspace/transcripts/full_pass_summary.json'

TOPIC_QUERIES = OrderedDict([
    ('entry_pricing', 'entry OR chase OR price OR odds OR "fair value" OR spread OR EV OR overbought OR discount'),
    ('execution', '"limit order" OR maker OR taker OR fills OR fill OR fees OR spread'),
    ('timing_setup', 'clip OR headline OR before OR after OR timing OR reaction OR "Q&A" OR venue OR "East Room" OR rally OR briefing'),
    ('mentions_logic', 'mentions OR "mention markets" OR strike OR speech OR topic OR bring up OR say OR said'),
    ('risk_disputes', 'dispute OR resolved OR resolve OR partial OR sequence OR live OR volatility OR uncertainty'),
])

conn=sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
all_candidates=[]
seen_chunks=set()
per_video_total={}
per_topic_counts={}

for topic, query in TOPIC_QUERIES.items():
    rows=conn.execute('''
      SELECT c.id as chunk_id, c.video_id, v.title, c.chunk_index, c.text
      FROM transcript_chunks_fts f
      JOIN transcript_chunks c ON c.id = f.rowid
      JOIN videos v ON v.video_id = c.video_id
      WHERE transcript_chunks_fts MATCH ?
      LIMIT 1200
    ''',(query,)).fetchall()
    kept=0
    for r in rows:
        cid=r['chunk_id']
        vid=r['video_id']
        if cid in seen_chunks:
            continue
        if per_video_total.get(vid,0) >= 8:
            continue
        text=' '.join(r['text'].split())
        if len(text) < 180:
            continue
        lowered=text.lower()
        score=0
        for token in ['price','limit order','fair value','mentions','market','speech','headline','clip','dispute','q&a','late','odds','overbought','discount','fill']:
            if token in lowered:
                score += 1
        all_candidates.append({
            'topic': topic,
            'score': score,
            'chunk_id': cid,
            'video_id': vid,
            'title': r['title'],
            'chunk_index': r['chunk_index'],
            'text': text,
        })
        seen_chunks.add(cid)
        per_video_total[vid]=per_video_total.get(vid,0)+1
        kept += 1
    per_topic_counts[topic]=kept

all_candidates.sort(key=lambda x: (-x['score'], x['topic'], x['video_id'], x['chunk_index']))
Path(OUT).write_text(json.dumps(all_candidates, ensure_ascii=False, indent=2), encoding='utf-8')
summary={
    'total_candidates': len(all_candidates),
    'topic_counts': per_topic_counts,
    'unique_videos': len({c['video_id'] for c in all_candidates}),
}
Path(SUMMARY).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
print('OUT', OUT)
