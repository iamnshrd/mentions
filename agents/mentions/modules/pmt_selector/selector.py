from __future__ import annotations

import re

from agents.mentions.module_contracts import ensure_dict, ensure_list


CATEGORY_PRIORITY = [
    'pricing_signals',
    'execution_patterns',
    'phase_logic',
    'crowd_mistakes',
    'decision_cases',
    'speaker_profiles',
]

GENERIC_ANALOG_TERMS = {'generic', 'broad', 'macro', 'template', 'general case'}
TOPIC_TOKENS = ['iran', 'oil', 'nuclear', 'deal', 'hormuz', 'tariff', 'fed', 'inflation']
FORMAT_TOKENS = ['speech', 'interview', 'q&a', 'press conference', 'briefing', 'prepared remarks']


def select_pmt_evidence(query: str, frame: dict, market_prior: dict, pmt_knowledge: dict) -> dict:
    frame = ensure_dict(frame)
    market_prior = ensure_dict(market_prior)
    pmt_knowledge = ensure_dict(pmt_knowledge)

    ranked = {key: _rank_category(query, frame, market_prior, key, ensure_list(pmt_knowledge.get(key, []))) for key in CATEGORY_PRIORITY}

    selected = {
        'selected_pricing_signal': _top_row(ranked, 'pricing_signals'),
        'selected_execution_pattern': _top_row(ranked, 'execution_patterns'),
        'selected_phase_logic': _top_row(ranked, 'phase_logic'),
        'selected_crowd_mistake': _top_row(ranked, 'crowd_mistakes'),
        'selected_analog': _top_row(ranked, 'decision_cases'),
        'selected_speaker_profile': _top_row(ranked, 'speaker_profiles'),
        'selection_rationale': _build_rationale(frame, market_prior, ranked),
        'selection_summary': _build_summary(ranked),
        'rejected_candidates': _build_rejections(ranked),
    }
    return selected


def _rank_category(query: str, frame: dict, market_prior: dict, category: str, rows: list[dict]) -> list[dict]:
    route = (frame.get('route', '') or '').lower()
    regime = (market_prior.get('market_regime', '') or '').lower()
    query_lower = (query or '').lower()
    scored = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text_blob = ' '.join(str(v) for v in row.values() if isinstance(v, (str, int, float))).lower()
        score, reasons = _score_row(query_lower, route, regime, category, text_blob, row)
        enriched = dict(row)
        enriched['_selection_score'] = score
        enriched['_selection_reasons'] = reasons
        scored.append(enriched)
    scored.sort(key=lambda item: item.get('_selection_score', 0), reverse=True)
    return scored


def _score_row(query_lower: str, route: str, regime: str, category: str, text_blob: str, row: dict) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    penalties = []
    query_topics = [token for token in TOPIC_TOKENS if token in query_lower]
    query_formats = [token for token in FORMAT_TOKENS if token in query_lower]
    query_speaker = _infer_query_speaker(query_lower)

    for token in TOPIC_TOKENS + ['trump', 'speech', 'interview']:
        if token in query_lower and token in text_blob:
            score += 2
            reasons.append(f'token_match:{token}')
    if route and route in text_blob:
        score += 2
        reasons.append(f'route_match:{route}')
    if regime and regime in text_blob:
        score += 1
        reasons.append(f'regime_match:{regime}')

    apply_topic_penalty = category != 'speaker_profiles'
    apply_format_penalty = category not in {'speaker_profiles', 'crowd_mistakes'}

    if query_topics and not any(topic in text_blob for topic in query_topics):
        if apply_topic_penalty:
            score -= 3
            penalties.append('topic_mismatch')
    elif query_topics:
        score += len([topic for topic in query_topics if topic in text_blob])
        reasons.append('topic_alignment')
    if query_formats and not any(fmt in text_blob for fmt in query_formats):
        if apply_format_penalty:
            score -= 2
            penalties.append('format_mismatch')
    elif query_formats:
        score += 2
        reasons.append('format_alignment')

    if category == 'speaker_profiles':
        speaker_name = (row.get('speaker_name') or '').lower()
        if query_speaker and query_speaker in speaker_name:
            score += 4
            reasons.append('speaker_exact_match')
        elif query_speaker and speaker_name and query_speaker not in speaker_name:
            score -= 3
            penalties.append('speaker_mismatch')
    elif category == 'phase_logic':
        if any(token in query_lower for token in ['speech', 'interview', 'briefing', 'press conference']) and any(token in text_blob for token in ['prepared', 'q&a', 'interview', 'remarks', 'setup', 'briefing', 'press conference']):
            score += 3
            reasons.append('format_phase_match')
        if 'speech' in query_lower and 'q&a' in text_blob and 'speech' not in text_blob:
            score -= 2
            penalties.append('qna_only_mismatch')
    elif category == 'pricing_signals':
        if any(token in text_blob for token in ['overpriced', 'underpriced', 'ev', 'price']):
            score += 2
            reasons.append('pricing_language_match')
    elif category == 'execution_patterns':
        if any(token in text_blob for token in ['passive', 'aggressive', 'ladder', 'entry', 'execution']):
            score += 2
            reasons.append('execution_language_match')
    elif category == 'decision_cases':
        if any(token in text_blob for token in ['similar', 'case', 'q&a', 'speech', 'interview', 'briefing']):
            score += 1
            reasons.append('case_structure_match')
        if any(term in text_blob for term in GENERIC_ANALOG_TERMS):
            score -= 2
            penalties.append('generic_case_penalty')
        if query_topics and not any(topic in text_blob for topic in query_topics):
            score -= 2
            penalties.append('analog_topic_mismatch')
    elif category == 'crowd_mistakes':
        if any(token in text_blob for token in ['crowd', 'overpay', 'mistake', 'wrong', 'lying']):
            score += 2
            reasons.append('crowd_mistake_language_match')

    reasons.extend(penalties)
    return score, reasons


def _infer_query_speaker(query_lower: str) -> str:
    if re.search(r'\btrump\b', query_lower):
        return 'trump'
    if re.search(r'\bfed\b', query_lower):
        return 'fed'
    return ''


def _top_row(ranked: dict, key: str) -> dict:
    rows = ensure_list(ranked.get(key, []))
    return rows[0] if rows else {}


def _build_rationale(frame: dict, market_prior: dict, ranked: dict) -> list[str]:
    rationale = []
    regime = market_prior.get('market_regime', '')
    if regime:
        rationale.append(f'market_regime={regime}')
    route = frame.get('route', '')
    if route:
        rationale.append(f'route={route}')
    for key in CATEGORY_PRIORITY:
        rows = ensure_list(ranked.get(key, []))
        if rows:
            rationale.append(f'{key}:score={rows[0].get("_selection_score", 0)}')
    return rationale[:10]


def _build_summary(ranked: dict) -> dict:
    return {
        key: {
            'count': len(ensure_list(ranked.get(key, []))),
            'top_score': ensure_list(ranked.get(key, []))[0].get('_selection_score', 0) if ensure_list(ranked.get(key, [])) else 0,
        }
        for key in CATEGORY_PRIORITY
    }


def _build_rejections(ranked: dict) -> dict:
    out = {}
    for key in CATEGORY_PRIORITY:
        rows = ensure_list(ranked.get(key, []))
        out[key] = [
            {
                'score': row.get('_selection_score', 0),
                'label': row.get('signal_name') or row.get('pattern_name') or row.get('phase_name') or row.get('market_context') or row.get('speaker_name') or key,
                'reasons': row.get('_selection_reasons', []),
            }
            for row in rows[1:3]
        ]
    return out
