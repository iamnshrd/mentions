from __future__ import annotations

import re
import sqlite3

from agents.mentions.config import PMT_KNOWLEDGE_DB

SYNONYMS = {
    'trump': ['trump', 'potus', 'president'],
    'q&a': ['q&a', 'qa', 'questions', 'reporters', 'open press', 'press conference', 'briefing'],
    'interview': ['interview', 'sitdown'],
    'market-impact': ['size', 'sizing', 'fill', 'fills', 'liquidity', 'market impact'],
    'current-events': ['fresh news', 'breaking', 'changed setup', 'stale history'],
    'phase': ['prepared remarks', 'q&a', 'late path', 'opening'],
}

TABLE_CONFIG = {
    'pricing_signals': ('pricing_signals', ['id', 'signal_name', 'signal_type', 'description', 'interpretation', 'typical_action', 'confidence']),
    'crowd_mistakes': ('crowd_mistakes', ['id', 'mistake_name', 'mistake_type', 'description', 'why_it_happens', 'how_to_exploit']),
    'phase_logic': ('phase_logic', ['id', 'phase_name', 'description', 'what_becomes_more_likely', 'what_becomes_less_likely', 'common_pricing_errors', 'execution_notes']),
    'execution_patterns': ('execution_patterns', ['id', 'pattern_name', 'execution_type', 'description', 'best_used_when', 'avoid_when', 'risk_note']),
    'decision_cases': ('decision_cases', ['id', 'market_context', 'setup', 'decision', 'reasoning', 'risk_note', 'outcome_note', 'tags']),
    'speaker_profiles': ('speaker_profiles', ['id', 'speaker_name', 'speaker_type', 'description', 'behavior_style', 'favored_topics', 'avoid_topics', 'qna_style', 'adaptation_notes']),
}


def query_pmt_knowledge_bundle(event_title: str = '', speaker: str = '', fmt: str = '', freeform: str = '', top: int = 3) -> dict:
    query_terms = _build_query_terms(event_title, speaker, fmt, freeform)
    conn = sqlite3.connect(PMT_KNOWLEDGE_DB)
    conn.row_factory = sqlite3.Row
    try:
        result = {'query_terms': sorted(query_terms)}
        for out_key, (table, cols) in TABLE_CONFIG.items():
            scored = []
            for row in conn.execute(f"SELECT {','.join(cols)} FROM {table}").fetchall():
                row_dict = dict(row)
                blob = ' '.join(str(row_dict.get(col, '')) for col in cols if col != 'id')
                score, hits = _score_text(blob, query_terms)
                if score <= 0:
                    continue
                row_dict['_score'] = score
                row_dict['_hits'] = hits
                scored.append(row_dict)
            scored.sort(key=lambda x: (-x['_score'], x['id']))
            result[out_key] = scored[:top]
        return result
    finally:
        conn.close()


def _build_query_terms(event_title: str, speaker: str, fmt: str, freeform: str) -> set[str]:
    query_terms = set()
    for text in [event_title, speaker, fmt, freeform]:
        query_terms |= _tokenize(text)
    if speaker.lower() == 'trump':
        query_terms |= _expand_terms(['trump', 'q&a', 'current-events'])
    if fmt.lower() == 'interview':
        query_terms |= _expand_terms(['interview', 'q&a', 'current-events'])
    return query_terms


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9\+\-']+", (text or '').lower()))


def _expand_terms(terms: list[str]) -> set[str]:
    out = set()
    for term in terms:
        t = term.lower().strip()
        out.add(t)
        out.update(SYNONYMS.get(t, []))
    return out


def _score_text(blob: str, query_terms: set[str]) -> tuple[int, list[str]]:
    lowered = (blob or '').lower()
    score = 0
    hits = []
    for term in query_terms:
        if term and term in lowered:
            weight = 3 if ' ' in term else 1
            score += weight
            hits.append(term)
    return score, sorted(set(hits))[:10]
