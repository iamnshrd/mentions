from __future__ import annotations


def evaluate_media_paths(event_ctx: dict | None, media_context: dict | None) -> dict:
    event_ctx = event_ctx or {}
    media_context = media_context or {}

    likely_topics = [str(topic).strip() for topic in (event_ctx.get('likely_topics') or []) if str(topic).strip()]
    topic_centrality = 'weak'
    if likely_topics:
        topic_centrality = 'adjacent'

    direct_topic_terms = {
        'iran', 'iranian', 'ufo', 'uap', 'tariff', 'tax day', 'no tax on tips',
        'border', 'immigration', 'china', 'ukraine', 'israel'
    }
    if any(topic.lower() in direct_topic_terms for topic in likely_topics):
        topic_centrality = 'core'

    show_type = (media_context.get('show_type') or '').lower()
    host_control = (media_context.get('host_control') or '').lower()
    realistic_paths = list(media_context.get('realistic_paths') or [])
    weak_paths = list(media_context.get('weak_paths') or [])
    blocked_paths: list[str] = []

    if host_control == 'high' and 'agenda_native_path' not in realistic_paths and topic_centrality != 'core':
        blocked_paths.append('agenda_native_path')
    if show_type in {'generic_tv_hit', 'news_interview', 'sunday_show'}:
        if 'closing_riff_path' not in weak_paths:
            weak_paths.append('closing_riff_path')
    if topic_centrality == 'core':
        if 'agenda_native_path' not in realistic_paths:
            realistic_paths.append('agenda_native_path')
    else:
        if 'bridge_path' not in weak_paths:
            weak_paths.append('bridge_path')

    confidence = 'medium'
    if topic_centrality == 'core' and host_control == 'high':
        confidence = 'medium'
    elif topic_centrality == 'weak':
        confidence = 'low'

    return {
        'topic_centrality': topic_centrality,
        'realistic_paths': list(dict.fromkeys(realistic_paths)),
        'weak_paths': list(dict.fromkeys(weak_paths)),
        'blocked_paths': list(dict.fromkeys(blocked_paths)),
        'path_confidence': confidence,
    }
