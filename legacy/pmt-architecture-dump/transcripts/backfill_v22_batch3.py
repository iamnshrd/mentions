#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

TARGETS = {
    '7G7qFsIQPg0',   # TRUMP PRESS BRIEFING - SPECIAL GUEST
    '7pQihJ9lKxo',   # DONALD TRUMP CEREMONY
    'fn74hQNkl0g',   # TRUMP MEETS WITH FARMERS
    'Nqd2PIniI-g',   # Trump Netanyahu Meeting
    'WGMg2hZXPCg',   # LIVE TO THE 4TH QUARTER - NFL ANNOUNCER MENTIONS
    '18GkcgZ6Few',   # BAD BUNNY PRESS CONFERECE _ WHITE HOUSE PRESS BRIEFING
    'KQR4SOOhp5E',   # TRUMP MEETING
}

def now():
    return datetime.now(timezone.utc).isoformat()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_ts = now()

chunk_map = {}
for row in conn.execute(f"select id, video_id, chunk_index from transcript_chunks where video_id in ({','.join(['?']*len(TARGETS))})", tuple(TARGETS)):
    chunk_map[(row['video_id'], row['chunk_index'])] = row['id']

# helpers

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

def ensure_link(table, left_field, right_field, left_id, right_id):
    exists = conn.execute(f"SELECT 1 FROM {table} WHERE {left_field}=? AND {right_field}=?", (left_id, right_id)).fetchone()
    if not exists:
        conn.execute(f"INSERT INTO {table} ({left_field}, {right_field}) VALUES (?,?)", (left_id, right_id))
        return True
    return False

added = {
    'speaker_profiles': 0,
    'crowd_mistakes': 0,
    'dispute_patterns': 0,
    'live_trading_tells': 0,
    'decision_cases': 0,
    'case_speaker_profiles': 0,
    'case_crowd_mistakes': 0,
    'case_dispute_patterns': 0,
    'case_live_trading_tells': 0,
}

# speaker profiles batch3
speaker_rows = [
    {
        'speaker_name': 'Karoline Leavitt',
        'speaker_type': 'press_secretary',
        'description': 'Recurring press-briefing speaker where setup, pacing, and room dynamics matter, but frequent appearances make comparative modeling stronger than for rare speakers.',
        'behavior_style': 'more recurring and modelable than rare political speakers, but still sensitive to briefing context',
        'favored_topics': 'administration line items, current briefing agenda, headline political disputes',
        'avoid_topics': 'depends on briefing scope rather than stable hard exclusions',
        'qna_style': 'briefing-driven; question density and room flow matter a lot',
        'adaptation_notes': 'good recurring source for comparative pricing, but crowd can still overreact to open/closed setup cues.',
    },
    {
        'speaker_name': 'Culture live-event host / production flow',
        'speaker_type': 'host',
        'description': 'Live culture-event speaking environment where production choices and performance logistics matter as much as spoken content.',
        'behavior_style': 'production-driven, timing-sensitive, less transcript-stable',
        'favored_topics': 'show flow, performer introductions, event-specific stage moments',
        'avoid_topics': 'off-script tangents unless event chaos creates them',
        'qna_style': 'none or minimal',
        'adaptation_notes': 'must consider logistics, not just words, especially in performer markets.',
    },
]

speaker_ids = {r['speaker_name']: r['id'] for r in conn.execute('select id, speaker_name from speaker_profiles')}
for payload in speaker_rows:
    rid, created = upsert_named('speaker_profiles', 'speaker_name', payload)
    speaker_ids[payload['speaker_name']] = rid
    if created:
        added['speaker_profiles'] += 1

crowd_rows = [
    {
        'mistake_name': 'assuming-setup-kills-late-paths',
        'mistake_type': 'event_structure',
        'description': 'Killing late-path strikes too early because the crowd believes setup or early remarks mechanically rule out later Q&A or detours.',
        'why_it_happens': 'people mentally collapse the whole event tree after the opening phase instead of keeping late-path optionality alive.',
        'how_to_exploit': 'hold or accumulate selective late-path contracts when Q&A remains plausible despite early silence.',
        'example_video_id': '7G7qFsIQPg0',
        'example_chunk_id': chunk_map[('7G7qFsIQPg0', 24)],
    },
    {
        'mistake_name': 'confusing-logistics-with-probability-zero',
        'mistake_type': 'culture',
        'description': 'Treating noisy production/logistics information as either irrelevant or as full certainty, instead of pricing it proportionally.',
        'why_it_happens': 'culture markets attract dramatic narrative thinking and binary interpretations of show logistics.',
        'how_to_exploit': 'translate logistics into probability shifts instead of all-or-nothing conclusions.',
        'example_video_id': '18GkcgZ6Few',
        'example_chunk_id': chunk_map[('18GkcgZ6Few', 12)],
    },
    {
        'mistake_name': 'assuming-random-yap-is-variance-not-structure',
        'mistake_type': 'sports',
        'description': 'Treating late-game announcer wander as random bad luck instead of a structural phase where chatter patterns change.',
        'why_it_happens': 'traders price all game minutes similarly even though garbage time has a different language mix.',
        'how_to_exploit': 'reprice chatter-prone strikes differently once the game state is dead.',
        'example_video_id': 'WGMg2hZXPCg',
        'example_chunk_id': chunk_map[('WGMg2hZXPCg', 9)],
    },
]

