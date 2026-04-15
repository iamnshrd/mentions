#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

TARGETS = {
    'foster---88830119-e55f-4054-975b-635fce0f3e83',
    'logan---dfc37c1c-12b9-4386-9354-3d0c310d3e01',
    'nate---d6d7387d-9e40-4d80-ba90-a8a8c49c1ad8',
    'tyrael---f5dae1a5-e645-4d7a-b3b8-caab7f68d3bb',
    '4Js-KlhdsTA',
    'X7BkPL1e8vI',
    'kW16V0BA7Lc',
    'zRCmG7F48N4',
    '4eXmc82qnPs',
    '4lDIrQ-_WuY',
    '5tNFwH2n5BA',
    'DYfdif2F-O0',
    'OypmGZ9IJb4',
    'j9GyEcdlHR4',
    '1_h3-mHlqTE',
}

def now():
    return datetime.now(timezone.utc).isoformat()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_ts = now()

chunk_map = {}
for row in conn.execute(f"select id, video_id, chunk_index from transcript_chunks where video_id in ({','.join(['?']*len(TARGETS))})", tuple(TARGETS)):
    chunk_map[(row['video_id'], row['chunk_index'])] = row['id']

# --- helpers ---
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
    'case_speaker_profiles': 0,
    'case_crowd_mistakes': 0,
    'case_dispute_patterns': 0,
    'case_live_trading_tells': 0,
}

# --- speaker profiles ---
speaker_profiles = [
    {
        'speaker_name': 'Donald Trump',
        'speaker_type': 'politician',
        'description': 'Highly path-dependent mention speaker whose pricing depends heavily on event type, current narrative regime, and whether Q&A opens up.',
        'behavior_style': 'vibes-heavy, reactive, nonlinear, detour-prone',
        'favored_topics': 'current political fights, live media narratives, grievance and contrast themes',
        'avoid_topics': 'strictly avoiding a topic is rare unless event structure heavily constrains him',
        'qna_style': 'can massively widen topic tree when engaged',
        'adaptation_notes': 'historical transcript baselines must be adjusted because his speaking mix evolves over time and by format',
    },
    {
        'speaker_name': 'JD Vance',
        'speaker_type': 'politician',
        'description': 'Less frequently modeled mention speaker where thin history makes fake precision dangerous.',
        'behavior_style': 'harder to model due to sparse comparable set',
        'favored_topics': 'issue- and context-dependent',
        'avoid_topics': 'not enough stable evidence for strong exclusion rules',
        'qna_style': 'important when present because late-question paths can materially change fair value',
        'adaptation_notes': 'size down and widen uncertainty bands relative to more familiar recurring speakers',
    },
    {
        'speaker_name': 'Recurring NFL announcer pair',
        'speaker_type': 'announcer_pair',
        'description': 'Sports-broadcast speaker profile where wording frequency depends on booth style, network, and game script.',
        'behavior_style': 'recurrent but highly segmented',
        'favored_topics': 'game-state language, replay chatter, player anecdotes, network-specific phrasing',
        'avoid_topics': 'depends on booth/network rather than hard rules',
        'qna_style': 'none',
        'adaptation_notes': 'must segment by booth and network; pooled averages are misleading',
    },
]

speaker_ids = {}
for payload in speaker_profiles:
    rid, created = upsert_named('speaker_profiles', 'speaker_name', payload)
    speaker_ids[payload['speaker_name']] = rid
    if created:
        added['speaker_profiles'] += 1

# --- crowd mistakes ---
crowd_mistakes = [
    {
        'mistake_name': 'overweighting-setup-labels',
        'mistake_type': 'event_structure',
        'description': 'Treating open press / closed press / setup shorthand as near-deterministic instead of one variable in the event tree.',
        'why_it_happens': 'setup cues are simple and visible, so the crowd anchors on them even when current-event context matters more.',
        'how_to_exploit': 'fade pure setup overreaction and reprice after actual event path becomes visible.',
        'example_video_id': 'j9GyEcdlHR4',
        'example_chunk_id': chunk_map[('j9GyEcdlHR4', 20)],
    },
    {
        'mistake_name': 'trusting-pooled-historicals',
        'mistake_type': 'modeling',
        'description': 'Using one pooled historical hit rate for recurring mention markets instead of segmenting by event subtype, booth, network, or context.',
        'why_it_happens': 'a single number looks rigorous and is easy to communicate, even when it hides the real drivers of fair value.',
        'how_to_exploit': 'rebuild the comparable set on the correct subset and trade against the crowd’s fake precision.',
        'example_video_id': 'foster---88830119-e55f-4054-975b-635fce0f3e83',
        'example_chunk_id': chunk_map[('foster---88830119-e55f-4054-975b-635fce0f3e83', 7)],
    },
    {
        'mistake_name': 'copy-trading-after-price-move',
        'mistake_type': 'execution',
        'description': 'Following a sharp after the number already moved, while confusing the original good entry with the current worse one.',
        'why_it_happens': 'public trade sharing creates social proof and urgency, especially in illiquid books.',
        'how_to_exploit': 'either sell into follower demand or simply refuse to inherit their worse entry unless you independently rebuild the thesis.',
        'example_video_id': 'logan---dfc37c1c-12b9-4386-9354-3d0c310d3e01',
        'example_chunk_id': chunk_map[('logan---dfc37c1c-12b9-4386-9354-3d0c310d3e01', 35)],
    },
    {
        'mistake_name': 'misreading-field-information',
        'mistake_type': 'conditional_probability',
        'description': 'Treating each field member independently even after informed flow clearly reweights the rest of the field.',
        'why_it_happens': 'traders focus on the pumped names and fail to update the untouched names as conditional losers.',
        'how_to_exploit': 'reprice the rest of the field downward and farm NOs where the market still prices them independently.',
        'example_video_id': 'nate---d6d7387d-9e40-4d80-ba90-a8a8c49c1ad8',
        'example_chunk_id': chunk_map[('nate---d6d7387d-9e40-4d80-ba90-a8a8c49c1ad8', 7)],
    },
]

