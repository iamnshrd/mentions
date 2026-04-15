#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

def now():
    return datetime.now(timezone.utc).isoformat()

NEW_HEURISTICS = [
    {
        'heuristic_text': 'When price and timing both favor you, it can be correct to take aggressively rather than wait for perfect passive fills.',
        'heuristic_type': 'aggressive_take_when_edge_is_live',
        'market_type': 'mentions',
        'confidence': 0.75,
        'notes': 'Default is limit-order discipline, but he also recognizes moments when waiting for passive fills costs more than paying spread.',
        'evidence': [
            ('-1iqA98SSV0', 3514, 'He says for Leavitt he should have just hammered some things with market buys because the price kept moving away from him.', 0.86, 'Execution can be more aggressive when the edge is obviously decaying in real time.'),
            ('PpOxlt3t2o8', 5488, 'He had limit orders set for the Saudi speech but notes he could not accumulate much before the event.', 0.63, 'Shows the trade-off between ideal entry and actually getting exposure.'),
        ],
    },
    {
        'heuristic_text': 'Sparse or unusual event formats should be priced with wider uncertainty bands than repeatable briefings or speeches.',
        'heuristic_type': 'format_uncertainty',
        'market_type': 'mentions',
        'confidence': 0.79,
        'notes': 'He repeatedly distinguishes well-modeled repeated formats from weird one-offs.',
        'evidence': [
            ('4eXmc82qnPs', 4051, 'JD Vance speeches are a little hard to price because we do not get them that often.', 0.84, 'Direct statement that sparse historicals reduce confidence.'),
            ('4Js-KlhdsTA', 4015, 'New markets start largely unsolved and only become modelable after tightening from historicals and format-specific work.', 0.78, 'General principle for unfamiliar or under-modeled formats.'),
        ],
    },
    {
        'heuristic_text': 'If the market misreads whether Q&A is likely, that creates immediate edge on strikes whose only path is late questions.',
        'heuristic_type': 'qa_path_dependency',
        'market_type': 'mentions',
        'confidence': 0.83,
        'notes': 'A recurring theme is that some strikes only really become live through Q&A, so Q&A probability is a hidden driver of fair value.',
        'evidence': [
            ('4eXmc82qnPs', 4063, 'People thought there would not be a Q&A, which made certain strikes get absurdly cheap even though trillion was highly likely if Q&A happened.', 0.94, 'Strong direct example of Q&A probability mispricing a strike.'),
            ('4lDIrQ-_WuY', 4114, 'Given the East Room setup and low Q&A odds, Iran-related strikes should lose value unless Trump goes off-topic immediately.', 0.82, 'Shows how Q&A path dependency changes pricing before the event.'),
        ],
    },
    {
        'heuristic_text': 'For small portfolios, simple microstructure edge can beat deep prediction: snipe obvious mispriced bids/offers instead of trying to forecast the whole event.',
        'heuristic_type': 'microstructure_over_prediction',
        'market_type': 'mentions',
        'confidence': 0.77,
        'notes': 'He explicitly says beginners can grow by exploiting bad live quotes and market-making behavior rather than heroic prediction.',
        'evidence': [
            ('zRCmG7F48N4', 7699, 'With a tiny portfolio it is unbelievably easy to profit by putting bids at dumb levels and selling quickly during live speeches.', 0.9, 'Directly frames early-stage edge as microstructure, not prediction.'),
            ('5tNFwH2n5BA', 4328, 'The most mispriced things are often 90-95 cent contracts that should really be 99, making a seemingly small price gap enormous in EV terms.', 0.81, 'Supports the idea that obvious structural mispricing matters more than fancy forecasting.'),
        ],
    },
]

NEW_ANTI = [
    {
        'pattern_text': 'Assuming a strike is bad just because it sounds unlikely, without checking whether the current price already overstates that unlikelihood.',
        'why_bad': 'Mention markets are not judged by plausibility alone. Even thin-probability paths can be good trades if the odds are cheap enough.',
        'example_video_id': '7pQihJ9lKxo',
        'example_chunk_id': 4507,
    },
    {
        'pattern_text': 'Modeling a strike in isolation when its real path depends on event format or Q&A structure.',
        'why_bad': 'Some words only become live through late-question paths. Ignoring format turns you into a bad price-taker on path-dependent strikes.',
        'example_video_id': '4lDIrQ-_WuY',
        'example_chunk_id': 4114,
    },
]

