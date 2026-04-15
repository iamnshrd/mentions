#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

TARGETS = {
    'OypmGZ9IJb4',   # $100k Profit on Mention Markets with @nathanmeininger
    'j9GyEcdlHR4',   # TRUMP CABINET MEETING
    'nTYUc3U57yc',   # TRUMP SPECIAL ANNOUNCEMENT
    'oEac6LNhGrU',   # TRUMP ANNOUNCEMENT
    'PpOxlt3t2o8',   # TRUMP SAUDI ARABIA, ACKMAN SPACE, MORE
    '5fMdpV0HWz0',   # 2025 ELECTION NIGHT STREAM
    '1_h3-mHlqTE',   # QUOTING KALSHI COMBOS LIVE - VibeCoding
}

def now():
    return datetime.now(timezone.utc).isoformat()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_ts = now()

chunk_map = {}
for row in conn.execute(f"select id, video_id, chunk_index from transcript_chunks where video_id in ({','.join(['?']*len(TARGETS))})", tuple(TARGETS)):
    chunk_map[(row['video_id'], row['chunk_index'])] = row['id']

# ----- helpers -----
def upsert_named(table, key_field, payload):
    row = conn.execute(f"SELECT id FROM {table} WHERE {key_field}=?", (payload[key_field],)).fetchone()
    cols = [k for k in payload.keys() if k != 'id']
    if row:
        set_parts = [f"{c}=?" for c in cols if c != key_field]
        values = [payload[c] for c in cols if c != key_field] + [now_ts, row['id']]
        conn.execute(f"UPDATE {table} SET {', '.join(set_parts)}, updated_at=? WHERE id=?", values)
        return row['id'], False
    insert_cols = cols + ['created_at', 'updated_at']
    insert_vals = [payload[c] for c in cols] + [now_ts, now_ts]
    cur = conn.execute(f"INSERT INTO {table} ({', '.join(insert_cols)}) VALUES ({','.join(['?']*len(insert_cols))})", insert_vals)
    return cur.lastrowid, True

