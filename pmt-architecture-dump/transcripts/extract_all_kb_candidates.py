#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path
from collections import defaultdict

DB = '/root/.openclaw/workspace/pmt_trader_knowledge.db'
OUT_DIR = Path('/root/.openclaw/workspace/transcripts/kb_candidates')
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOPIC_QUERIES = {
    'principles': 'fair OR value OR price OR edge OR transcript OR qna OR setup OR segmentation OR market OR recurring OR model',
    'execution_patterns': '"limit order" OR maker OR taker OR fill OR fills OR passive OR aggressive OR orderbook OR bond OR bonding OR chase OR marketmaking OR snipe',
    'sizing_lessons': 'size OR sizing OR bankroll OR portfolio OR conviction OR undersized OR kelly OR capital OR allocation',
    'market_archetypes': 'recurring OR announcer OR speech OR briefing OR earnings OR culture OR performer OR field OR market',
    'event_formats': 'open OR closed OR press OR briefing OR qna OR prepared OR remarks OR interview OR rally OR announcement',
    'phase_logic': 'qna OR prepared OR remarks OR late OR early OR opening OR garbage OR dead game OR fourth quarter',
    'speaker_profiles': 'Trump OR Karoline OR Vance OR Powell OR announcer OR speaker OR briefing OR says OR style',
    'pricing_signals': 'mispriced OR underpriced OR overpriced OR priced OR market OR overreaction OR setup OR transcript OR signal',
    'crowd_mistakes': 'everyone OR people OR crowd OR market OR priced OR overreaction OR setup OR transcript OR assume',
    'dispute_patterns': 'dispute OR resolve OR clarification OR rules OR contract OR count OR counted OR ambiguity OR brand',
    'live_trading_tells': 'live OR filled OR fill OR orderbook OR bid OR ask OR snipe OR pumped OR book OR market moved',
    'decision_cases': 'I bought OR I sold OR I should have OR I regret OR I sized OR I took OR I faded OR I held',
}

CATEGORY_HINTS = {
    'principles': ['fair value', 'edge', 'should', 'historical', 'market', 'recurring', 'q&a', 'setup'],
    'execution_patterns': ['limit order', 'maker', 'taker', 'fill', 'passive', 'aggressive', 'orderbook', 'bond', 'snipe'],
    'sizing_lessons': ['size', 'sizing', 'bankroll', 'portfolio', 'undersized', 'conviction', 'kelly', 'capital'],
    'market_archetypes': ['recurring', 'announcer', 'speech', 'briefing', 'earnings', 'performer', 'field'],
    'event_formats': ['open press', 'closed press', 'briefing', 'q&a', 'prepared remarks', 'interview', 'rally'],
    'phase_logic': ['prepared', 'q&a', 'late', 'early', 'opening', 'garbage time', 'fourth quarter'],
    'speaker_profiles': ['trump', 'karoline', 'vance', 'powell', 'announcer', 'speaker', 'style'],
    'pricing_signals': ['mispriced', 'underpriced', 'overpriced', 'priced', 'market', 'overreaction'],
    'crowd_mistakes': ['everyone', 'people', 'crowd', 'market', 'assume', 'priced'],
    'dispute_patterns': ['dispute', 'resolve', 'clarification', 'rules', 'contract', 'count', 'ambiguity'],
    'live_trading_tells': ['filled', 'fill', 'orderbook', 'bid', 'ask', 'snipe', 'pumped', 'book'],
    'decision_cases': ['i bought', 'i sold', 'i should have', 'i regret', 'i sized', 'i took', 'i faded', 'i held'],
}

MAX_PER_VIDEO_PER_CATEGORY = 8
MAX_RESULTS_PER_CATEGORY = 2500
MIN_TEXT_LEN = 180

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

all_summary = {}

for category, query in TOPIC_QUERIES.items():
    rows = conn.execute('''
      SELECT c.id as chunk_id, c.video_id, v.title, c.chunk_index, c.text
      FROM transcript_chunks_fts f
      JOIN transcript_chunks c ON c.id = f.rowid
      JOIN videos v ON v.video_id = c.video_id
      WHERE transcript_chunks_fts MATCH ?
      LIMIT ?
    ''', (query, MAX_RESULTS_PER_CATEGORY)).fetchall()

    per_video = defaultdict(int)
    candidates = []

    for row in rows:
        text = ' '.join((row['text'] or '').split())
        if len(text) < MIN_TEXT_LEN:
            continue
        if per_video[row['video_id']] >= MAX_PER_VIDEO_PER_CATEGORY:
            continue
        lowered = text.lower()
        score = 0
        for hint in CATEGORY_HINTS[category]:
            if hint in lowered:
                score += 1
        if score == 0:
            continue
        per_video[row['video_id']] += 1
        candidates.append({
            'category': category,
            'score': score,
            'video_id': row['video_id'],
            'title': row['title'],
            'chunk_id': row['chunk_id'],
            'chunk_index': row['chunk_index'],
            'text': text,
        })

    candidates.sort(key=lambda x: (-x['score'], x['video_id'], x['chunk_index']))
    out_path = OUT_DIR / f'{category}.json'
    out_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding='utf-8')
    all_summary[category] = {
        'count': len(candidates),
        'videos': len({c['video_id'] for c in candidates}),
        'path': str(out_path),
    }

summary_path = OUT_DIR / 'summary.json'
summary_path.write_text(json.dumps(all_summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(all_summary, ensure_ascii=False, indent=2))
print('OUT_DIR', OUT_DIR)