NEW_CASES = [
    {
        'video_id': '4eXmc82qnPs',
        'chunk_id': 4063,
        'market_context': 'JD Vance speech with widespread assumption there would be no Q&A.',
        'setup': 'The market aggressively discounted some question-dependent strikes because participants thought the speech format would end without questions.',
        'decision': 'Treat those strikes as underpriced and keep bids/positions because the Q&A path was much more alive than the market implied.',
        'reasoning': 'If Q&A happens, some late-topic words become drastically more likely, so prices that assume no Q&A are too cheap.',
        'risk_note': 'If Q&A truly never comes, those strikes can die fast and passive orders may never fill enough size.',
        'outcome_note': 'He explicitly says he should have done much better on this market because the opportunity was huge.',
        'tags': 'q&a,path-dependency,late-questions,mentions'
    },
    {
        'video_id': 'zRCmG7F48N4',
        'chunk_id': 7699,
        'market_context': 'Beginner/early-portfolio live mention trading strategy.',
        'setup': 'Small account size means fills are easy and the trader can exploit temporary dislocations during speeches.',
        'decision': 'Think like an exchange/market maker at first: buy obviously cheap yeses or mispriced live quotes and flip them rather than overfocusing on prediction.',
        'reasoning': 'With a tiny portfolio, the easiest edge is often microstructure and live quote dislocation, not having the deepest model of the event.',
        'risk_note': 'This approach breaks down as size grows because you start moving the market and getting worse adverse-selection dynamics.',
        'outcome_note': 'He frames this explicitly as a practical path to growing a small account.',
        'tags': 'beginners,microstructure,market-making,small-portfolio'
    }
]

conn=sqlite3.connect(DB)
now_ts = now()

for seed in NEW_HEURISTICS:
    row = conn.execute('SELECT id FROM heuristics WHERE heuristic_text=?', (seed['heuristic_text'],)).fetchone()
    if row:
        hid = row[0]
        conn.execute('UPDATE heuristics SET heuristic_type=?, market_type=?, confidence=?, notes=?, updated_at=? WHERE id=?',
                     (seed['heuristic_type'], seed['market_type'], seed['confidence'], seed['notes'], now_ts, hid))
    else:
        cur = conn.execute('INSERT INTO heuristics (heuristic_text, heuristic_type, market_type, confidence, recurring_count, notes, created_at, updated_at) VALUES (?,?,?,?,1,?,?,?)',
                           (seed['heuristic_text'], seed['heuristic_type'], seed['market_type'], seed['confidence'], seed['notes'], now_ts, now_ts))
        hid = cur.lastrowid
    conn.execute('DELETE FROM heuristic_evidence WHERE heuristic_id=?', (hid,))
    for vid, chunk_id, quote, strength, note in seed['evidence']:
        conn.execute('INSERT INTO heuristic_evidence (heuristic_id, video_id, chunk_id, quote_text, evidence_strength, context_note, created_at) VALUES (?,?,?,?,?,?,?)',
                     (hid, vid, chunk_id, quote, strength, note, now_ts))

for ap in NEW_ANTI:
    row = conn.execute('SELECT id FROM anti_patterns WHERE pattern_text=?', (ap['pattern_text'],)).fetchone()
    if row:
        conn.execute('UPDATE anti_patterns SET why_bad=?, example_video_id=?, example_chunk_id=?, updated_at=? WHERE id=?',
                     (ap['why_bad'], ap['example_video_id'], ap['example_chunk_id'], now_ts, row[0]))
    else:
        conn.execute('INSERT INTO anti_patterns (pattern_text, why_bad, example_video_id, example_chunk_id, created_at, updated_at) VALUES (?,?,?,?,?,?)',
                     (ap['pattern_text'], ap['why_bad'], ap['example_video_id'], ap['example_chunk_id'], now_ts, now_ts))

for case in NEW_CASES:
    row = conn.execute('SELECT id FROM decision_cases WHERE video_id=? AND chunk_id=? AND decision=?', (case['video_id'], case['chunk_id'], case['decision'])).fetchone()
    if row:
        conn.execute('UPDATE decision_cases SET market_context=?, setup=?, reasoning=?, risk_note=?, outcome_note=?, tags=? WHERE id=?',
                     (case['market_context'], case['setup'], case['reasoning'], case['risk_note'], case['outcome_note'], case['tags'], row[0]))
    else:
        conn.execute('INSERT INTO decision_cases (video_id, chunk_id, market_context, setup, decision, reasoning, risk_note, outcome_note, tags, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                     (case['video_id'], case['chunk_id'], case['market_context'], case['setup'], case['decision'], case['reasoning'], case['risk_note'], case['outcome_note'], case['tags'], now_ts))

conn.commit()
print('heuristics', conn.execute('SELECT COUNT(*) FROM heuristics').fetchone()[0])
print('evidence', conn.execute('SELECT COUNT(*) FROM heuristic_evidence').fetchone()[0])
print('decision_cases', conn.execute('SELECT COUNT(*) FROM decision_cases').fetchone()[0])
print('anti_patterns', conn.execute('SELECT COUNT(*) FROM anti_patterns').fetchone()[0])
