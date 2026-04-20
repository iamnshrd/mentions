from __future__ import annotations

import re

from agents.mentions.presentation.output_wording import apply_wording


def clean_phrase(text: str) -> str:
    value = (text or '').strip()
    protected = _protect_backticked_spans(value)
    value = protected['text']
    phrase_replacements = {
        'supports_yes': 'смещение скорее в сторону YES',
        'supports_no': 'смещение скорее в сторону NO',
        'full-conviction trade view': 'полноценный вывод',
        'maker-quality-beats-theoretical-ev': 'качество исполнения важнее теоретического EV',
        'bounded move': 'ограниченный сдвиг',
        'only marginal drift': 'только слабый дрейф',
        'stays close to market': 'остаётся близко к рынку',
        'market prior': 'рыночная базовая линия',
        'New transcript evidence': 'новый подтверждающий транскрипт',
        'Fresh reporting contradicts setup': 'свежее подтверждение ломает текущую рабочую картину',
        'fair value': 'ориентир по вероятности/цене',
        'baseline': 'базовая линия',
        'setup': 'рабочая картина',
    }
    word_replacements = {
        'weak': 'слабая',
        'moderate': 'умеренная',
        'strong': 'сильная',
        'none': 'отсутствует',
        'monitor': 'наблюдать',
        'edge': 'сигнал',
        'roughly': 'примерно',
        'pricing': 'ценообразование',
    }
    for source, target in phrase_replacements.items():
        value = value.replace(source, target)
    for source, target in word_replacements.items():
        value = re.sub(rf'\b{re.escape(source)}\b', target, value)
    return _restore_backticked_spans(value, protected['spans'])


def apply_market_wording(text: str) -> str:
    protected = _protect_backticked_spans(text)
    rendered = apply_wording(protected['text'])
    return _restore_backticked_spans(rendered, protected['spans'])


def _protect_backticked_spans(text: str) -> dict:
    spans: dict[str, str] = {}
    index = 0

    def repl(match: re.Match) -> str:
        nonlocal index
        token = f'__BACKTICK_SPAN_{index}__'
        spans[token] = match.group(0)
        index += 1
        return token

    protected = re.sub(r'`[^`]+`', repl, text or '')
    return {'text': protected, 'spans': spans}


def _restore_backticked_spans(text: str, spans: dict[str, str]) -> str:
    restored = text
    for token, original in spans.items():
        restored = restored.replace(token, original)
    return restored