crowd_ids = {}
for payload in crowd_mistakes:
    rid, created = upsert_named('crowd_mistakes', 'mistake_name', payload)
    crowd_ids[payload['mistake_name']] = rid
    if created:
        added['crowd_mistakes'] += 1

# --- dispute patterns ---
dispute_patterns = [
    {
        'pattern_name': 'sub-brand-vs-parent-brand-ambiguity',
        'dispute_type': 'rules_scope',
        'description': 'A market names a parent brand/company, but the live event references only a product or sub-brand, creating a rules dispute over whether it counts.',
        'common_confusion': 'traders assume ownership implies resolution, while rules may require the named brand itself to be specifically advertised or mentioned.',
        'market_impact': 'can create huge intraday repricing and false certainty on both sides.',
        'mitigation': 'read the contract scope literally and search for explicit clarifications before treating it as a bond.',
        'example_video_id': 'nate---d6d7387d-9e40-4d80-ba90-a8a8c49c1ad8',
        'example_chunk_id': chunk_map[('nate---d6d7387d-9e40-4d80-ba90-a8a8c49c1ad8', 47 if ('nate---d6d7387d-9e40-4d80-ba90-a8a8c49c1ad8', 47) in chunk_map else 17)],
    },
    {
        'pattern_name': 'false-bond-via-rules-or-tail-risk',
        'dispute_type': 'bonding',
        'description': 'A market looks like a simple 95-99% bond but still contains enough unresolved rules/path ambiguity that the last few percent are very real.',
        'common_confusion': 'traders treat long winning streaks as proof the edge is safe, instead of pricing the occasional catastrophic failure.',
        'market_impact': 'one bad clarification or missed path can erase many small bond wins.',
        'mitigation': 'price tail risk explicitly and size by rules clarity, not just base-rate confidence.',
        'example_video_id': 'logan---dfc37c1c-12b9-4386-9354-3d0c310d3e01',
        'example_chunk_id': chunk_map[('logan---dfc37c1c-12b9-4386-9354-3d0c310d3e01', 12)],
    },
]

dispute_ids = {}
for payload in dispute_patterns:
    rid, created = upsert_named('dispute_patterns', 'pattern_name', payload)
    dispute_ids[payload['pattern_name']] = rid
    if created:
        added['dispute_patterns'] += 1

# --- live trading tells ---
live_tells = [
    {
        'tell_name': 'full-size-fill-from-one-side',
        'tell_type': 'adverse_selection',
        'description': 'You suddenly get filled for the entire resting size at once, suggesting a counterparty may know something you do not.',
        'interpretation': 'the fill itself is information; this is different from getting slowly nibbled by retail flow.',
        'typical_response': 'pause, recheck the news/setup/rules, and do not assume your quote was simply lucky.',
        'risk_note': 'not every full fill is informed flow, but ignoring it entirely is costly.',
        'example_video_id': 'foster---88830119-e55f-4054-975b-635fce0f3e83',
        'example_chunk_id': chunk_map[('foster---88830119-e55f-4054-975b-635fce0f3e83', 35)],
    },
    {
        'tell_name': 'book-moves-before-you-finish-thinking',
        'tell_type': 'decaying_edge',
        'description': 'Price is clearly running away while you wait for ideal passive fills, signalling that entry quality is degrading in real time.',
        'interpretation': 'some edge is time-decaying fast enough that perfect passivity is no longer optimal.',
        'typical_response': 'consider switching from passive to selective aggressive entry if the thesis is still intact.',
        'risk_note': 'can also just be FOMO; only valid when there is a real short-lived informational edge.',
        'example_video_id': 'OypmGZ9IJb4',
        'example_chunk_id': chunk_map[('OypmGZ9IJb4', 19)],
    },
    {
        'tell_name': 'informed-pump-implies-rest-of-field-weaker',
        'tell_type': 'field_inference',
        'description': 'In a field market, heavy informed-looking action into a few names is itself a live tell on the rest of the field.',
        'interpretation': 'the absence of buying elsewhere becomes bearish information for untouched names.',
        'typical_response': 'look immediately at NOs or cheap exits on the non-pumped names.',
        'risk_note': 'only reliable when the pumped names truly look informed and the rules do not allow many simultaneous winners.',
        'example_video_id': 'nate---d6d7387d-9e40-4d80-ba90-a8a8c49c1ad8',
        'example_chunk_id': chunk_map[('nate---d6d7387d-9e40-4d80-ba90-a8a8c49c1ad8', 7)],
    },
    {
        'tell_name': 'setup-cue-price-spike-without-live-confirmation',
        'tell_type': 'crowd_overreaction',
        'description': 'Price spikes off a setup cue or label before the event has provided live evidence that the path is actually opening or closing.',
        'interpretation': 'the crowd is paying for shorthand rather than event reality.',
        'typical_response': 'slow down, reprice from path structure, and prepare to fade if the move exceeds what the cue justifies.',
        'risk_note': 'some setup cues are real signal; the key is whether the move outruns what the cue actually implies.',
        'example_video_id': 'j9GyEcdlHR4',
        'example_chunk_id': chunk_map[('j9GyEcdlHR4', 20)],
    },
]

