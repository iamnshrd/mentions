#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

TARGETS = {
    '4Js-KlhdsTA',   # THE FOSTER INTERVIEW
    'X7BkPL1e8vI',   # Interviewing @LoganPredicts $400K+ Profit
    'kW16V0BA7Lc',   # $1K to $30K in 1 Month on Kalshi
    'zRCmG7F48N4',   # MAMDANI SPEECH _ TRUMP CNBC INTERVIEW
    '4eXmc82qnPs',   # JD VANCE SPEECH
    '4lDIrQ-_WuY',   # likely event-format/Q&A case already used in prior extraction
    '5tNFwH2n5BA',   # bond/capital allocation references from prior extraction
    'DYfdif2F-O0',   # drug event comparables from prior extraction
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
    'case_principles': 0,
    'case_anti_patterns': 0,
    'case_pricing_signals': 0,
    'case_execution_patterns': 0,
}

# ----- v2 rows from batch1 older transcripts -----
market_archetypes = [
    {
        'name': 'rare-speaker-or-thin-history-mentions',
        'archetype_type': 'mentions',
        'description': 'Mention markets on speakers or formats that do not recur often enough for strong transcript baselines.',
        'pricing_drivers': 'event setup, narrative context, sparse historical analogs, Q&A expectations',
        'common_edges': 'uncertainty discounts, avoiding fake precision, selective small sizing',
        'common_traps': 'pretending thin-history markets deserve tight fair values',
        'liquidity_profile': 'medium',
        'repeatability': 'low to medium',
    },
    {
        'name': 'name-linked-policy-announcement-mentions',
        'archetype_type': 'mentions',
        'description': 'Policy or corporate announcements where directly involved named counterparties have much higher mention probability than generic topic words.',
        'pricing_drivers': 'named counterparties, explicit partnership structure, recent comparables, announcement framing',
        'common_edges': 'compare direct name paths versus vague thematic paths',
        'common_traps': 'treating all related names as equally likely to be said',
        'liquidity_profile': 'medium to high',
        'repeatability': 'medium',
    },
]

for payload in market_archetypes:
    _, created = upsert_named('market_archetypes', 'name', payload)
    if created:
        added['market_archetypes'] += 1