def upsert_sizing(payload):
    row = conn.execute("SELECT id FROM sizing_lessons WHERE lesson_text=?", (payload['lesson_text'],)).fetchone()
    if row:
        conn.execute("UPDATE sizing_lessons SET lesson_type=?, description=?, applies_to=?, risk_note=?, updated_at=? WHERE id=?",
                     (payload['lesson_type'], payload['description'], payload['applies_to'], payload['risk_note'], now_ts, row['id']))
        return row['id'], False
    cur = conn.execute("INSERT INTO sizing_lessons (lesson_text, lesson_type, description, applies_to, risk_note, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                       (payload['lesson_text'], payload['lesson_type'], payload['description'], payload['applies_to'], payload['risk_note'], now_ts, now_ts))
    return cur.lastrowid, True

def ensure_link(table, left_field, right_field, left_id, right_id):
    exists = conn.execute(f"SELECT 1 FROM {table} WHERE {left_field}=? AND {right_field}=?", (left_id, right_id)).fetchone()
    if not exists:
        conn.execute(f"INSERT INTO {table} ({left_field}, {right_field}) VALUES (?,?)", (left_id, right_id))
        return True
    return False

added = {
    'market_archetypes': 0,
    'event_formats': 0,
    'execution_patterns': 0,
    'pricing_signals': 0,
    'sizing_lessons': 0,
    'phase_logic': 0,
    'decision_cases': 0,
    'case_principles': 0,
    'case_anti_patterns': 0,
    'case_pricing_signals': 0,
    'case_execution_patterns': 0,
}

market_archetypes = [
    {
        'name': 'open-vs-closed-press-misread-mentions',
        'archetype_type': 'mentions',
        'description': 'Political mention markets where crowd overweights the scheduled setup label (open press / closed press) and underweights real-time current-event override risk.',
        'pricing_drivers': 'event setup label, live agenda changes, current narrative urgency, speaker disposition',
        'common_edges': 'fade setup overreaction, reassess after the first minutes of remarks, keep Q&A path optionality alive',
        'common_traps': 'assuming open/closed press labels mechanically determine every strike',
        'liquidity_profile': 'high on Trump events',
        'repeatability': 'high',
    },
    {
        'name': 'manual-orderbook-execution-markets',
        'archetype_type': 'execution',
        'description': 'Markets where edge comes from manual speed, RFQ/limit quoting, and orderbook shape rather than only fundamental prediction.',
        'pricing_drivers': 'queue position, spread width, stale quotes, review-step friction, public orderbook behavior',
        'common_edges': 'maker-first entries, queue priority, reacting to stale books faster than crowd',
        'common_traps': 'blind market-taking, ignoring adverse selection, overautomating bad logic',
        'liquidity_profile': 'varies widely',
        'repeatability': 'high',
    },
]

for payload in market_archetypes:
    _, created = upsert_named('market_archetypes', 'name', payload)
    if created:
        added['market_archetypes'] += 1

formats = [
    {
        'format_name': 'trump-announcement-with-setup-fud',
        'domain': 'politics',
        'description': 'Trump announcement where market anchors heavily to pre-event setup cues like open press / closed press, often too aggressively.',
        'has_prepared_remarks': 1,
        'has_qna': 1,
        'qna_probability': 'uncertain but often misread',
        'usual_market_effects': 'setup labels move prices too much relative to actual path structure',
        'format_risk_notes': 'current events can blow through setup assumptions instantly',
    },
    {
        'format_name': 'manual-quoting-market',
        'domain': 'general',
        'description': 'Orderbook-driven market where queue position, maker discipline, and execution mechanics materially affect realized edge.',
        'has_prepared_remarks': 0,
        'has_qna': 0,
        'qna_probability': 'none',
        'usual_market_effects': 'realized EV differs from theoretical EV depending on fill quality and speed',
        'format_risk_notes': 'small UI frictions and quote management details matter more than people expect',
    },
]

format_ids = {}
for payload in formats:
    rid, created = upsert_named('event_formats', 'format_name', payload)
    format_ids[payload['format_name']] = rid
    if created:
        added['event_formats'] += 1

execution_patterns = [
    {
        'pattern_name': 'maker-first-unless-edge-is-decaying',
        'execution_type': 'entry',
        'description': 'Prefer passive entry for price quality, but switch to aggressive execution when the market is visibly moving away and waiting costs more than spread.',
        'best_used_when': 'liquidity exists but edge is time-sensitive',
        'avoid_when': 'you are just chasing without a thesis or the move is already mostly spent',
        'risk_note': 'aggressive entry without a decaying-edge reason turns into pure overpaying',
        'example_video_id': 'OypmGZ9IJb4',
        'example_chunk_id': chunk_map[('OypmGZ9IJb4', 19)],
    },
    {
        'pattern_name': 'quote-where-ui-friction-gives-you-edge',
        'execution_type': 'market_making',
        'description': 'Exploit markets where manual review steps, bad UI, or quote-management friction slow other traders more than they slow you.',
        'best_used_when': 'manual orderbooks, RFQ-like setups, combo quoting, thin but active books',
        'avoid_when': 'competition is fully automated or your own process is too slow to manage inventory',
        'risk_note': 'execution edge disappears if your quote discipline breaks under fast conditions',
        'example_video_id': '1_h3-mHlqTE',
        'example_chunk_id': chunk_map[('1_h3-mHlqTE', 10)],
    },
    {
        'pattern_name': 'separate-setup-signal-from-true-path',
        'execution_type': 'entry',
        'description': 'Treat open-press/closed-press labels as one input, not the whole model. Rebuild fair value from actual event path and current context.',
        'best_used_when': 'Trump events, briefing-like setups, setup-label-driven crowd behavior',
        'avoid_when': 'the setup cue is backed by hard mechanical constraints rather than fuzzy expectation',
        'risk_note': 'if you fade setup labels mechanically, you just become the mirror-image overreactor',
        'example_video_id': 'j9GyEcdlHR4',
        'example_chunk_id': chunk_map[('j9GyEcdlHR4', 20)],
    },
]

execution_ids = {}
for payload in execution_patterns:
    rid, created = upsert_named('execution_patterns', 'pattern_name', payload)
    execution_ids[payload['pattern_name']] = rid
    if created:
        added['execution_patterns'] += 1

pricing_signals = [
    {
        'signal_name': 'setup-label-overreaction',
        'signal_type': 'public_flow',
        'description': 'The market is moving too hard off open/closed press or similar setup labels without enough adjustment for current-event override and actual path structure.',
        'interpretation': 'the crowd is pricing a shorthand cue, not the real event tree',
        'typical_action': 'discount the setup cue and rebuild probabilities from actual likely phases and news context',
        'confidence': 0.88,
    },
    {
        'signal_name': 'maker-quality-beats-theoretical-ev',
        'signal_type': 'microstructure',
        'description': 'The main edge is not just having the right fair value but actually getting the fills before the market moves.',
        'interpretation': 'realized EV depends heavily on quote quality and queue priority',
        'typical_action': 'optimize entry mechanics before increasing directional aggression',
        'confidence': 0.83,
    },
    {
        'signal_name': 'bond-capital-lockup-tradeoff',
        'signal_type': 'capital_allocation',
        'description': 'A bond-like trade may be profitable in isolation but still inferior if it ties up capital that could be used in higher-ROI recurring edge.',
        'interpretation': 'expected value must be judged against capital efficiency, not only correctness',
        'typical_action': 'compare bond-like returns against opportunity cost in faster, higher-edge markets',
        'confidence': 0.82,
    },
]

signal_ids = {}
for payload in pricing_signals:
    rid, created = upsert_named('pricing_signals', 'signal_name', payload)
    signal_ids[payload['signal_name']] = rid
    if created:
        added['pricing_signals'] += 1

sizing_lessons = [
    {
        'lesson_text': 'Capital allocation matters: even profitable bond-like trades can be suboptimal if they crowd out faster, higher-ROI recurring edges.',
        'lesson_type': 'capital_allocation',
        'description': 'Sizing is not only about conviction in one trade; it is also about preserving bankroll for repeated high-edge setups.',
        'applies_to': 'mentions traders balancing bond-like positions versus faster recurring opportunities',
        'risk_note': 'overcommitting to slow low-volatility trades can quietly lower total portfolio growth',
    },
    {
        'lesson_text': 'When realized edge depends on fills, bet sizing should track execution quality, not just your paper fair value.',
        'lesson_type': 'execution_adjusted_sizing',
        'description': 'A theoretically great trade may deserve less size if you consistently enter late or get bad fills relative to the modeled price.',
        'applies_to': 'manual orderbooks, live events, RFQ-style execution',
        'risk_note': 'paper EV without fill realism leads to phantom confidence and oversized positions',
    },
]

for payload in sizing_lessons:
    _, created = upsert_sizing(payload)
    if created:
        added['sizing_lessons'] += 1

phase_rows = [
    {
        'phase_name': 'setup-fud-phase',
        'event_format_id': format_ids['trump-announcement-with-setup-fud'],
        'description': 'Pre-event and opening minutes where setup labels dominate trader psychology more than actual event evidence.',
        'what_becomes_more_likely': 'pricing driven by roll call, setup notes, and crowd narratives about press openness',
        'what_becomes_less_likely': 'careful path-by-path pricing from live evidence',
        'common_pricing_errors': 'too much movement from open/closed press shorthand alone',
        'execution_notes': 'avoid inheriting crowd shorthand; reassess after first live evidence about whether detours and questions are real',
    },
]

for payload in phase_rows:
    row = conn.execute('SELECT id FROM phase_logic WHERE phase_name=? AND event_format_id=?', (payload['phase_name'], payload['event_format_id'])).fetchone()
    if row:
        conn.execute('UPDATE phase_logic SET description=?, what_becomes_more_likely=?, what_becomes_less_likely=?, common_pricing_errors=?, execution_notes=?, updated_at=? WHERE id=?',
                     (payload['description'], payload['what_becomes_more_likely'], payload['what_becomes_less_likely'], payload['common_pricing_errors'], payload['execution_notes'], now_ts, row['id']))
    else:
        conn.execute('INSERT INTO phase_logic (phase_name, event_format_id, description, what_becomes_more_likely, what_becomes_less_likely, common_pricing_errors, execution_notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                     (payload['phase_name'], payload['event_format_id'], payload['description'], payload['what_becomes_more_likely'], payload['what_becomes_less_likely'], payload['common_pricing_errors'], payload['execution_notes'], now_ts, now_ts))
        added['phase_logic'] += 1

principles = {r['heuristic_text']: r['id'] for r in conn.execute('select id, heuristic_text from heuristics')}
anti_patterns = {r['pattern_text']: r['id'] for r in conn.execute('select id, pattern_text from anti_patterns')}

# Create two explicit batch2 cases.
case_specs = [
    {
        'video_id': 'OypmGZ9IJb4',
        'chunk_index': 19,
        'market_context': 'Mention-market execution when obvious edge is moving away faster than passive orders are getting filled.',
        'setup': 'Trader preferred limit-order discipline but recognized some spots where waiting for passive fills meant never getting enough exposure.',
        'decision': 'Start passive, but switch aggressive once it is clear the edge is decaying faster than fill quality can compensate.',
        'reasoning': 'Execution is part of fair value. Missing the trade entirely can be worse than paying some spread when the move is obvious and short-lived.',
        'risk_note': 'This is not permission to chase every move; the key condition is genuine decaying edge, not simple FOMO.',
        'outcome_note': 'Useful refinement of the usual “always be passive” instinct.',
        'tags': 'execution,mentions,passive-vs-aggressive,entry-quality',
    },
    {
        'video_id': 'j9GyEcdlHR4',
        'chunk_index': 20,
        'market_context': 'Trump mention markets where open/closed press labeling strongly moves prices before the event.',
        'setup': 'The crowd treats setup labels as near-deterministic signals, but real event path and current-news urgency often dominate the eventual distribution.',
        'decision': 'Fade pure setup-label overreaction and rebuild the tree from live path, current narrative, and whether Q&A or detours are actually opening up.',
        'reasoning': 'Setup cues matter, but they are one variable among many. Market shorthand often turns them into a false certainty.',
        'risk_note': 'Blindly fading setup labels is also wrong; the trade only works when crowd reaction exceeds what the setup actually implies.',
        'outcome_note': 'Transforms setup interpretation from binary lore into probabilistic event-structure work.',
        'tags': 'trump,setup-fud,open-press,closed-press,q&a,event-structure',
    },
]

case_ids = {}
for spec in case_specs:
    chunk_id = chunk_map[(spec['video_id'], spec['chunk_index'])]
    row = conn.execute('SELECT id FROM decision_cases WHERE video_id=? AND chunk_id=? AND decision=?', (spec['video_id'], chunk_id, spec['decision'])).fetchone()
    if row:
        cid = row['id']
    else:
        cur = conn.execute('INSERT INTO decision_cases (video_id, chunk_id, market_context, setup, decision, reasoning, risk_note, outcome_note, tags, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (spec['video_id'], chunk_id, spec['market_context'], spec['setup'], spec['decision'], spec['reasoning'], spec['risk_note'], spec['outcome_note'], spec['tags'], now_ts))
        cid = cur.lastrowid
        added['decision_cases'] += 1
    case_ids[(spec['video_id'], spec['chunk_index'])] = cid

# Link created cases.
case1 = case_ids[('OypmGZ9IJb4', 19)]
if ensure_link('case_execution_patterns', 'case_id', 'execution_pattern_id', case1, execution_ids['maker-first-unless-edge-is-decaying']):
    added['case_execution_patterns'] += 1
if ensure_link('case_pricing_signals', 'case_id', 'pricing_signal_id', case1, signal_ids['maker-quality-beats-theoretical-ev']):
    added['case_pricing_signals'] += 1
if 'When price and timing both favor you, it can be correct to take aggressively rather than wait for perfect passive fills.' in principles:
    if ensure_link('case_principles', 'case_id', 'heuristic_id', case1, principles['When price and timing both favor you, it can be correct to take aggressively rather than wait for perfect passive fills.']):
        added['case_principles'] += 1

case2 = case_ids[('j9GyEcdlHR4', 20)]
if ensure_link('case_execution_patterns', 'case_id', 'execution_pattern_id', case2, execution_ids['separate-setup-signal-from-true-path']):
    added['case_execution_patterns'] += 1
if ensure_link('case_pricing_signals', 'case_id', 'pricing_signal_id', case2, signal_ids['setup-label-overreaction']):
    added['case_pricing_signals'] += 1
if 'As the market gets sharper, edge often comes from one extra layer of context beyond what the crowd already checked.' in principles:
    if ensure_link('case_principles', 'case_id', 'heuristic_id', case2, principles['As the market gets sharper, edge often comes from one extra layer of context beyond what the crowd already checked.']):
        added['case_principles'] += 1
if 'Modeling a strike in isolation when its real path depends on event format or Q&A structure.' in anti_patterns:
    if ensure_link('case_anti_patterns', 'case_id', 'anti_pattern_id', case2, anti_patterns['Modeling a strike in isolation when its real path depends on event format or Q&A structure.']):
        added['case_anti_patterns'] += 1

# Link older capital-allocation case if present.
for row in conn.execute("select id, video_id, decision from decision_cases where video_id='5tNFwH2n5BA'"):
    if ensure_link('case_pricing_signals', 'case_id', 'pricing_signal_id', row['id'], signal_ids['bond-capital-lockup-tradeoff']):
        added['case_pricing_signals'] += 1

conn.commit()
print('ADDED', added)
for table in [
    'market_archetypes',
    'event_formats',
    'execution_patterns',
    'pricing_signals',
    'sizing_lessons',
    'phase_logic',
    'decision_cases',
    'case_principles',
    'case_anti_patterns',
    'case_pricing_signals',
    'case_execution_patterns',
]:
    print(table, conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
