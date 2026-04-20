from __future__ import annotations

from mentions_domain.normalize import ensure_dict


def render_header(query: str, analysis_profiles: dict) -> str:
    supporting = ensure_dict(analysis_profiles.get('supporting_blocks', {}))
    market_prior = ensure_dict(supporting.get('market_prior', {}))
    title = (market_prior.get('title') or '').strip()
    compact = compact_title(title, query)
    if compact:
        return compact
    if title:
        return title
    return (query or '').strip()


def compact_title(title: str, query: str = '') -> str:
    value = (title or '').strip()
    combined = ' '.join([value, query or '']).strip()
    lowered = combined.lower()
    speaker = ''
    if 'donald trump' in lowered or 'trump' in lowered:
        speaker = 'Trump'
    elif 'zohran mamdani' in lowered or 'mamdani' in lowered:
        speaker = 'Mamdani'

    format_label = ''
    if 'interview' in lowered:
        format_label = 'interview'
    elif 'speech' in lowered:
        format_label = 'speech'
    elif 'press conference' in lowered or 'briefing' in lowered:
        format_label = 'press conference'
    elif 'mention' in lowered or 'say' in lowered:
        format_label = 'mention market'

    topic = ''
    markers = ['iran', 'oil', 'nuclear', 'deal', 'hormuz', 'fed', 'rates', 'inflation']
    for marker in markers:
        if marker in lowered:
            topic = marker.capitalize()
            break

    parts = [part for part in [speaker, format_label, topic] if part]
    if len(parts) >= 2:
        return ' / '.join(parts)
    if value and len(value) <= 80:
        return value
    if speaker and topic:
        return f'{speaker} / {topic}'
    if speaker and format_label:
        return f'{speaker} / {format_label}'
    if format_label and topic:
        return f'{format_label} / {topic}'
    return value