tell_ids = {}
for payload in live_tells:
    rid, created = upsert_named('live_trading_tells', 'tell_name', payload)
    tell_ids[payload['tell_name']] = rid
    if created:
        added['live_trading_tells'] += 1

# --- link to existing cases ---
case_rows = conn.execute('select id, video_id, tags, decision from decision_cases').fetchall()
for case in case_rows:
    cid = case['id']
    vid = case['video_id']
    tags = (case['tags'] or '').lower()
    decision = (case['decision'] or '').lower()

    if 'trump' in tags or 'event-structure' in tags or 'open-press' in tags or 'q&a' in tags:
        if ensure_link('case_speaker_profiles', 'case_id', 'speaker_profile_id', cid, speaker_ids['Donald Trump']):
            added['case_speaker_profiles'] += 1
        if ensure_link('case_crowd_mistakes', 'case_id', 'crowd_mistake_id', cid, crowd_ids['overweighting-setup-labels']):
            added['case_crowd_mistakes'] += 1
        if ensure_link('case_live_trading_tells', 'case_id', 'live_trading_tell_id', cid, tell_ids['setup-cue-price-spike-without-live-confirmation']):
            added['case_live_trading_tells'] += 1

    if 'announcer' in tags or 'segmentation' in tags or 'nfl' in tags:
        if ensure_link('case_speaker_profiles', 'case_id', 'speaker_profile_id', cid, speaker_ids['Recurring NFL announcer pair']):
            added['case_speaker_profiles'] += 1
        if ensure_link('case_crowd_mistakes', 'case_id', 'crowd_mistake_id', cid, crowd_ids['trusting-pooled-historicals']):
            added['case_crowd_mistakes'] += 1

    if 'copy-trading' in tags or 'price-discipline' in tags:
        if ensure_link('case_crowd_mistakes', 'case_id', 'crowd_mistake_id', cid, crowd_ids['copy-trading-after-price-move']):
            added['case_crowd_mistakes'] += 1

    if 'field-pricing' in tags or 'conditional-probability' in tags or 'insider-flow' in tags:
        if ensure_link('case_crowd_mistakes', 'case_id', 'crowd_mistake_id', cid, crowd_ids['misreading-field-information']):
            added['case_crowd_mistakes'] += 1
        if ensure_link('case_live_trading_tells', 'case_id', 'live_trading_tell_id', cid, tell_ids['informed-pump-implies-rest-of-field-weaker']):
            added['case_live_trading_tells'] += 1

    if 'bond' in tags or 'capital-allocation' in tags:
        if ensure_link('case_dispute_patterns', 'case_id', 'dispute_pattern_id', cid, dispute_ids['false-bond-via-rules-or-tail-risk']):
            added['case_dispute_patterns'] += 1

# Explicit links for sparse-speaker cases.
for row in conn.execute("select id from decision_cases where video_id in ('4eXmc82qnPs','4lDIrQ-_WuY')"):
    if ensure_link('case_speaker_profiles', 'case_id', 'speaker_profile_id', row['id'], speaker_ids['JD Vance']):
        added['case_speaker_profiles'] += 1

# Link execution decay tell to the aggressive-entry case from batch2.
for row in conn.execute("select id from decision_cases where video_id='OypmGZ9IJb4'"):
    if ensure_link('case_live_trading_tells', 'case_id', 'live_trading_tell_id', row['id'], tell_ids['book-moves-before-you-finish-thinking']):
        added['case_live_trading_tells'] += 1

conn.commit()
print('ADDED', added)
for table in [
    'speaker_profiles',
    'crowd_mistakes',
    'dispute_patterns',
    'live_trading_tells',
    'case_speaker_profiles',
    'case_crowd_mistakes',
    'case_dispute_patterns',
    'case_live_trading_tells',
]:
    print(table, conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
