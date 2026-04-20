#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB = '/root/.openclaw/workspace/pmt_trader_knowledge.db'
BASE = Path('/root/.openclaw/workspace/transcripts/kb_normalized')

def now():
    return datetime.now(timezone.utc).isoformat()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_ts = now()

# ---- helpers ----
def load(name):
    path = BASE / f'{name}.json'
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8'))

def upsert_named(table, key_field, payload):
    row = conn.execute(f"SELECT id FROM {table} WHERE {key_field}=?", (payload[key_field],)).fetchone()
    cols = [k for k in payload.keys() if k != 'id']
    if row:
        set_cols = [c for c in cols if c != key_field]
        values = [payload[c] for c in set_cols] + [now_ts, row['id']]
        conn.execute(f"UPDATE {table} SET {', '.join(f'{c}=?' for c in set_cols)}, updated_at=? WHERE id=?", values)
        return row['id'], False
    insert_cols = cols + ['created_at', 'updated_at']
    insert_vals = [payload[c] for c in cols] + [now_ts, now_ts]
    cur = conn.execute(f"INSERT INTO {table} ({', '.join(insert_cols)}) VALUES ({','.join(['?']*len(insert_cols))})", insert_vals)
    return cur.lastrowid, True

def summarize_evidence(row):
    ev = row.get('sample_evidence', [])
    texts = [x['text'] for x in ev[:3]]
    return ' | '.join(texts)[:1800]

added = {
    'market_archetypes': 0,
    'event_formats': 0,
    'speaker_profiles': 0,
    'pricing_signals': 0,
    'crowd_mistakes': 0,
    'dispute_patterns': 0,
    'live_trading_tells': 0,
    'execution_patterns': 0,
    'sizing_lessons': 0,
    'phase_logic': 0,
}

# ---- market_archetypes ----
for row in load('market_archetypes'):
    name = row['canonical_name']
    payload = {
        'name': name,
        'archetype_type': 'mentions' if 'mentions' in name else ('execution' if 'execution' in name else 'general'),
        'description': f'Canonical full-corpus archetype: {name}. Evidence count={row["evidence_count"]}.',
        'pricing_drivers': summarize_evidence(row),
        'common_edges': 'Derived from full-corpus normalization.',
        'common_traps': 'See attached evidence cluster for recurring mistakes.',
        'liquidity_profile': 'varies',
        'repeatability': 'varies',
    }
    _, created = upsert_named('market_archetypes', 'name', payload)
    if created:
        added['market_archetypes'] += 1

# ---- event_formats ----
for row in load('event_formats'):
    name = row['canonical_name']
    domain = 'sports' if 'sports' in name or 'broadcast' in name else ('culture' if 'culture' in name else 'politics')
    payload = {
        'format_name': name,
        'domain': domain,
        'description': f'Canonical full-corpus event format: {name}. Evidence count={row["evidence_count"]}.',
        'has_prepared_remarks': 1 if any(k in name for k in ['trump', 'briefing', 'announcement', 'speech']) else 0,
        'has_qna': 1 if any(k in name for k in ['qna', 'briefing', 'trump']) else 0,
        'qna_probability': 'variable',
        'usual_market_effects': summarize_evidence(row),
        'format_risk_notes': 'Normalized from corpus-level evidence cluster.',
    }
    _, created = upsert_named('event_formats', 'format_name', payload)
    if created:
        added['event_formats'] += 1

# ---- speaker_profiles ----
for row in load('speaker_profiles'):
    name = row['canonical_name']
    stype = 'announcer_pair' if 'announcer' in name.lower() else ('press_secretary' if 'karoline' in name.lower() else ('politician' if any(x in name.lower() for x in ['trump','vance']) else 'host'))
    payload = {
        'speaker_name': name,
        'speaker_type': stype,
        'description': f'Canonical full-corpus speaker profile: {name}. Evidence count={row["evidence_count"]}.',
        'behavior_style': 'Normalized from transcript cluster.',
        'favored_topics': summarize_evidence(row),
        'avoid_topics': 'Needs refined manual pass for stronger exclusions.',
        'qna_style': 'variable',
        'adaptation_notes': 'Corpus-normalized profile; should be refined manually if used in production reasoning.',
    }
    _, created = upsert_named('speaker_profiles', 'speaker_name', payload)
    if created:
        added['speaker_profiles'] += 1

# ---- pricing_signals ----
for row in load('pricing_signals'):
    name = row['canonical_name']
    payload = {
        'signal_name': name,
        'signal_type': 'normalized_family',
        'description': f'Canonical full-corpus pricing signal: {name}. Evidence count={row["evidence_count"]}.',
        'interpretation': summarize_evidence(row),
        'typical_action': 'See evidence cluster and linked execution patterns.',
        'confidence': 0.75,
    }
    _, created = upsert_named('pricing_signals', 'signal_name', payload)
    if created:
        added['pricing_signals'] += 1

# ---- crowd_mistakes ----
for row in load('crowd_mistakes'):
    name = row['canonical_name']
    ev = row.get('sample_evidence', [])
    example_video_id = ev[0]['video_id'] if ev else None
    example_chunk_id = ev[0]['chunk_id'] if ev else None
    payload = {
        'mistake_name': name,
        'mistake_type': 'normalized_family',
        'description': f'Canonical full-corpus crowd mistake: {name}. Evidence count={row["evidence_count"]}.',
        'why_it_happens': summarize_evidence(row),
        'how_to_exploit': 'Fade the crowd version of this error when live path and pricing diverge.',
        'example_video_id': example_video_id,
        'example_chunk_id': example_chunk_id,
    }
    _, created = upsert_named('crowd_mistakes', 'mistake_name', payload)
    if created:
        added['crowd_mistakes'] += 1

