#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

def now():
    return datetime.now(timezone.utc).isoformat()

NEW_HEURISTICS = [
    {
        'heuristic_text': 'Historical comparables matter, but they must be adjusted for the current narrative environment instead of copied blindly.',
        'heuristic_type': 'comparables_adjustment',
        'market_type': 'mentions',
        'confidence': 0.76,
        'notes': 'He frequently starts from historical mention patterns, then adjusts for the current topic cluster or political environment.',
        'evidence': [
            ('-1iqA98SSV0', 3509, 'Healthcare historically centered on shutdown framing, so without a shutdown the current healthcare strike should be materially repriced lower.', 0.9, 'Uses historical mention context but adjusts for changed narrative environment.'),
            ('DYfdif2F-O0', 4875, 'He focuses on the last three correlated drug-price events to infer likely mentions for the current announcement.', 0.82, 'Explicit use of event comparables rather than generic intuition.'),
        ],
    },
    {
        'heuristic_text': 'High-probability “bond” markets deserve sizing only when the gap between market price and true resolution probability is still meaningful.',
        'heuristic_type': 'bond_mispricing',
        'market_type': 'prediction_markets',
        'confidence': 0.81,
        'notes': 'He treats 90-95 vs 99 as a major EV gap, but still insists on price discipline rather than automatic bond buying.',
        'evidence': [
            ('5tNFwH2n5BA', 4328, 'The most mispriced things are often 90-95 cent contracts that should be 99, and that small-looking difference is actually enormous in EV terms.', 0.95, 'Core bond-pricing principle.'),
            ('PpOxlt3t2o8', 5488, 'At 17 hours into the challenge, being able to still buy 97-cent shares looked like a real bond opportunity rather than a trivial edge.', 0.72, 'Example of bond-style thinking applied in practice.'),
        ],
    },
    {
        'heuristic_text': 'When event-specific context is weak, fall back to smaller size and wider uncertainty instead of forcing a confident price.',
        'heuristic_type': 'size_down_when_unclear',
        'market_type': 'mentions',
        'confidence': 0.74,
        'notes': 'He often reduces aggression when the event path is ambiguous or when he admits he is out of his element.',
        'evidence': [
            ('4lDIrQ-_WuY', 4112, 'He says he does not have big positions because prices moved and the exact path for the soccer meeting is still uncertain.', 0.83, 'Direct size reduction under uncertainty.'),
            ('4eXmc82qnPs', 4051, 'JD Vance speeches are hard to price, so he explicitly says he is a little out of his element trying to price them.', 0.79, 'Signals lower conviction sizing rather than fake certainty.'),
        ],
    },
]

NEW_ANTI = [
    {
        'pattern_text': 'Forcing oversized confidence in markets where the event type is rare or the comparable set is thin.',
        'why_bad': 'If you do not have enough reliable historical analogs, pretending to have a tight fair value is fake precision and usually leads to bad sizing.',
        'example_video_id': '4eXmc82qnPs',
        'example_chunk_id': 4051,
    },
    {
        'pattern_text': 'Using historical averages without checking whether the current narrative regime is different.',
        'why_bad': 'Historical mention frequencies can break when the event topic cluster changes, so naive copy-paste historical pricing is dangerous.',
        'example_video_id': '-1iqA98SSV0',
        'example_chunk_id': 3509,
    },
]

NEW_CASES = [
    {
        'video_id': 'DYfdif2F-O0',
        'chunk_id': 4875,
        'market_context': 'Trump special drug announcement with Eli Lilly / Novo Nordisk-related mention strikes.',
        'setup': 'Recent highly correlated drug-price events provided a comparable set and the market was still offering sub-95 prices on company-name mentions.',
        'decision': 'Load into the clearest name-linked strikes (especially Eli Lilly / Trump RX) because past correlated events and the explicit partnership context made the mentions highly likely.',
        'reasoning': 'When the event is directly tied to named counterparties and historical comparables show repeated explicit name mentions, high-probability yeses can still be undervalued.',
        'risk_note': 'Longer, more awkward names can still carry a little extra speech-friction risk; not every “obvious” name has identical mention probability.',
        'outcome_note': 'He distinguishes between stronger and weaker name mentions rather than blindly treating all involved companies as identical.',
        'tags': 'comparables,drug-event,high-probability,mentions'
    },
    {
        'video_id': '5tNFwH2n5BA',
        'chunk_id': 4328,
        'market_context': 'Portfolio-level use of bond-style prediction markets alongside high-ROI mentions trading.',
        'setup': 'Large cash balance plus access to high-probability contracts trading materially below true resolution probability.',
        'decision': 'Use bond-style contracts to park capital while reserving more liquid risk budget for high-ROI mentions trades.',
        'reasoning': 'Prediction market capital can be split between compounding low-risk bond mispricings and more volatile mention-market edge.',
        'risk_note': 'This only works if the “bond” is actually mispriced; buying high-probability contracts without a real edge just locks up capital for mediocre return.',
        'outcome_note': 'He explicitly frames this as portfolio construction rather than pure single-trade prediction.',
        'tags': 'portfolio,bonds,capital-allocation,mispricing'
    },
]