formats = [
    {
        'format_name': 'rare-political-speech-format',
        'domain': 'politics',
        'description': 'A political speech/interview format with weak recurrence or limited historical samples for direct modeling.',
        'has_prepared_remarks': 1,
        'has_qna': 1,
        'qna_probability': 'variable',
        'usual_market_effects': 'wide uncertainty bands; crowd often overstates precision from tiny sample sizes',
        'format_risk_notes': 'speaker-specific intuition may dominate transcripts when history is thin',
    },
    {
        'format_name': 'named-policy-announcement',
        'domain': 'politics',
        'description': 'Announcement where counterparties, companies, or named actors are central to the event and can dominate mention probability.',
        'has_prepared_remarks': 1,
        'has_qna': 1,
        'qna_probability': 'low to variable',
        'usual_market_effects': 'directly involved names often deserve higher yes probabilities than crowd first assumes',
        'format_risk_notes': 'longer or awkward names still have speech-friction even when they are central to the event',
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
        'pattern_name': 'go-one-layer-deeper-than-the-crowd',
        'execution_type': 'entry',
        'description': 'When the crowd already checked transcripts or obvious context, look for one additional conditioning layer such as quarter, event subtype, Q&A structure, or broadcast-specific detail.',
        'best_used_when': 'markets are no longer trivially soft but still not fully solved',
        'avoid_when': 'extra segmentation would be pure overfit with no sample support',
        'risk_note': 'not every extra layer is signal; forced granularity can invent fake edge',
        'example_video_id': '4Js-KlhdsTA',
        'example_chunk_id': chunk_map[('4Js-KlhdsTA', 11)],
    },
    {
        'pattern_name': 'price-named-counterparties-above-theme-basket',
        'execution_type': 'entry',
        'description': 'In named policy events, rank direct counterparties above generic related themes or loosely connected names.',
        'best_used_when': 'announcement explicitly revolves around a named company, executive, or counterparty',
        'avoid_when': 'the name is only tangentially related or likely avoided for rhetorical reasons',
        'risk_note': 'speech friction still matters for long or awkward names even when conceptually central',
        'example_video_id': 'DYfdif2F-O0',
        'example_chunk_id': chunk_map[('DYfdif2F-O0', 17)],
    },
    {
        'pattern_name': 'use-microstructure-edges-when-small',
        'execution_type': 'market_making',
        'description': 'With a small portfolio, exploit stale bids/offers and wide spreads rather than forcing full-event predictions in every market.',
        'best_used_when': 'small account, illiquid books, live events with obvious stale quotes',
        'avoid_when': 'your size now moves the market or you are facing informed counterparties in thin books',
        'risk_note': 'adverse selection rises quickly as size grows',
        'example_video_id': 'kW16V0BA7Lc',
        'example_chunk_id': chunk_map[('kW16V0BA7Lc', 8)],
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
        'signal_name': 'thin-history-fake-precision',
        'signal_type': 'stale_context',
        'description': 'The market is assigning a tight-looking price to a setup where historical analogs are sparse or weak.',
        'interpretation': 'confidence is overstated relative to actual model support',
        'typical_action': 'widen uncertainty, reduce size, and prefer clearer setups',
        'confidence': 0.85,
    },
    {
        'signal_name': 'direct-name-path-underpriced',
        'signal_type': 'event_specific_path',
        'description': 'A directly involved named actor is being priced too close to generic related terms instead of being recognized as a primary path.',
        'interpretation': 'the market is underweighting direct mention pathways relative to thematic ones',
        'typical_action': 'upgrade explicit counterparties/names and downgrade vague adjacent names',
        'confidence': 0.84,
    },
    {
        'signal_name': 'small-account-spread-harvest',
        'signal_type': 'microstructure',
        'description': 'A small trader can harvest wide spreads or stale quotes in books where larger players cannot efficiently deploy enough capital.',
        'interpretation': 'microstructure, not superior prediction, is the real edge source',
        'typical_action': 'take the obvious spread/misquote rather than inventing a deep directional thesis',
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
        'lesson_text': 'Small accounts should optimize for repeatable spread and stale-quote edge before trying to force maximum directional sophistication.',
        'lesson_type': 'small-account-growth',
        'description': 'With limited bankroll, easier growth often comes from microstructure and execution edge rather than huge conviction punts.',
        'applies_to': 'small portfolios, early-stage traders',
        'risk_note': 'this edge shrinks as account size grows and adverse selection gets worse',
    },
    {
        'lesson_text': 'Thin-history events deserve a bigger uncertainty discount in sizing than recurring markets with clear comparables.',
        'lesson_type': 'uncertainty_discount',
        'description': 'Rare speakers and weird formats can still be tradable, but not with the same confidence and stake size as repeated formats.',
        'applies_to': 'rare speakers, one-offs, weak comparable sets',
        'risk_note': 'the danger is fake confidence dressed up as a precise number',
    },
]

for payload in sizing_lessons:
    _, created = upsert_sizing(payload)
    if created:
        added['sizing_lessons'] += 1

