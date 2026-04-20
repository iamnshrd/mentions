from __future__ import annotations

EVENT_PRIOR_REGISTRY = {
    'dinner_media_room': {
        'title_tokens': ["correspondents' dinner", 'correspondents dinner', 'dinner', 'gala', 'banquet', 'roast'],
        'formats': [],
        'gets_right': 'здесь естественнее читать событие как media-room / social-format формат, а не как обычное policy event',
        'allow_overextended': {'opponents', 'media_culture'},
        'allow_late': {'opponents', 'media_culture'},
    },
    'press_briefing': {
        'title_tokens': ['press briefing', 'briefing room', 'press conference', 'presser'],
        'formats': ['press_conference'],
        'gets_right': 'здесь естественнее ожидать реактивный briefing-style формат с возможными журналистскими ответвлениями',
        'allow_overextended': {'opponents'},
        'allow_late': {'opponents'},
    },
    'sunday_show_interview': {
        'title_tokens': ['fox news sunday', 'meet the press', 'face the nation', 'state of the union', 'this week'],
        'formats': [],
        'gets_right': 'здесь естественнее ожидать moderated Sunday-show interview, где расширения идут через host-driven prompts, а не через свободный event sprawl',
        'allow_overextended': {'opponents', 'media_culture'},
        'allow_late': {'opponents', 'media_culture'},
    },
    'interview': {
        'title_tokens': [],
        'formats': ['interview'],
        'gets_right': 'здесь естественнее читать событие как host-driven Q&A, где боковые ветки могут открываться через вопросы, а не через основной prepared path',
        'allow_overextended': set(),
        'allow_late': set(),
    },
    'scripted_speech': {
        'title_tokens': [],
        'formats': ['speech', 'statement', 'press_release'],
        'gets_right': 'здесь естественнее ожидать более узкий scripted path, а не широкий набор спонтанных тематических уходов',
        'allow_overextended': set(),
        'allow_late': set(),
    },
    'conference_coalition': {
        'title_tokens': ['turning point', 'red wall'],
        'formats': ['conference'],
        'gets_right': 'рынок, скорее всего, правильно считывает activist / coalition framing события, а не чисто policy-specific формат',
        'allow_overextended': {'opponents', 'media_culture'},
        'allow_late': {'opponents'},
    },
    'rally': {
        'title_tokens': ['rally', 'campaign stop', 'campaign event'],
        'formats': ['rally'],
        'gets_right': 'здесь естественнее ждать широкий crowd-facing rhetorical mix, а не аккуратно ограниченный policy-only path',
        'allow_overextended': set(),
        'allow_late': set(),
    },
}


def detect_event_prior_mode(event_title: str, fmt: str) -> str:
    title = (event_title or '').lower()
    fmt = (fmt or '').lower()
    for mode, cfg in EVENT_PRIOR_REGISTRY.items():
        if any(token in title for token in cfg.get('title_tokens', [])):
            return mode
        if fmt and fmt in cfg.get('formats', []):
            return mode
    return 'default'


def get_event_prior(mode: str) -> dict:
    return EVENT_PRIOR_REGISTRY.get(mode, {})