crowd_ids = {r['mistake_name']: r['id'] for r in conn.execute('select id, mistake_name from crowd_mistakes')}
for payload in crowd_rows:
    rid, created = upsert_named('crowd_mistakes', 'mistake_name', payload)
    crowd_ids[payload['mistake_name']] = rid
    if created:
        added['crowd_mistakes'] += 1

dispute_rows = [
    {
        'pattern_name': 'speaker-vs-display-vs-context-resolution-confusion',
        'dispute_type': 'mention_counting',
        'description': 'Market participants disagree on whether something counts because it appeared in surrounding context, display text, or indirect phrasing rather than clean spoken usage.',
        'common_confusion': 'traders blur together spoken word, displayed text, quoted references, and production context.',
        'market_impact': 'creates fake bonds and late repricing when the contract language is interpreted more narrowly than the crowd expected.',
        'mitigation': 'map exactly what the contract counts and avoid treating adjacent context as equivalent to the named criterion.',
        'example_video_id': 'Nqd2PIniI-g',
        'example_chunk_id': chunk_map[('Nqd2PIniI-g', 18)],
    },
]

dispute_ids = {r['pattern_name']: r['id'] for r in conn.execute('select id, pattern_name from dispute_patterns')}
for payload in dispute_rows:
    rid, created = upsert_named('dispute_patterns', 'pattern_name', payload)
    dispute_ids[payload['pattern_name']] = rid
    if created:
        added['dispute_patterns'] += 1

tell_rows = [
    {
        'tell_name': 'late-path-stays-too-cheap-after-silence',
        'tell_type': 'qna_optionality',
        'description': 'A strike remains cheap after being unsaid in prepared remarks even though the real path was always later Q&A or detour-driven.',
        'interpretation': 'the market is confusing “not said yet” with “dead.”',
        'typical_response': 'buy or hold selective late-path names when event structure still leaves them alive.',
        'risk_note': 'dies fast if Q&A truly closes or event ends early.',
        'example_video_id': '7G7qFsIQPg0',
        'example_chunk_id': chunk_map[('7G7qFsIQPg0', 24)],
    },
    {
        'tell_name': 'garbage-time-broadcast-drift',
        'tell_type': 'sports_phase_shift',
        'description': 'Once the game script dies, announcers drift into broader chatter and anecdotal language, changing hit probabilities.',
        'interpretation': 'late-game word frequencies are no longer the same as competitive-game frequencies.',
        'typical_response': 'downgrade confidence in NOs on chatter-prone strikes and re-evaluate replay/anecdote words.',
        'risk_note': 'not every blowout produces the same drift; booth style still matters.',
        'example_video_id': 'WGMg2hZXPCg',
        'example_chunk_id': chunk_map[('WGMg2hZXPCg', 9)],
    },
    {
        'tell_name': 'logistics-signal-before-performance',
        'tell_type': 'culture_logistics',
        'description': 'Pre-event physical presence, rehearsal clues, or production logistics can be informative, but not always to the extreme degree the market prices.',
        'interpretation': 'logistics are signal, but often noisy signal rather than total certainty.',
        'typical_response': 'reprice proportionally and check whether the market has converted a clue into unjustified near-certainty.',
        'risk_note': 'culture events have enough ambiguity that overconfidence on logistics can get punished both ways.',
        'example_video_id': '18GkcgZ6Few',
        'example_chunk_id': chunk_map[('18GkcgZ6Few', 12)],
    },
]

tell_ids = {r['tell_name']: r['id'] for r in conn.execute('select id, tell_name from live_trading_tells')}
for payload in tell_rows:
    rid, created = upsert_named('live_trading_tells', 'tell_name', payload)
    tell_ids[payload['tell_name']] = rid
    if created:
        added['live_trading_tells'] += 1