# ---- dispute_patterns ----
for row in load('dispute_patterns'):
    name = row['canonical_name']
    ev = row.get('sample_evidence', [])
    example_video_id = ev[0]['video_id'] if ev else None
    example_chunk_id = ev[0]['chunk_id'] if ev else None
    payload = {
        'pattern_name': name,
        'dispute_type': 'normalized_family',
        'description': f'Canonical full-corpus dispute pattern: {name}. Evidence count={row["evidence_count"]}.',
        'common_confusion': summarize_evidence(row),
        'market_impact': 'Can create false bonds, overconfident pricing, or late repricing after clarification.',
        'mitigation': 'Read contract scope literally and separate direct counted events from adjacent context.',
        'example_video_id': example_video_id,
        'example_chunk_id': example_chunk_id,
    }
    _, created = upsert_named('dispute_patterns', 'pattern_name', payload)
    if created:
        added['dispute_patterns'] += 1

# ---- live_trading_tells ----
for row in load('live_trading_tells'):
    name = row['canonical_name']
    ev = row.get('sample_evidence', [])
    example_video_id = ev[0]['video_id'] if ev else None
    example_chunk_id = ev[0]['chunk_id'] if ev else None
    payload = {
        'tell_name': name,
        'tell_type': 'normalized_family',
        'description': f'Canonical full-corpus live-trading tell: {name}. Evidence count={row["evidence_count"]}.',
        'interpretation': summarize_evidence(row),
        'typical_response': 'Treat the tell as information and re-check fair value / path / rules before acting mechanically.',
        'risk_note': 'Some tells are noisy; they improve judgment but are not deterministic.',
        'example_video_id': example_video_id,
        'example_chunk_id': example_chunk_id,
    }
    _, created = upsert_named('live_trading_tells', 'tell_name', payload)
    if created:
        added['live_trading_tells'] += 1

# ---- execution_patterns ----
for row in load('execution_patterns'):
    name = row['canonical_name']
    payload = {
        'pattern_name': name,
        'execution_type': 'normalized_family',
        'description': f'Canonical full-corpus execution pattern: {name}. Evidence count={row["evidence_count"]}.',
        'best_used_when': summarize_evidence(row),
        'avoid_when': 'Avoid if matching logic is weak or the pattern is only loosely present.',
        'risk_note': 'Execution families still need market-specific adaptation.',
        'example_video_id': row['sample_evidence'][0]['video_id'] if row.get('sample_evidence') else None,
        'example_chunk_id': row['sample_evidence'][0]['chunk_id'] if row.get('sample_evidence') else None,
    }
    _, created = upsert_named('execution_patterns', 'pattern_name', payload)
    if created:
        added['execution_patterns'] += 1

# ---- sizing_lessons ----
for row in load('sizing_lessons'):
    name = row['canonical_name']
    row0 = conn.execute('SELECT id FROM sizing_lessons WHERE lesson_text=?', (name,)).fetchone()
    payload_desc = summarize_evidence(row)
    if row0:
        conn.execute('UPDATE sizing_lessons SET lesson_type=?, description=?, applies_to=?, risk_note=?, updated_at=? WHERE id=?',
                     ('normalized_family', payload_desc, 'general', 'Corpus-normalized sizing lesson.', now_ts, row0['id']))
    else:
        conn.execute('INSERT INTO sizing_lessons (lesson_text, lesson_type, description, applies_to, risk_note, created_at, updated_at) VALUES (?,?,?,?,?,?,?)',
                     (name, 'normalized_family', payload_desc, 'general', 'Corpus-normalized sizing lesson.', now_ts, now_ts))
        added['sizing_lessons'] += 1

# ---- phase_logic ----
format_lookup = {r['format_name']: r['id'] for r in conn.execute('select id, format_name from event_formats')}
def guess_event_format_id(phase_name):
    if 'garbage' in phase_name:
        return format_lookup.get('sports-broadcast-live')
    if 'setup' in phase_name:
        return format_lookup.get('trump-announcement-with-setup-fud') or format_lookup.get('trump-live-event-with-qna-risk')
    if 'q-and-a' in phase_name or 'prepared' in phase_name:
        return format_lookup.get('trump-live-event-with-qna-risk')
    return None

for row in load('phase_logic'):
    name = row['canonical_name']
    eid = guess_event_format_id(name)
    existing = conn.execute('SELECT id FROM phase_logic WHERE phase_name=? AND event_format_id IS ?', (name, eid)).fetchone()
    if existing:
        conn.execute('UPDATE phase_logic SET description=?, what_becomes_more_likely=?, what_becomes_less_likely=?, common_pricing_errors=?, execution_notes=?, updated_at=? WHERE id=?',
                     (f'Canonical full-corpus phase: {name}. Evidence count={row["evidence_count"]}.', summarize_evidence(row), 'Context-dependent', 'See normalized evidence cluster.', 'Use with event-format reasoning.', now_ts, existing['id']))
    else:
        conn.execute('INSERT INTO phase_logic (phase_name, event_format_id, description, what_becomes_more_likely, what_becomes_less_likely, common_pricing_errors, execution_notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                     (name, eid, f'Canonical full-corpus phase: {name}. Evidence count={row["evidence_count"]}.', summarize_evidence(row), 'Context-dependent', 'See normalized evidence cluster.', 'Use with event-format reasoning.', now_ts, now_ts))
        added['phase_logic'] += 1

conn.commit()
print('ADDED', added)
for table in [
    'market_archetypes',
    'event_formats',
    'speaker_profiles',
    'pricing_signals',
    'crowd_mistakes',
    'dispute_patterns',
    'live_trading_tells',
    'execution_patterns',
    'sizing_lessons',
    'phase_logic',
]:
    print(table, conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
