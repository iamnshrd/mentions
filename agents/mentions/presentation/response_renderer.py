from __future__ import annotations

import json

from agents.mentions.presentation.profile_renderers import build_output_profiles
from agents.mentions.presentation.normalizer import normalize_confidence, normalize_confidence_scope, normalize_route


def render_user_response(query: str, frame: dict, synthesis: dict,
                         mode: str = 'deep', output_format: str = 'text',
                         **_kwargs) -> str:
    if output_format == 'json':
        return json.dumps({
            'query': query,
            'frame': frame,
            'synthesis': synthesis,
        }, ensure_ascii=False, indent=2)

    analysis_profiles = synthesis.get('analysis_profiles') or {}
    rendered_profiles = build_output_profiles(query, analysis_profiles) if analysis_profiles else {}

    if mode == 'quick':
        return rendered_profiles.get('telegram_brief') or _render_quick_fallback(synthesis)
    return _render_deep_fallback(query, frame, synthesis, rendered_profiles)


def _render_quick_fallback(synthesis: dict) -> str:
    market_summary = synthesis.get('market_summary', '')
    signal = synthesis.get('signal_assessment', {}) or {}
    conclusion = synthesis.get('conclusion', '')
    confidence = synthesis.get('confidence', 'low')

    parts = []
    if market_summary:
        parts.append(market_summary)
    if signal.get('verdict'):
        verdict = signal['verdict']
        strength = signal.get('signal_strength', '')
        parts.append(f'Сигнал: {verdict} ({strength})' if strength else f'Сигнал: {verdict}')
    if conclusion:
        parts.append(conclusion)
    parts.append(f'Уверенность: {confidence}.')
    return '\n\n'.join(p for p in parts if p)


def _render_deep_fallback(query: str, frame: dict, synthesis: dict, rendered_profiles: dict | None = None) -> str:
    rendered_profiles = rendered_profiles or {}
    trade_memo = rendered_profiles.get('trade_memo') or {}
    investor_note = rendered_profiles.get('investor_note') or ''
    if trade_memo:
        strike_line = trade_memo.get('strike_list', '')
        strike_block = f"\nСтрайки: {strike_line}" if strike_line else ''
        return (
            f"Рынок: {trade_memo.get('query', query)}\n"
            f"Тезис: {trade_memo.get('thesis', '')}\n"
            f"Ориентир по вероятности/цене: {trade_memo.get('fair_value_view', '')}\n"
            f"Почему сейчас: {trade_memo.get('why_now', '')}\n"
            f"Ключевой риск: {trade_memo.get('key_risk', '')}\n"
            f"Инвалидация: {trade_memo.get('invalidation', '')}\n"
            f"Что делать: {trade_memo.get('recommended_action', '')}"
            f"{strike_block}"
        ).strip()
    if investor_note:
        return investor_note

    route = frame.get('route', 'general-market')
    confidence = synthesis.get('confidence', 'low')
    market_summary = synthesis.get('market_summary', '')
    reasoning = synthesis.get('reasoning_chain', []) or []
    conclusion = synthesis.get('conclusion', '')

    confidence_scope = synthesis.get('confidence_scope') or ''
    confidence_label = synthesis.get('confidence_label') or ''
    rendered_route = normalize_route(route)
    rendered_confidence = normalize_confidence(confidence)
    confidence_line = f'Маршрут: {rendered_route} | Уверенность: {rendered_confidence}'
    if confidence_scope or confidence_label:
        scope_note = normalize_confidence_scope(confidence_scope) if confidence_scope else confidence_label
        confidence_line = f'{confidence_line} ({scope_note})'

    parts = [f'Разбор: {query}', confidence_line, '─' * 48]
    if market_summary:
        parts.append('Сводка рынка:')
        parts.append(market_summary)
    if reasoning:
        parts.append('Логика:')
        for i, step in enumerate(reasoning, 1):
            parts.append(f'  {i}. {step}')
    if conclusion:
        parts.append('Вывод:')
        parts.append(conclusion)
    return '\n\n'.join(part for part in parts if part)
