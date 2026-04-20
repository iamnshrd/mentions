from __future__ import annotations


MEDIA_PRIOR_REGISTRY = {
    'cable_news_short_hit': {
        'title_tokens': ['fox news', 'hannity', 'ingraham', 'watters', 'bret baier'],
        'formats': ['interview'],
        'host_control': 'high',
        'segment_shape': 'topic_bounded',
        'realistic_paths': ['direct_prompt_path', 'reactive_path'],
        'weak_paths': ['bridge_path', 'closing_riff_path'],
        'gets_right': 'здесь естественнее ждать host-driven телевизионный сегмент, где mention чаще приходит через prompt или реактивный ответ, а не через свободный event sprawl',
    },
    'sunday_show_interview': {
        'title_tokens': ['fox news sunday', 'meet the press', 'face the nation', 'state of the union', 'this week'],
        'formats': ['interview'],
        'host_control': 'high',
        'segment_shape': 'topic_bounded',
        'realistic_paths': ['direct_prompt_path', 'reactive_path'],
        'weak_paths': ['bridge_path'],
        'gets_right': 'здесь естественнее ждать moderated Sunday-show interview, где расширения открываются через host prompts, а не через свободное саморасширение темы',
    },
    'host_driven_interview': {
        'title_tokens': ['interview'],
        'formats': ['interview'],
        'host_control': 'high',
        'segment_shape': 'topic_bounded',
        'realistic_paths': ['direct_prompt_path', 'reactive_path', 'bridge_path'],
        'weak_paths': ['closing_riff_path'],
        'gets_right': 'это лучше читать как host-driven interview format, где релевантность темы сама по себе не равна реальному path to mention',
    },
}


def detect_media_prior_mode(event_title: str, fmt: str) -> str:
    title = (event_title or '').lower()
    fmt = (fmt or '').lower()
    for mode, cfg in MEDIA_PRIOR_REGISTRY.items():
        if any(token in title for token in cfg.get('title_tokens', [])):
            return mode
        if fmt and fmt in cfg.get('formats', []) and mode == 'host_driven_interview':
            return mode
    return 'default'


def get_media_prior(mode: str) -> dict:
    return MEDIA_PRIOR_REGISTRY.get(mode, {})
