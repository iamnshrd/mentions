from __future__ import annotations


def ru_conclusion_note(state: str) -> str:
    mapping = {
        'event-and-core-aligned': 'Свежий новостной фон и transcript core одновременно указывают прямо на само событие.',
        'news-and-transcript-aligned': 'Свежий новостной фон и исторические аналогии по транскриптам указывают на одну и ту же картину события.',
        'ambient-news-only': 'Свежий новостной фон есть, но это скорее общий режимный контекст, чем прямое подтверждение события.',
        'topic-led-news-only': 'Свежий новостной фон есть, но он в основном поддерживает соседние темы, а не само событие напрямую.',
        'event-news-with-limited-transcripts': 'Свежий новостной фон уже есть, но историческая аналогия пока ограничена.',
        'generic-transcript-only': 'Транскриптная опора есть, но она пока больше похожа на общий режимный фон, чем на event-native аналогию.',
        'spillover-transcript-only': 'Транскриптная аналогия есть, но она больше похожа на spillover, чем на прямую event support.',
        'transcript-stronger-than-news': 'Исторические аналогии по транскриптам пока сильнее, чем свежий новостной фон.',
        'empty': '',
    }
    return mapping.get(state, state)


def event_read_sentence(event_structure: str, topic_centrality: str, historical_support: str) -> str:
    parts = []
    if event_structure == 'semi-open':
        parts.append('Это не полностью заскриптованное выступление, а более открытый формат с пространством для живых ответвлений.')
    elif event_structure == 'scripted':
        parts.append('Это скорее заскриптованное выступление, чем открытый реактивный формат.')
    else:
        parts.append('Формат события пока выглядит смешанным и не до конца зафиксированным.')

    if topic_centrality == 'core-topic':
        parts.append('Целевая тема выглядит центральной для самого события.')
    elif topic_centrality == 'adjacent-topic':
        parts.append('Целевая тема выглядит релевантной, но не единственным фокусом события.')
    else:
        parts.append('Целевая тема пока слабо заземлена в текущем контексте события.')

    if historical_support == 'strong':
        parts.append('Исторические аналогии по транскриптам хорошо поддерживают такую интерпретацию.')
    elif historical_support == 'partial':
        parts.append('Исторические аналогии по транскриптам поддерживают такую интерпретацию лишь частично.')

    return ' '.join(parts).strip()


def format_read_sentence(event_ctx: dict) -> str:
    fmt = (event_ctx.get('format') or '').lower()
    qa = (event_ctx.get('qa_likelihood') or '').lower()
    if fmt == 'panel':
        base = 'Формат ближе к `Roundtable` / panel'
    elif fmt == 'press_conference':
        base = 'Формат ближе к пресс-конференции'
    elif fmt == 'speech':
        base = 'Формат ближе к выступлению'
    else:
        base = 'Формат события пока описывается только общими чертами'

    qa_map = {
        'high': 'с высокой вероятностью вопросов и ответов',
        'medium': 'с умеренной вероятностью вопросов и ответов',
        'low': 'с низкой вероятностью вопросов и ответов',
    }
    qa_text = qa_map.get(qa, 'с неясной вероятностью вопросов и ответов')
    return f'{base}, {qa_text}.'


def ru_match_reasons(reasons: list[str]) -> str:
    mapping = {
        'same-speaker': 'тот же спикер',
        'same-format': 'тот же формат',
        'same-topic': 'та же тема',
        'media-format': 'тот же медиа-формат',
    }
    out = [mapping.get(reason, reason) for reason in reasons]
    return ', '.join(out)