phase_rows = [
    {
        'phase_name': 'late-q-and-a-detour',
        'event_format_id': format_ids['rare-political-speech-format'],
        'description': 'Late-stage question period where weakly related but still live topic words can suddenly activate.',
        'what_becomes_more_likely': 'question-driven topic pivots, reactive current-event mentions',
        'what_becomes_less_likely': 'strictly scripted opening-message words',
        'common_pricing_errors': 'market assumes no-Q&A and kills late-path strikes too hard',
        'execution_notes': 'hold or bid selectively on Q&A-dependent names if the market is overconfident that questions are dead',
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

# Link old cases already in v1 to new v2 concepts.
case_rows = conn.execute(f"select id, video_id, tags, decision from decision_cases where video_id in ({','.join(['?']*len(TARGETS))})", tuple(TARGETS)).fetchall()
for case in case_rows:
    cid = case['id']
    tags = (case['tags'] or '').lower()
    vid = case['video_id']

    if vid == 'DYfdif2F-O0':
        if ensure_link('case_pricing_signals', 'case_id', 'pricing_signal_id', cid, signal_ids['direct-name-path-underpriced']):
            added['case_pricing_signals'] += 1
        if ensure_link('case_execution_patterns', 'case_id', 'execution_pattern_id', cid, execution_ids['price-named-counterparties-above-theme-basket']):
            added['case_execution_patterns'] += 1

    if vid == '4eXmc82qnPs' or vid == '4lDIrQ-_WuY':
        if ensure_link('case_pricing_signals', 'case_id', 'pricing_signal_id', cid, signal_ids['thin-history-fake-precision']):
            added['case_pricing_signals'] += 1
        if ensure_link('case_execution_patterns', 'case_id', 'execution_pattern_id', cid, execution_ids['go-one-layer-deeper-than-the-crowd']):
            added['case_execution_patterns'] += 1
        if 'Forcing oversized confidence in markets where the event type is rare or the comparable set is thin.' in anti_patterns:
            if ensure_link('case_anti_patterns', 'case_id', 'anti_pattern_id', cid, anti_patterns['Forcing oversized confidence in markets where the event type is rare or the comparable set is thin.']):
                added['case_anti_patterns'] += 1

    if vid == '5tNFwH2n5BA':
        if 'High-probability “bond” markets deserve sizing only when the gap between market price and true resolution probability is still meaningful.' in principles:
            if ensure_link('case_principles', 'case_id', 'heuristic_id', cid, principles['High-probability “bond” markets deserve sizing only when the gap between market price and true resolution probability is still meaningful.']):
                added['case_principles'] += 1

# Also create one new case from the Moonlight 1k->30k interview if not present.
moon_case_decision = 'Use small-account microstructure edge first: stale quotes and wide spreads can compound bankroll faster than forcing full predictive models too early.'
moon_chunk_id = chunk_map[('kW16V0BA7Lc', 8)]
existing = conn.execute('SELECT id FROM decision_cases WHERE video_id=? AND chunk_id=? AND decision=?', ('kW16V0BA7Lc', moon_chunk_id, moon_case_decision)).fetchone()
if existing:
    moon_case_id = existing['id']
else:
    cur = conn.execute('INSERT INTO decision_cases (video_id, chunk_id, market_context, setup, decision, reasoning, risk_note, outcome_note, tags, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       ('kW16V0BA7Lc', moon_chunk_id,
                        'Early-stage Kalshi growth from a very small bankroll.',
                        'Small size allowed easy fills in stale or obviously mispriced books where larger traders could not deploy meaningful capital efficiently.',
                        moon_case_decision,
                        'At tiny bankroll, structural misquotes and spread capture can matter more than perfect event prediction.',
                        'This edge decays as portfolio size grows and adverse selection becomes more punishing.',
                        'Frames small-account growth as an execution/microstructure problem, not only a prediction problem.',
                        'small-portfolio,microstructure,market-making,bankroll-growth',
                        now_ts))
    moon_case_id = cur.lastrowid

if ensure_link('case_pricing_signals', 'case_id', 'pricing_signal_id', moon_case_id, signal_ids['small-account-spread-harvest']):
    added['case_pricing_signals'] += 1
if ensure_link('case_execution_patterns', 'case_id', 'execution_pattern_id', moon_case_id, execution_ids['use-microstructure-edges-when-small']):
    added['case_execution_patterns'] += 1
if 'For small accounts, microstructure and bad live quotes can be a better starting edge than pretending to have a full prediction model.' in principles:
    if ensure_link('case_principles', 'case_id', 'heuristic_id', moon_case_id, principles['For small accounts, microstructure and bad live quotes can be a better starting edge than pretending to have a full prediction model.']):
        added['case_principles'] += 1

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