# new cases for batch3
case_specs = [
    {
        'video_id': '7G7qFsIQPg0',
        'chunk_index': 24,
        'market_context': 'Trump/briefing-style mention market where a strike stayed cheap after not appearing in the opening phase.',
        'setup': 'The crowd treated early silence plus setup cues as if they mechanically killed the late path.',
        'decision': 'Keep the late-path strike alive and price it off actual Q&A optionality rather than opening-phase silence alone.',
        'reasoning': 'Some words are structurally late-path words. Being unsaid early is not the same as being dead.',
        'risk_note': 'The edge disappears if the event truly closes without questions or detours.',
        'outcome_note': 'Useful case for distinguishing “unsaid yet” from “dead.”',
        'tags': 'q&a,late-path,event-structure,trump,mentions',
    },
    {
        'video_id': 'WGMg2hZXPCg',
        'chunk_index': 9,
        'market_context': 'NFL announcer mentions during late-game / fourth-quarter dead-game conditions.',
        'setup': 'The crowd priced late-game chatter as if it were the same as the rest of the game even after the competitive script had died.',
        'decision': 'Reprice chatter-prone words for garbage-time drift instead of treating late-game hits as pure bad variance.',
        'reasoning': 'Broadcast language changes when the booth no longer has live competitive action to focus on.',
        'risk_note': 'Booth style still matters; not every dead game creates the same chatter mix.',
        'outcome_note': 'Turns “announcer randomness” into a structural phase concept.',
        'tags': 'announcer,nfl,garbage-time,live-trading,phase-shift',
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

# link new cases and existing related cases
case1 = case_ids[('7G7qFsIQPg0', 24)]
if ensure_link('case_speaker_profiles', 'case_id', 'speaker_profile_id', case1, speaker_ids['Donald Trump']):
    added['case_speaker_profiles'] += 1
if ensure_link('case_crowd_mistakes', 'case_id', 'crowd_mistake_id', case1, crowd_ids['assuming-setup-kills-late-paths']):
    added['case_crowd_mistakes'] += 1
if ensure_link('case_live_trading_tells', 'case_id', 'live_trading_tell_id', case1, tell_ids['late-path-stays-too-cheap-after-silence']):
    added['case_live_trading_tells'] += 1

case2 = case_ids[('WGMg2hZXPCg', 9)]
if ensure_link('case_speaker_profiles', 'case_id', 'speaker_profile_id', case2, speaker_ids['Recurring NFL announcer pair']):
    added['case_speaker_profiles'] += 1
if ensure_link('case_crowd_mistakes', 'case_id', 'crowd_mistake_id', case2, crowd_ids['assuming-random-yap-is-variance-not-structure']):
    added['case_crowd_mistakes'] += 1
if ensure_link('case_live_trading_tells', 'case_id', 'live_trading_tell_id', case2, tell_ids['garbage-time-broadcast-drift']):
    added['case_live_trading_tells'] += 1

# attach Karoline-related profile to older briefing cases if any
for row in conn.execute("select id from decision_cases where video_id in ('-1iqA98SSV0','0SQ1N4o2cLQ','Kbw5kJ3a0iU','DySVjsb3cNU','v80_PNaDf8M')"):
    if ensure_link('case_speaker_profiles', 'case_id', 'speaker_profile_id', row['id'], speaker_ids['Karoline Leavitt']):
        added['case_speaker_profiles'] += 1

# attach dispute/tells to relevant existing cases
for row in conn.execute("select id from decision_cases where tags like '%field-pricing%' or tags like '%conditional-probability%'"):
    if ensure_link('case_live_trading_tells', 'case_id', 'live_trading_tell_id', row['id'], tell_ids['logistics-signal-before-performance']):
        added['case_live_trading_tells'] += 1

for row in conn.execute("select id from decision_cases where tags like '%bond%' or tags like '%price-discipline%'"):
    if ensure_link('case_dispute_patterns', 'case_id', 'dispute_pattern_id', row['id'], dispute_ids['speaker-vs-display-vs-context-resolution-confusion']):
        added['case_dispute_patterns'] += 1

conn.commit()
print('ADDED', added)
for table in [
    'speaker_profiles',
    'crowd_mistakes',
    'dispute_patterns',
    'live_trading_tells',
    'decision_cases',
    'case_speaker_profiles',
    'case_crowd_mistakes',
    'case_dispute_patterns',
    'case_live_trading_tells',
]:
    print(table, conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