conn=sqlite3.connect(DB)
now_ts = now()

for seed in NEW_HEURISTICS:
    row = conn.execute('SELECT id FROM heuristics WHERE heuristic_text=?', (seed['heuristic_text'],)).fetchone()
    if row:
        hid=row[0]
        conn.execute('UPDATE heuristics SET heuristic_type=?, market_type=?, confidence=?, notes=?, updated_at=? WHERE id=?', (seed['heuristic_type'], seed['market_type'], seed['confidence'], seed['notes'], now_ts, hid))
    else:
        cur=conn.execute('INSERT INTO heuristics (heuristic_text, heuristic_type, market_type, confidence, recurring_count, notes, created_at, updated_at) VALUES (?,?,?,?,1,?,?,?)', (seed['heuristic_text'], seed['heuristic_type'], seed['market_type'], seed['confidence'], seed['notes'], now_ts, now_ts))
        hid=cur.lastrowid
    conn.execute('DELETE FROM heuristic_evidence WHERE heuristic_id=?', (hid,))
    for vid, chunk_id, quote, strength, note in seed['evidence']:
        conn.execute('INSERT INTO heuristic_evidence (heuristic_id, video_id, chunk_id, quote_text, evidence_strength, context_note, created_at) VALUES (?,?,?,?,?,?,?)', (hid, vid, chunk_id, quote, strength, note, now_ts))

for ap in NEW_ANTI:
    row = conn.execute('SELECT id FROM anti_patterns WHERE pattern_text=?', (ap['pattern_text'],)).fetchone()
    if row:
        conn.execute('UPDATE anti_patterns SET why_bad=?, example_video_id=?, example_chunk_id=?, updated_at=? WHERE id=?', (ap['why_bad'], ap['example_video_id'], ap['example_chunk_id'], now_ts, row[0]))
    else:
        conn.execute('INSERT INTO anti_patterns (pattern_text, why_bad, example_video_id, example_chunk_id, created_at, updated_at) VALUES (?,?,?,?,?,?)', (ap['pattern_text'], ap['why_bad'], ap['example_video_id'], ap['example_chunk_id'], now_ts, now_ts))

for case in NEW_CASES:
    row = conn.execute('SELECT id FROM decision_cases WHERE video_id=? AND chunk_id=? AND decision=?', (case['video_id'], case['chunk_id'], case['decision'])).fetchone()
    if row:
        conn.execute('UPDATE decision_cases SET market_context=?, setup=?, reasoning=?, risk_note=?, outcome_note=?, tags=? WHERE id=?', (case['market_context'], case['setup'], case['reasoning'], case['risk_note'], case['outcome_note'], case['tags'], row[0]))
    else:
        conn.execute('INSERT INTO decision_cases (video_id, chunk_id, market_context, setup, decision, reasoning, risk_note, outcome_note, tags, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)', (case['video_id'], case['chunk_id'], case['market_context'], case['setup'], case['decision'], case['reasoning'], case['risk_note'], case['outcome_note'], case['tags'], now_ts))

conn.commit()
print('heuristics', conn.execute('SELECT COUNT(*) FROM heuristics').fetchone()[0])
print('evidence', conn.execute('SELECT COUNT(*) FROM heuristic_evidence').fetchone()[0])
print('decision_cases', conn.execute('SELECT COUNT(*) FROM decision_cases').fetchone()[0])
print('anti_patterns', conn.execute('SELECT COUNT(*) FROM anti_patterns').fetchone()[0])
