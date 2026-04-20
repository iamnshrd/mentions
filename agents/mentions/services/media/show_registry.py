from __future__ import annotations


MEDIA_SHOW_REGISTRY = {
    'fox_news_sunday': {
        'title_tokens': ['fox news sunday'],
        'outlet': 'Fox News',
        'program_type': 'sunday_show',
        'host_control': 'high',
        'segment_shape': 'topic_bounded',
        'topic_breadth': 'medium',
        'panel_mode': 'low',
        'style': 'moderated interview',
    },
    'hannity': {
        'title_tokens': ['hannity'],
        'outlet': 'Fox News',
        'program_type': 'prime_time_host_show',
        'host_control': 'high',
        'segment_shape': 'host_driven',
        'topic_breadth': 'medium',
        'panel_mode': 'low',
        'style': 'friendly ideological interview',
    },
    'the_ingraham_angle': {
        'title_tokens': ['ingraham', 'ingraham angle'],
        'outlet': 'Fox News',
        'program_type': 'prime_time_host_show',
        'host_control': 'high',
        'segment_shape': 'host_driven',
        'topic_breadth': 'medium',
        'panel_mode': 'low',
        'style': 'host-driven ideological interview',
    },
    'jesse_watters_primetime': {
        'title_tokens': ['jesse watters', 'watters'],
        'outlet': 'Fox News',
        'program_type': 'prime_time_host_show',
        'host_control': 'high',
        'segment_shape': 'host_driven',
        'topic_breadth': 'medium',
        'panel_mode': 'low',
        'style': 'reactive commentary interview',
    },
    'special_report_bret_baier': {
        'title_tokens': ['bret baier', 'special report'],
        'outlet': 'Fox News',
        'program_type': 'news_interview',
        'host_control': 'high',
        'segment_shape': 'topic_bounded',
        'topic_breadth': 'medium',
        'panel_mode': 'low',
        'style': 'structured news interview',
    },
    'fox_and_friends': {
        'title_tokens': ['fox & friends', 'fox and friends'],
        'outlet': 'Fox News',
        'program_type': 'morning_show',
        'host_control': 'medium',
        'segment_shape': 'looser_host_mix',
        'topic_breadth': 'high',
        'panel_mode': 'medium',
        'style': 'friendly morning show segment',
    },
    'generic_fox_news_hit': {
        'title_tokens': ['fox news'],
        'outlet': 'Fox News',
        'program_type': 'generic_tv_hit',
        'host_control': 'high',
        'segment_shape': 'topic_bounded',
        'topic_breadth': 'medium',
        'panel_mode': 'unknown',
        'style': 'generic cable news appearance',
    },
    'meet_the_press': {
        'title_tokens': ['meet the press'],
        'outlet': 'NBC',
        'program_type': 'sunday_show',
        'host_control': 'high',
        'segment_shape': 'topic_bounded',
        'topic_breadth': 'medium',
        'panel_mode': 'low',
        'style': 'moderated sunday interview',
    },
    'face_the_nation': {
        'title_tokens': ['face the nation'],
        'outlet': 'CBS',
        'program_type': 'sunday_show',
        'host_control': 'high',
        'segment_shape': 'topic_bounded',
        'topic_breadth': 'medium',
        'panel_mode': 'low',
        'style': 'moderated sunday interview',
    },
    'this_week': {
        'title_tokens': ['this week'],
        'outlet': 'ABC',
        'program_type': 'sunday_show',
        'host_control': 'high',
        'segment_shape': 'topic_bounded',
        'topic_breadth': 'medium',
        'panel_mode': 'low',
        'style': 'moderated sunday interview',
    },
    'state_of_the_union': {
        'title_tokens': ['state of the union'],
        'outlet': 'CNN',
        'program_type': 'sunday_show',
        'host_control': 'high',
        'segment_shape': 'topic_bounded',
        'topic_breadth': 'medium',
        'panel_mode': 'low',
        'style': 'moderated sunday interview',
    },
}


def detect_media_show(event_title: str) -> tuple[str, dict]:
    title = (event_title or '').lower()
    for show_key, cfg in MEDIA_SHOW_REGISTRY.items():
        if any(token in title for token in cfg.get('title_tokens', [])):
            return show_key, cfg
    return '', {}
