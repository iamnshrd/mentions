#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

def now():
    return datetime.now(timezone.utc).isoformat()

SEEDS = [
    {
        'heuristic_text': 'Reprice immediately when the event frame changes. A structural update (special guest, topic shift, setup change) can invalidate the old market surface before the speech even starts.',
        'heuristic_type': 'timing_setup_shift',
        'market_type': 'mentions',
        'confidence': 0.87,
        'notes': 'The key edge is reacting faster than the market when the event context changes before the actual remarks begin.',
        'evidence': [
            {
                'video_id': '7G7qFsIQPg0',
                'chunk_id': 4415,
                'quote_text': 'When Karoline tweeted a very special guest, the vibes were immediately that it was Trump, so all the existing odds needed to be adjusted and he slammed a ton of no shares before the correction.',
                'evidence_strength': 0.97,
                'context_note': 'Direct example of pre-speech structural reprice from new information.'
            },
            {
                'video_id': '0SQ1N4o2cLQ',
                'chunk_id': 3719,
                'quote_text': 'He explicitly says there is a lot going on that Karoline can cover today and adjusts his comfort with a stock-market strike after the S&P reversed before the briefing.',
                'evidence_strength': 0.78,
                'context_note': 'Shows repricing a setup when background conditions change before the event.'
            }
        ]
    },
    {
        'heuristic_text': 'Wait as late as practical to enter when timing itself creates edge. For fast event markets, getting closer to the actual start can give better information and still enough liquidity.',
        'heuristic_type': 'timing_entry',
        'market_type': 'mentions',
        'confidence': 0.8,
        'notes': 'He often contrasts disciplined late entry with early accumulation when information quality improves near start time.',
        'evidence': [
            {
                'video_id': '-nyL4CW0AMQ',
                'chunk_id': 3568,
                'quote_text': 'He says other people accumulated a week out, but he took the disciplined approach to wait until roughly 30 minutes before game time and all the fills came through quickly.',
                'evidence_strength': 0.93,
                'context_note': 'Clear statement that waiting closer to the event improved his execution and information quality.'
            },
            {
                'video_id': '4lDIrQ-_WuY',
                'chunk_id': 4112,
                'quote_text': 'He uses room/setup information before the speech starts to infer there is an extremely low chance of Q&A, which affects which strikes are worth holding.',
                'evidence_strength': 0.79,
                'context_note': 'Shows why late pre-event information can materially improve pricing.'
            }
        ]
    },
    {
        'heuristic_text': 'Use venue, format, and stream setup as predictive features. Where the speech happens and whether Q&A is likely materially changes mention probabilities.',
        'heuristic_type': 'setup_features',
        'market_type': 'mentions',
        'confidence': 0.85,
        'notes': 'Not just topic matters; room, event type, whether questions are expected, and livestream format are part of the model.',
        'evidence': [
            {
                'video_id': '4lDIrQ-_WuY',
                'chunk_id': 4112,
                'quote_text': 'East Room historically does not have Q&A, so he uses that as a strong reason to expect a narrower set of possible mentions.',
                'evidence_strength': 0.95,
                'context_note': 'Very explicit use of venue/format as a predictive variable.'
            },
            {
                'video_id': '4eXmc82qnPs',
                'chunk_id': 4051,
                'quote_text': 'He says JD Vance speeches are hard to price because they happen less often, meaning sparse format-specific historicals reduce confidence.',
                'evidence_strength': 0.63,
                'context_note': 'Supports the idea that event format frequency and comparable history matter.'
            }
        ]
    },
    {
        'heuristic_text': 'As the event goes live, liquidity often disappears and wide spreads themselves become information. Pulling or avoiding stale orders near start is part of risk management.',
        'heuristic_type': 'live_liquidity',
        'market_type': 'mentions',
        'confidence': 0.88,
        'notes': 'He repeatedly talks about spread widening, order risk, and the danger of being picked off right as the event begins.',
        'evidence': [
            {
                'video_id': '6gNeabkXq8k',
                'chunk_id': 4357,
                'quote_text': 'As the event starts, liquidity dries up because people pull their orders; if Powell says your word while your order is still up, someone will fill you instantly.',
                'evidence_strength': 0.98,
                'context_note': 'Direct live-trading risk rule for mentions markets.'
            },
            {
                'video_id': '1_h3-mHlqTE',
                'chunk_id': 3882,
                'quote_text': 'For early markets, as soon as you put in a limit order with size, market makers may move the market against you.',
                'evidence_strength': 0.81,
                'context_note': 'Supports execution/liquidity sensitivity around live quoting.'
            }
        ]
    },
    {
        'heuristic_text': 'When a keyword or event has already half-triggered, use the live sequence rather than the static market. Partial progression can create temporary mispricing and dispute risk.',
        'heuristic_type': 'live_sequence',
        'market_type': 'mentions',
        'confidence': 0.77,
        'notes': 'This is a more advanced mentions pattern: exploit the live path of the event, but stay aware of disputes and incomplete triggers.',
        'evidence': [
            {
                'video_id': '0LssiD1TVdM',
                'chunk_id': 3685,
                'quote_text': 'When Bad Bunny started coming close to singing, he got favorable fills and then sold because he thought the market might dispute whether the trigger was complete.',
                'evidence_strength': 0.9,
                'context_note': 'Strong example of trading the sequence, not just the final binary outcome.'
            },
            {
                'video_id': '6gNeabkXq8k',
                'chunk_id': 4358,
                'quote_text': 'Buying at 99 after a word is said can still carry dispute risk because some markets later flip if the trigger is judged differently.',
                'evidence_strength': 0.88,
                'context_note': 'Live-sequence trading remains exposed to resolution risk.'
            }
        ]
    }
]

conn=sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_ts = now()

for seed in SEEDS:
    row = conn.execute('SELECT id FROM heuristics WHERE heuristic_text = ?', (seed['heuristic_text'],)).fetchone()
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
print('Seeded heuristics total:', conn.execute('SELECT COUNT(*) FROM heuristics').fetchone()[0])
print('Seeded evidence total:', conn.execute('SELECT COUNT(*) FROM heuristic_evidence').fetchone()[0])
for row in conn.execute('SELECT id, heuristic_type, substr(heuristic_text,1,100) as t FROM heuristics ORDER BY id'):
    print(dict(row))
