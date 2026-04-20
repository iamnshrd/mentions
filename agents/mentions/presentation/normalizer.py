from __future__ import annotations


def normalize_confidence(value: str) -> str:
    mapping = {
        'high': 'высокая',
        'medium': 'умеренная',
        'low': 'низкая',
    }
    return mapping.get((value or '').lower(), value)


def normalize_confidence_scope(value: str) -> str:
    mapping = {
        'context-grounding': 'контекст и заземлённость',
        'analysis-confidence': 'качество анализа',
    }
    return mapping.get((value or '').lower(), value)


def normalize_route(value: str) -> str:
    mapping = {
        'speaker-event': 'speaker-event',
        'general-market': 'general-market',
        'price-movement': 'price-movement',
    }
    return mapping.get((value or '').lower(), value)


def normalize_analysis_confidence(value: str) -> str:
    mapping = {
        'high': 'сильная',
        'medium': 'средняя',
        'low': 'слабая',
    }
    return mapping.get((value or '').lower(), value)


def normalize_format(value: str) -> str:
    mapping = {
        'interview': 'интервью',
        'hearing': 'hearing',
        'speech': 'выступление',
        'panel': 'панельная дискуссия',
        'press_conference': 'пресс-конференция',
    }
    return mapping.get((value or '').lower(), value)


def normalize_level(value: str) -> str:
    mapping = {
        'high': 'высокая',
        'medium': 'умеренная',
        'low': 'низкая',
        'strong': 'сильная',
        'weak': 'слабая',
    }
    return mapping.get((value or '').lower(), value)


def normalize_difficulty(value: str) -> str:
    mapping = {
        'hard': 'высокая',
        'medium': 'умеренная',
        'easy': 'низкая',
    }
    return mapping.get((value or '').lower(), value)


def normalize_venue(value: str) -> str:
    if (value or '').strip().lower() == 'venue not identified from available data':
        return 'пока не подтверждена'
    return value


def normalize_signal_verdict(value: str) -> str:
    mapping = {
        'bullish': 'поддерживает расширение read',
        'bearish': 'сдерживает расширение read',
        'mixed': 'смешанный',
    }
    return mapping.get((value or '').lower(), value)


PATH_LABELS = {
    'direct_prompt_path': 'если ведущий сам поднимет тему',
    'reactive_path': 'если тема всплывёт как реакция на другой вопрос',
    'bridge_path': 'если спикер сам попробует перевести разговор в эту сторону',
    'agenda_native_path': 'если тема встроена в основной предмет сегмента',
    'closing_riff_path': 'если тема появится в финальном риффе или завершающей реплике',
}

SHOW_LABELS = {
    'generic_fox_news_hit': 'типичный короткий Fox News сегмент',
    'fox_news_sunday': 'модерируемое интервью формата Fox News Sunday',
    'hannity': 'host-driven интервью формата Hannity',
    'the_ingraham_angle': 'host-driven сегмент формата Ingraham',
    'jesse_watters_primetime': 'короткий комментарийный сегмент формата Watters',
    'special_report_bret_baier': 'структурированное news-интервью формата Bret Baier',
    'fox_and_friends': 'более свободный утренний телевизионный сегмент',
    'meet_the_press': 'модерируемое интервью формата Meet the Press',
    'face_the_nation': 'модерируемое интервью формата Face the Nation',
    'this_week': 'модерируемое интервью формата This Week',
    'state_of_the_union': 'модерируемое интервью формата State of the Union',
}

FAMILY_LABELS = {
    'war_geopolitics': 'геополитический контекст',
    'border_immigration': 'погранично-иммиграционный контекст',
    'tariff_policy_legal': 'тарифно-правовой контекст',
    'trade_industry_manufacturing': 'торгово-производственный контекст',
    'broad_economy_prices': 'макроэкономический фон',
    'energy_industry_manufacturing': 'энергетико-промышленный фон',
    'opponents_media_attacks': 'ветка медиа/политических оппонентов',
    'gop_coalition_internal': 'внутрикоалиционная политическая ветка',
}


def normalize_market_phrase(text: str) -> str:
    value = text or ''
    replacements = {
        'institutional language': 'институциональный язык',
        'institutional register': 'институциональный речевой регистр',
        'loaded words': 'политически нагруженные формулировки',
        'loaded phrasing': 'политически нагруженные формулировки',
        'exact-word risk': 'риск, что тема будет затронута без exact keyword hit',
        'topic hit': 'затрагивание темы',
        'contract hit': 'exact keyword hit по контракту',
        'native wording': 'естественная для спикера формулировка',
        'generic cable news appearance': 'типичный короткий cable-news сегмент',
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def normalize_path_label(value: str) -> str:
    return PATH_LABELS.get(value or '', value or '')


def normalize_show_family(value: str) -> str:
    return SHOW_LABELS.get(value or '', value or '')


def normalize_family_label(value: str) -> str:
    return FAMILY_LABELS.get(value or '', value or '')


def normalize_key_risk(text: str) -> str:
    value = (text or '').strip()
    replacements = {
        'credible fresh reporting that the speaker focus shifted away from the topic would weaken the thesis': 'если появится надёжное свежее подтверждение, что спикер ушёл от темы, тезис ослабнет',
        'new primary-source text contradicting the current topical expectation would reduce confidence': 'если первоисточник прямо пойдёт против текущего ожидания по теме, уверенность снизится',
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def normalize_invalidation(text: str) -> str:
    value = (text or '').strip()
    replacements = {
        'fresh high-quality text evidence in the relevant event window': 'нужен свежий качественный текст именно в релевантном event window',
        'cleaner contract linkage or a confirmed exact market/event mapping': 'нужна более чистая привязка рынка к событию',
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def normalize_action_text(text: str) -> str:
    value = (text or '').strip()
    replacements = {
        'Пока no-trade, подтверждение слишком слабое.': 'Пока наблюдать, подтверждение слишком слабое.',
        'Пока no-trade, апдейт не оправдан': 'Пока наблюдать, апдейт не оправдан.',
        'слишком много противоречий в evidence': 'слишком много противоречий в подтверждениях',
        'Пока наблюдать, для trade view рано.': 'Пока наблюдать, для полноценного вывода ещё рано.',
        'Пока наблюдать, prior слишком хрупкий.': 'Пока наблюдать, рыночная базовая линия слишком хрупкая.',
        'Пока наблюдать, конфликтов слишком много.': 'Пока наблюдать, сигнал слишком конфликтный.',
        'Пока наблюдать, апдейт пока не собран.': 'Пока наблюдать, апдейт пока не собран.',
        'Пока наблюдать, эдж слишком маленький.': 'Пока наблюдать, сигнал слишком слабый.',
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value
