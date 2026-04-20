from __future__ import annotations

from agents.mentions.presentation.header_renderer import render_header
from agents.mentions.presentation.normalizer import normalize_action_text, normalize_invalidation, normalize_key_risk
from agents.mentions.presentation.wording_adapter import apply_market_wording, clean_phrase


def build_output_profiles(query: str, analysis_profiles: dict) -> dict:
    return {
        'telegram_brief': render_telegram_brief(query, analysis_profiles),
        'trade_memo': render_trade_memo(query, analysis_profiles),
        'investor_note': render_investor_note(query, analysis_profiles),
    }


def render_telegram_brief(query: str, analysis_profiles: dict) -> str:
    card = _analysis_card(analysis_profiles)
    thesis = _finalize_phrase(card.get('thesis', ''))
    action = _humanize_action(_compress_action(_finalize_phrase(card.get('action', ''))))
    why_now = _compress_why_now(_finalize_phrase(_why_now_text(analysis_profiles, card)))
    fair_value = _compress_fair_value(_finalize_phrase(card.get('fair_value_view', '')))
    strike_line = _render_strike_line(analysis_profiles)
    header = render_header(query, analysis_profiles)
    body = f"Тезис: {thesis}\nОриентир по вероятности/цене: {fair_value}\nПочему сейчас: {why_now}\nЧто делать: {action}"
    if strike_line:
        body = f"{body}\nСтрайки: {strike_line}"
    return f"{header}\n\n{body}".strip()


def render_trade_memo(query: str, analysis_profiles: dict) -> dict:
    card = _analysis_card(analysis_profiles)
    action = _compress_action(_finalize_phrase(card.get('action', '')))
    thesis = _finalize_phrase(card.get('thesis', ''))
    rendered_query = render_header(query, analysis_profiles)
    key_risk = _humanize_key_risk(_finalize_phrase(card.get('risk', '')))
    invalidation = _humanize_invalidation(_finalize_phrase(card.get('next_check', '')))
    return {
        'query': rendered_query,
        'thesis': thesis,
        'fair_value_view': _compress_fair_value(_finalize_phrase(card.get('fair_value_view', ''))),
        'why_now': _compress_why_now(_finalize_phrase(_why_now_text(analysis_profiles, card))),
        'key_risk': key_risk,
        'invalidation': invalidation,
        'recommended_action': _humanize_action(action),
        'strike_list': _render_strike_line(analysis_profiles),
        'summary_line': f"{thesis} | {_humanize_action(action)}",
    }


def render_investor_note(query: str, analysis_profiles: dict) -> str:
    card = _analysis_card(analysis_profiles)
    rendered_query = render_header(query, analysis_profiles)
    thesis = _finalize_phrase(card.get('thesis', ''))
    fair_value = _compress_fair_value(_finalize_phrase(card.get('fair_value_view', '')))
    why_now = _compress_why_now(_finalize_phrase(_why_now_text(analysis_profiles, card)))
    action = _humanize_action(_compress_action(_finalize_phrase(card.get('action', ''))))
    key_risk = _humanize_key_risk(_finalize_phrase(card.get('risk', '')))
    invalidation = _humanize_invalidation(_finalize_phrase(card.get('next_check', '')))
    strike_line = _render_strike_line(analysis_profiles)
    strike_block = f"\nСтрайки: {strike_line}" if strike_line else ''
    return (
        f"Инвесторская заметка: {rendered_query}\n"
        f"Тезис: {thesis}\n"
        f"Ориентир по вероятности/цене: {fair_value}\n"
        f"Почему сейчас: {why_now}\n"
        f"Ключевой риск: {key_risk}\n"
        f"Инвалидация: {invalidation}\n"
        f"Действие: {action}"
        f"{strike_block}"
    ).strip()


def _finalize_phrase(text: str) -> str:
    return apply_market_wording(clean_phrase(text or '')).strip()


