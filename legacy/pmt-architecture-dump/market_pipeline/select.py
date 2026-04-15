#!/usr/bin/env python3
import json, sys

def pick_one(rows): return rows[0] if rows else None

def summarize_case(case):
    if not case: return None
    return {'id': case.get('id'), 'market_context': case.get('market_context'), 'setup': case.get('setup'), 'lesson': case.get('reasoning') or case.get('outcome_note'), 'tags': case.get('tags'), '_score': case.get('_score'), '_hits': case.get('_hits')}

def summarize_row(row, name_key):
    if not row: return None
    out={'id': row.get('id'), 'name': row.get(name_key), '_score': row.get('_score'), '_hits': row.get('_hits')}
    for k,v in row.items():
        if k not in out and not k.startswith('_'): out[k]=v
    return out

def select_bundle(data):
    return {
        'query_terms': data.get('query_terms', []),
        'main_pricing_signal': summarize_row(pick_one(data.get('pricing_signals', [])), 'signal_name'),
        'main_crowd_mistake': summarize_row(pick_one(data.get('crowd_mistakes', [])), 'mistake_name'),
        'relevant_phase_logic': summarize_row(pick_one(data.get('phase_logic', [])), 'phase_name'),
        'main_execution_pattern': summarize_row(pick_one(data.get('execution_patterns', [])), 'pattern_name'),
        'closest_case': summarize_case(pick_one(data.get('decision_cases', []))),
        'secondary': {
            'pricing_signals': [summarize_row(x, 'signal_name') for x in data.get('pricing_signals', [])[1:3]],
            'crowd_mistakes': [summarize_row(x, 'mistake_name') for x in data.get('crowd_mistakes', [])[1:3]],
            'phase_logic': [summarize_row(x, 'phase_name') for x in data.get('phase_logic', [])[1:3]],
            'execution_patterns': [summarize_row(x, 'pattern_name') for x in data.get('execution_patterns', [])[1:3]],
            'decision_cases': [summarize_case(x) for x in data.get('decision_cases', [])[1:3]],
        }
    }

def main():
    print(json.dumps(select_bundle(json.load(sys.stdin)), indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
