"""Chain-of-reasoning builder — construct an explicit reasoning chain for an analysis."""
from __future__ import annotations

import logging

log = logging.getLogger('mentions')


def build_reasoning_chain(query: str, frame: dict, market_summary: str,
                          signal: dict, transcript_context: str,
                          news: list) -> list[str]:
    """Build an ordered list of reasoning steps for the analysis.

    Each step is a short, declarative statement advancing toward the conclusion.
    Returns list of strings (the chain), ordered from observation to inference.
    """
    chain = []

    route = frame.get('route', 'general-market')
    category = frame.get('category', 'general')
    mode = frame.get('mode', 'deep')

    # Step 1: Establish context
    chain.append(f'Маршрут запроса: {route} (категория: {category})')

    # Step 2: Market data observation
    if market_summary and 'No live data' not in market_summary:
        # Extract the key fact line
        first_line = market_summary.split('\n')[0]
        chain.append(f'Рыночные данные: {first_line}')
    else:
        chain.append('Рыночные данные недоступны, разбор опирается на исторический / кэшированный контекст')

    # Step 3: Signal assessment
    if isinstance(signal, dict) and signal.get('verdict') != 'unclear':
        verdict = signal.get('verdict', '?')
        strength = signal.get('signal_strength', '?')
        factors = signal.get('factors', [])
        chain.append(f'Сигнальная оценка: {verdict} (сила: {strength})')
        for f in factors[:2]:
            chain.append(f'  Фактор: {f}')
    else:
        chain.append('Сигнальная оценка остаётся неясной, данных для классификации недостаточно')

    # Step 4: News context
    if news:
        headlines = [n.get('headline', '') for n in news[:2] if n.get('headline')]
        if headlines:
            chain.append(f'Свежий контекст: {headlines[0]}')

    # Step 5: Transcript/speaker evidence
    if transcript_context:
        first_line = transcript_context.split('\n')[0][:120]
        chain.append(f'Исторический speaker-контекст: {first_line}')
    else:
        if route in ('speaker-history', 'context-research', 'macro'):
            chain.append('Релевантных транскриптных аналогов для этого запроса пока не найдено')

    # Step 6: Route-specific reasoning
    route_inference = _route_inference(route, signal, transcript_context)
    if route_inference:
        chain.append(route_inference)

    # Step 7: Uncertainty label
    confidence = _estimate_confidence(market_summary, signal, transcript_context, news)
    chain.append(f'Оценка уверенности: {confidence}')

    return chain


def _route_inference(route: str, signal: dict, transcript_context: str) -> str:
    """Generate a route-specific inference step."""
    verdict = signal.get('verdict', 'unclear') if isinstance(signal, dict) else 'unclear'
    strength = signal.get('signal_strength', 'unknown') if isinstance(signal, dict) else 'unknown'

    if route == 'price-movement':
        if verdict == 'signal':
            return f'Движение цены похоже на {strength} сигнал, вероятно с внешним катализатором'
        return 'Паттерн движения цены пока неубедителен без явного катализатора'

    if route == 'macro':
        if transcript_context:
            return 'Макроконтекст: transcript corpus даёт релевантное позиционирование спикера'
        return 'Макроконтекст: транскриптных данных нет, приходится сильнее опираться на рыночное ценообразование'

    if route == 'speaker-history':
        if transcript_context:
            return 'История спикера найдена, её стоит сверять с текущим ценообразованием рынка'
        return 'История спикера по транскриптам недоступна, позиция остаётся слабозаземлённой'

    if route == 'signal-or-noise':
        if verdict in ('signal', 'noise'):
            return f'Классификация signal/noise: {verdict} (на score-based основе)'
        return 'Граница между signal и noise пока размыта, лучше дождаться дополнительных данных'

    if route == 'breaking-news':
        return 'Для breaking-news кейса важнее свежесть сигнала, рынок мог ещё не полностью это впитать'

    if route == 'trend-analysis':
        return 'Trend-analysis требует многоточечной истории, одного snapshot недостаточно'

    return ''


def _estimate_confidence(market_summary: str, signal: dict,
                         transcript_context: str, news: list) -> str:
    score = 0
    if market_summary and 'No live data' not in market_summary:
        score += 2
    if isinstance(signal, dict) and signal.get('verdict') != 'unclear':
        score += 1
    if transcript_context:
        score += 1
    if news:
        score += 1

    if score >= 4:
        return 'high, есть несколько подтверждающих источников'
    if score >= 2:
        return 'medium, данные частичные, но уже рабочие'
    if score >= 1:
        return 'low, данных пока мало'
    return 'very low, подтверждающих данных почти нет'
