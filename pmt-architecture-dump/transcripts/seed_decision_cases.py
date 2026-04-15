#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

def now():
    return datetime.now(timezone.utc).isoformat()

CASES = [
    {
        'video_id': '7G7qFsIQPg0',
        'chunk_id': 4415,
        'market_context': 'Karoline Leavitt mention market / special guest press briefing before remarks began.',
        'setup': 'A pre-event tweet announced a very special guest. Existing Karoline market prices were still based on the old assumption set.',
        'decision': 'Immediately slam no shares across the old Karoline mention surface because a Trump appearance would radically alter mention probabilities.',
        'reasoning': 'The event frame changed before the speech started. Once Trump became the most likely guest, the old odds were stale and should be repriced fast.',
        'risk_note': 'Could be wrong if the guest was not Trump or if the market had already fully adjusted.',
        'outcome_note': 'He sold out after prices corrected and noted he maybe could have made even more.',
        'tags': 'mentions,timing,setup-shift,pre-event,repricing'
    },
    {
        'video_id': '-nyL4CW0AMQ',
        'chunk_id': 3568,
        'market_context': 'NFL announcer mention markets around the Super Bowl.',
        'setup': 'Many traders accumulated positions a week early, but game-day order flow and information quality improved close to start.',
        'decision': 'Wait until roughly 30 minutes before game time to accumulate instead of buying a week out.',
        'reasoning': 'Late entry preserved flexibility, improved information, and still allowed fills because volume exploded near kickoff.',
        'risk_note': 'Waiting too long can miss good prices if the market moves before you get size.',
        'outcome_note': 'He says the fills came through quickly and he was glad he waited.',
        'tags': 'timing,entry,discipline,sports,mentions'
    },
    {
        'video_id': '0f3Bws_klco',
        'chunk_id': 3754,
        'market_context': 'Trump EO signing; ballroom-related strike after a judge ruled against Trump ballroom expansion.',
        'setup': 'Fresh external news made ballroom salient, and he got in around 39-40 cents before the market steamed much higher.',
        'decision': 'Take a large yes position at low prices, but explicitly avoid recommending the same trade after it moved to ~75 cents.',
        'reasoning': 'The thesis could still be right while the trade quality deteriorated sharply as the price rose. Entry price determines EV.',
        'risk_note': 'The EO signing was unrelated to ballroom; Trump could still dodge the topic or not take questions.',
        'outcome_note': 'He viewed fair value as around 80 and leaned toward holding, but framed 75 as much less attractive than his original fill.',
        'tags': 'pricing,anti-chase,entry-price,trump,mentions'
    },
    {
        'video_id': '0LssiD1TVdM',
        'chunk_id': 3685,
        'market_context': 'Bad Bunny/Grammys-style live entertainment mention/trigger markets.',
        'setup': 'The event was partially progressing toward a trigger, creating temporary confusion and big intraday fills.',
        'decision': 'Buy during the partial trigger progression, then sell when the market got rich because of dispute risk.',
        'reasoning': 'Live sequence trading can create huge temporary edge before the market fully resolves whether the trigger was complete.',
        'risk_note': 'A dispute or surprise performance could flip the economics fast; partial triggers are not the same as clean resolution.',
        'outcome_note': 'He reports getting strong fills and exiting profitably rather than holding blindly.',
        'tags': 'live-sequence,dispute-risk,entertainment,mentions,timing'
    },
    {
        'video_id': '6gNeabkXq8k',
        'chunk_id': 4357,
        'market_context': 'Powell/Fed-style mention markets right as the event goes live.',
        'setup': 'Spreads widened and traders discussed pulling orders at the exact event start because stale resting orders become dangerous.',
        'decision': 'Respect wide live spreads and the fact that people pull orders right at go-live; avoid leaving vulnerable stale liquidity up.',
        'reasoning': 'If Powell says your word while your order is still posted, you get instantly picked off. Liquidity conditions themselves are part of the signal.',
        'risk_note': 'Being too cautious can also cause missed fills or missed edge if the market overreacts while you are flat.',
        'outcome_note': 'Used as a tactical example for why mentions liquidity behaves differently exactly at event start.',
        'tags': 'live-liquidity,powell,execution,mentions,spread-risk'
    }
]

conn=sqlite3.connect(DB)
now_ts = now()
for case in CASES:
    row = conn.execute('SELECT id FROM decision_cases WHERE video_id=? AND chunk_id=? AND decision=?', (case['video_id'], case['chunk_id'], case['decision'])).fetchone()
    if row:
        conn.execute('''
            UPDATE decision_cases
            SET market_context=?, setup=?, reasoning=?, risk_note=?, outcome_note=?, tags=?
            WHERE id=?
        ''', (case['market_context'], case['setup'], case['reasoning'], case['risk_note'], case['outcome_note'], case['tags'], row[0]))
    else:
        conn.execute('''
            INSERT INTO decision_cases (video_id, chunk_id, market_context, setup, decision, reasoning, risk_note, outcome_note, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (case['video_id'], case['chunk_id'], case['market_context'], case['setup'], case['decision'], case['reasoning'], case['risk_note'], case['outcome_note'], case['tags'], now_ts))
conn.commit()
print('decision_cases total:', conn.execute('SELECT COUNT(*) FROM decision_cases').fetchone()[0])
for row in conn.execute('SELECT id, video_id, substr(decision,1,90) FROM decision_cases ORDER BY id'):
    print(row)
