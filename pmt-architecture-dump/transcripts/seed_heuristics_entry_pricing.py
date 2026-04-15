#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

def now():
    return datetime.now(timezone.utc).isoformat()

SEEDS = [
    {
        'heuristic_text': 'Price matters more than the binary outcome. Treat the same strike very differently depending on entry price; avoid copying a trade at a much worse fill.',
        'heuristic_type': 'entry_pricing',
        'market_type': 'mentions',
        'confidence': 0.86,
        'notes': 'Core repeated theme: edge comes from entry price, not from whether the event sounds plausible in the abstract.',
        'evidence': [
            {
                'video_id': '-nyL4CW0AMQ',
                'chunk_id': 3565,
                'quote_text': 'If you are profiting over a long period of time, it is because of price. All you really care about is price.',
                'evidence_strength': 0.95,
                'context_note': 'Explicit statement that long-run edge comes from price, not binary lock thinking.'
            },
            {
                'video_id': '0SQ1N4o2cLQ',
                'chunk_id': 3724,
                'quote_text': 'If you are going to buy no shutdown at 34 cents, that is a totally different story from me getting in at 21 cents.',
                'evidence_strength': 0.93,
                'context_note': 'Direct warning against copying a trade without matching the original fill.'
            }
        ]
    },
    {
        'heuristic_text': 'Prefer limit orders and maker-style execution. Resting bids at good prices are a persistent edge in mentions markets.',
        'heuristic_type': 'execution',
        'market_type': 'mentions',
        'confidence': 0.88,
        'notes': 'Execution quality itself is treated as alpha, especially in wide-spread or illiquid markets.',
        'evidence': [
            {
                'video_id': '-1iqA98SSV0',
                'chunk_id': 3510,
                'quote_text': 'Limit order is alpha.',
                'evidence_strength': 0.98,
                'context_note': 'Blunt explicit statement of the execution principle.'
            },
            {
                'video_id': '0f3Bws_klco',
                'chunk_id': 3756,
                'quote_text': 'You should literally always do limit orders. You should never buy in dollars. If you use limit orders, you can be a maker and avoid paying trading fees.',
                'evidence_strength': 0.97,
                'context_note': 'Detailed execution advice: use limits, prefer maker fills, avoid blind market buying.'
            }
        ]
    },
    {
        'heuristic_text': 'Anchor fair value using adjacent or correlated market information. If related strikes or similar markets imply a different probability, use that discrepancy as an edge.',
        'heuristic_type': 'relative_value',
        'market_type': 'mentions',
        'confidence': 0.8,
        'notes': 'He repeatedly reasons from neighboring strikes, similar events, or component markets to estimate fair value.',
        'evidence': [
            {
                'video_id': '06uPhPipp5w',
                'chunk_id': 3606,
                'quote_text': 'Farmer over milk makes sense because he can easily talk about farmers without talking about milk, but he cannot talk about milk without talking about farmers.',
                'evidence_strength': 0.86,
                'context_note': 'Uses logical relation between strikes to justify spread/fair value.'
            },
            {
                'video_id': '0LssiD1TVdM',
                'chunk_id': 3685,
                'quote_text': 'When the individual markets for the awards implied only a tiny chance of one win, getting no on the aggregate award count at 80 cents was obviously a strong price.',
                'evidence_strength': 0.84,
                'context_note': 'Uses component markets to price a related aggregate market.'
            }
        ]
    },
    {
        'heuristic_text': 'Do not chase steamed prices just because the underlying thesis still sounds right. A correct idea can still be a bad trade once the price is too rich.',
        'heuristic_type': 'anti_chase',
        'market_type': 'mentions',
        'confidence': 0.84,
        'notes': 'He distinguishes between liking the narrative and liking the current odds; often references overbought conditions.',
        'evidence': [
            {
                'video_id': '0f3Bws_klco',
                'chunk_id': 3754,
                'quote_text': 'I got in on ballroom at 39 cents. I do not know if I would recommend getting into this at 75 cents.',
                'evidence_strength': 0.95,
                'context_note': 'Classic anti-chase framing: same idea, different trade depending on price.'
            },
            {
                'video_id': '-1iqA98SSV0',
                'chunk_id': 3510,
                'quote_text': 'I will short that at 60 cents. There are things that could point to her bringing it up, but I just think it is overbought.',
                'evidence_strength': 0.88,
                'context_note': 'Explicit statement that a plausible strike can still be overpriced.'
            }
        ]
    },
    {
        'heuristic_text': 'Scale into positions instead of slamming one giant order, especially in thinner markets. Gradual sizing improves fills and reveals where the market really trades.',
        'heuristic_type': 'sizing_execution',
        'market_type': 'mentions',
        'confidence': 0.78,
        'notes': 'He prefers smaller layered orders to avoid telegraphing size and to reduce being penny-jumped.',
        'evidence': [
            {
                'video_id': '0SQ1N4o2cLQ',
                'chunk_id': 3722,
                'quote_text': 'I do kind of try to size in with smaller orders here and there. If you put a giant limit order, people just penny jump you naturally.',
                'evidence_strength': 0.91,
                'context_note': 'Direct execution/sizing guidance for illiquid order books.'
            },
            {
                'video_id': '-1iqA98SSV0',
                'chunk_id': 3509,
                'quote_text': 'I tried to buy more. I was only able to get 300 shares at 31 cents.',
                'evidence_strength': 0.61,
                'context_note': 'Shows practical fill-constrained sizing in action.'
            }
        ]
    }
]

conn=sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_ts = now()

for seed in SEEDS:
    row = conn.execute(
        'SELECT id FROM heuristics WHERE heuristic_text = ?',
        (seed['heuristic_text'],)
    ).fetchone()
    if row:
        heuristic_id = row['id']
        conn.execute('''
            UPDATE heuristics
            SET heuristic_type=?, market_type=?, confidence=?, notes=?, updated_at=?
            WHERE id=?
        ''', (seed['heuristic_type'], seed['market_type'], seed['confidence'], seed['notes'], now_ts, heuristic_id))
    else:
        cur = conn.execute('''
            INSERT INTO heuristics (heuristic_text, heuristic_type, market_type, confidence, recurring_count, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?)
        ''', (seed['heuristic_text'], seed['heuristic_type'], seed['market_type'], seed['confidence'], seed['notes'], now_ts, now_ts))
        heuristic_id = cur.lastrowid
    conn.execute('DELETE FROM heuristic_evidence WHERE heuristic_id = ?', (heuristic_id,))
    for ev in seed['evidence']:
        conn.execute('''
            INSERT INTO heuristic_evidence (heuristic_id, video_id, chunk_id, quote_text, evidence_strength, context_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (heuristic_id, ev['video_id'], ev['chunk_id'], ev['quote_text'], ev['evidence_strength'], ev['context_note'], now_ts))

conn.commit()
print('Seeded heuristics:', conn.execute('SELECT COUNT(*) FROM heuristics').fetchone()[0])
print('Seeded evidence:', conn.execute('SELECT COUNT(*) FROM heuristic_evidence').fetchone()[0])
for row in conn.execute('SELECT id, heuristic_type, substr(heuristic_text,1,120) FROM heuristics ORDER BY id'):
    print(row)