def _compress_fair_value(text: str) -> str:
    value = (text or '').strip()
    replacements = {
        'Fair value view пока только ориентировочный, потому что policy не разрешает полный разбор.': 'пока это только ориентир по вероятности/цене, полного разбора ещё нет.',
        'Fair value пока остаётся привязан к рынку около': 'ориентир по вероятности/цене пока остаётся около',
        'Fair value view остаётся близко к рынку: примерно': 'ориентир по вероятности/цене остаётся близко к рынку: примерно',
        'Fair value around ': 'ориентир около ',
        'Fair value пока остаётся около рынка': 'ориентир по вероятности/цене пока остаётся около рынка',
        'fair value пока остаётся около рынка': 'ориентир по вероятности/цене пока остаётся около рынка',
        'only marginal drift': 'только слабый дрейф',
        'bounded move': 'ограниченный сдвиг',
        'market prior': 'рыночной базовой линии',
        'rerate': 'полноценный пересмотр цены',
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = value.replace('ориентир по вероятности/цене остаётся близко к рынку', 'остаётся близко к рынку')
    value = value.replace('ориентир по вероятности/цене пока остаётся около рынка', 'остаётся около рынка')
    value = value.replace('ориентир около ', 'около ')
    value = value.replace('fair value остаётся близко к рынку', 'остаётся близко к рынку')
    value = value.replace('fair value пока остаётся около рынка', 'остаётся около рынка')
    value = value.replace('fair value около ', 'около ')
    value = value.replace('fair value ', '')
    value = value.replace('Fair value ', '')
    value = value.strip()
    if value.startswith('около рынка'):
        value = 'остаётся около рынка' + value[len('около рынка'):]
    return value


def _compress_why_now(text: str) -> str:
    value = (text or '').strip()
    replacements = {
        'сила текстового подтверждения: ': 'текст: ',
        'свежих новостей по событию нет': 'свежих новостей нет',
        'подтверждающего transcript evidence нет': 'подтверждающего транскрипта нет',
        'PMT сигнал: ': 'PMT: ',
        'направление: ': 'направление: ',
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def _compress_action(text: str) -> str:
    value = (text or '').strip()
    replacements = {
        'Пока только наблюдать: policy не разрешает полноценный trade view.': 'Пока наблюдать, для полноценного вывода ещё рано.',
        'Пока наблюдать: market prior слишком хрупкий для агрессивного trade view.': 'Пока наблюдать, рыночная базовая линия слишком хрупкая.',
        'Пока наблюдать: conflict load слишком высокий.': 'Пока наблюдать, конфликтов слишком много.',
        'Пока наблюдать: posterior structure ещё слабая.': 'Пока наблюдать, апдейт пока не собран.',
        'Пока наблюдать: предполагаемый эдж над рынком слишком маленький.': 'Пока наблюдать, сигнал слишком слабый.',
        'Пока no-trade / наблюдать: апдейт не оправдан': 'Пока наблюдать, апдейт не оправдан',
        'Пока no-trade / monitor: апдейт не оправдан': 'Пока наблюдать, апдейт не оправдан',
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def _humanize_key_risk(text: str) -> str:
    return normalize_key_risk(text)


def _humanize_invalidation(text: str) -> str:
    return normalize_invalidation(text)


def _render_strike_line(analysis_profiles: dict) -> str:
    supporting = analysis_profiles.get('supporting_strikes') or []
    if not isinstance(supporting, list) or not supporting:
        return ''
    shown = supporting[:8]
    suffix = '' if len(supporting) <= 8 else f' + ещё {len(supporting) - 8}'
    return ', '.join(str(x) for x in shown if x) + suffix


def _humanize_action(text: str) -> str:
    return normalize_action_text(text)


def _analysis_card(analysis_profiles: dict) -> dict:
    analysis_profiles = analysis_profiles or {}
    card = analysis_profiles.get('analysis_card') or {}
    return {
        'thesis': card.get('thesis', analysis_profiles.get('thesis', '')),
        'fair_value_view': card.get('fair_value_view', analysis_profiles.get('fair_value_view', '')),
        'action': card.get('action', analysis_profiles.get('recommended_action', '')),
        'risk': card.get('risk', analysis_profiles.get('key_risk', '')),
        'next_check': card.get('next_check', analysis_profiles.get('invalidation', '')),
        'uncertainty': card.get('uncertainty', analysis_profiles.get('uncertainty', '')),
        'evidence': card.get('evidence', analysis_profiles.get('evidence_points', [])),
    }


def _why_now_text(analysis_profiles: dict, card: dict) -> str:
    why_now = analysis_profiles.get('why_now', '')
    if why_now:
        return why_now
    evidence = card.get('evidence', [])
    if isinstance(evidence, list) and evidence:
        return '; '.join(str(item) for item in evidence[:2] if item)
    return ''
