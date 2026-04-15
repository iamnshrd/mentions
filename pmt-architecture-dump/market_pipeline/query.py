#!/usr/bin/env python3
import argparse, json, re, sqlite3

DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'

SYNONYMS = {
    'trump': ['trump', 'potus', 'president'],
    'q&a': ['q&a', 'qa', 'questions', 'reporters', 'open press', 'press conference', 'briefing'],
    'interview': ['interview', 'sitdown'],
    'earnings': ['earnings', 'call'],
    'announcer': ['announcer', 'broadcast', 'commentary', 'game', 'football', 'super bowl', 'nfl', 'nba'],
    'bond': ['bond', 'bonding', '99', 'one-cent', 'dispute', 'clarification'],
    'market-impact': ['size', 'sizing', 'fill', 'fills', 'liquidity', 'market impact'],
    'current-events': ['fresh news', 'breaking', 'changed setup', 'promo', 'stale history'],
    'phase': ['prepared remarks', 'q&a', 'late path', 'opening', 'garbage time'],
}
FORMAT_HINTS = {
    'press conference': ['q&a','trump','current-events'],
    'briefing': ['q&a','current-events'],
    'interview': ['interview','current-events','q&a'],
    'earnings call': ['earnings','phase'],
    'announcer market': ['announcer','phase'],
    'sports broadcast': ['announcer','phase'],
}
ARCHETYPE_HINTS = {
    'trump live q&a mention market': ['trump','q&a','current-events'],
    'briefing-style market': ['q&a','current-events'],
    'recurring announcer mention market': ['announcer','phase'],
    'bond-like high-probability market': ['bond','market-impact'],
}
EVENT_CLASS_PRESETS = {
    'trump-rally': {'terms': ['trump', 'prepared remarks', 'crowd', 'speech'], 'formats': ['rally'], 'archetypes': ['trump live q&a mention market']},
    'trump-live-qa': {'terms': ['trump', 'q&a', 'reporters', 'open press', 'current-events'], 'formats': ['press conference', 'briefing'], 'archetypes': ['trump live q&a mention market', 'briefing-style market']},
    'briefing-style': {'terms': ['briefing', 'reporters', 'questions', 'q&a', 'current-events'], 'formats': ['briefing', 'press conference'], 'archetypes': ['briefing-style market']},
    'earnings-call': {'terms': ['earnings', 'prepared remarks', 'q&a'], 'formats': ['earnings call'], 'archetypes': []},
    'announcer-market': {'terms': ['announcer', 'broadcast', 'game', 'football', 'phase'], 'formats': ['announcer market', 'sports broadcast'], 'archetypes': ['recurring announcer mention market']},
    'bond-risk': {'terms': ['bond', 'clarification', 'dispute', 'one-cent', 'process'], 'formats': [], 'archetypes': ['bond-like high-probability market']}
}


def tokenize(text):
    return set(re.findall(r"[a-z0-9\+\-']+", (text or '').lower()))

def expand_terms(terms):
    out=set()
    for term in terms:
        t=term.lower().strip(); out.add(t)
        out.update(SYNONYMS.get(t, []))
    return out

def score_text(blob, query_terms):
    b=(blob or '').lower(); score=0; hits=[]
    for term in query_terms:
        if term and term in b:
            w=3 if ' ' in term else 1
            score += w; hits.append(term)
    return score, hits

def fetch_rows(cur, table, cols):
    return [dict(zip(cols, row)) for row in cur.execute(f"SELECT {','.join(cols)} FROM {table}")]

def tag_terms(tags_value):
    return [t.strip().lower() for t in (tags_value or '').split(',') if t.strip()]

def retrieve_bundle(event_title='', speaker='', fmt='', archetype='', freeform='', event_classes=None, top=3):
    event_classes = event_classes or []
    query_terms = set()
    for x in [event_title, speaker, fmt, archetype, freeform]:
        query_terms |= tokenize(x)
    if fmt.lower() in FORMAT_HINTS:
        query_terms |= expand_terms(FORMAT_HINTS[fmt.lower()])
    if archetype.lower() in ARCHETYPE_HINTS:
        query_terms |= expand_terms(ARCHETYPE_HINTS[archetype.lower()])
    if speaker.lower() == 'trump':
        query_terms |= expand_terms(['trump','q&a','current-events'])
    if 'correspondents' in event_title.lower() or 'dinner' in event_title.lower():
        query_terms |= expand_terms(['trump','q&a','current-events'])
    for event_class in event_classes:
        preset = EVENT_CLASS_PRESETS.get(event_class.lower())
        if not preset: continue
        query_terms |= expand_terms(preset.get('terms', []))
        for f in preset.get('formats', []):
            query_terms |= expand_terms(FORMAT_HINTS.get(f.lower(), []))
        for a in preset.get('archetypes', []):
            query_terms |= expand_terms(ARCHETYPE_HINTS.get(a.lower(), []))
    conn=sqlite3.connect(DB); cur=conn.cursor()
    result={'query_terms': sorted(query_terms), 'pricing_signals': [], 'crowd_mistakes': [], 'phase_logic': [], 'execution_patterns': [], 'decision_cases': []}
    configs={
        'pricing_signals': ('pricing_signals',['id','signal_name','signal_type','description','interpretation','typical_action','confidence']),
        'crowd_mistakes': ('crowd_mistakes',['id','mistake_name','mistake_type','description','why_it_happens','how_to_exploit']),
        'phase_logic': ('phase_logic',['id','phase_name','description','what_becomes_more_likely','what_becomes_less_likely','common_pricing_errors','execution_notes']),
        'execution_patterns': ('execution_patterns',['id','pattern_name','execution_type','description','best_used_when','avoid_when','risk_note']),
        'decision_cases': ('decision_cases',['id','market_context','setup','decision','reasoning','risk_note','outcome_note','tags']),
    }
    for out_key,(table,cols) in configs.items():
        scored=[]
        for row in fetch_rows(cur, table, cols):
            blob=' '.join(str(row.get(c,'')) for c in cols if c!='id')
            score,hits=score_text(blob, query_terms)
            if out_key=='decision_cases' and fmt and fmt.lower() in (row.get('market_context','').lower()): score += 2
            if out_key=='phase_logic' and any(t in query_terms for t in ['q&a','qa','questions','reporters','trump']): score += 1
            if out_key=='decision_cases':
                tags=tag_terms(row.get('tags',''))
                matched=[t for t in tags if any(q in t or t in q for q in query_terms)]
                if matched:
                    score += min(4, len(matched)); hits.extend(matched)
                if speaker and speaker.lower() in ' '.join(tags): score += 1
            if score > 0:
                r=dict(row); r['_score']=score; r['_hits']=sorted(set(hits))[:10]; scored.append(r)
        scored.sort(key=lambda x:(-x['_score'], x['id']))
        result[out_key]=scored[:top]
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--event-title', default='')
    ap.add_argument('--speaker', default='')
    ap.add_argument('--format', dest='fmt', default='')
    ap.add_argument('--archetype', default='')
    ap.add_argument('--freeform', default='')
    ap.add_argument('--event-class', action='append', default=[])
    ap.add_argument('--top', type=int, default=3)
    args=ap.parse_args()
    print(json.dumps(retrieve_bundle(args.event_title, args.speaker, args.fmt, args.archetype, args.freeform, args.event_class, args.top), indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
