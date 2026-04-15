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
    chain.append(f'Query classified as: {route} (category: {category})')

    # Step 2: Market data observation
    if market_summary and 'No live data' not in market_summary:
        # Extract the key fact line
        first_line = market_summary.split('\n')[0]
        chain.append(f'Market data: {first_line}')
    else:
        chain.append('Market data: unavailable — analysis based on historical/cached data only')

    # Step 3: Signal assessment
    if isinstance(signal, dict) and signal.get('verdict') != 'unclear':
        verdict = signal.get('verdict', '?')
        strength = signal.get('signal_strength', '?')
        factors = signal.get('factors', [])
        chain.append(f'Signal verdict: {verdict} (strength: {strength})')
        for f in factors[:2]:
            chain.append(f'  Factor: {f}')
    else:
        chain.append('Signal verdict: unclear — insufficient data for classification')

    # Step 4: News context
    if news:
        headlines = [n.get('headline', '') for n in news[:2] if n.get('headline')]
        if headlines:
            chain.append(f'News context: {headlines[0]}')

    # Step 5: Transcript/speaker evidence
    if transcript_context:
        first_line = transcript_context.split('\n')[0][:120]
        chain.append(f'Historical speaker evidence: {first_line}')
    else:
        if route in ('speaker-history', 'context-research', 'macro'):
            chain.append('No relevant transcript evidence found for this query')

    # Step 6: Route-specific reasoning
    route_inference = _route_inference(route, signal, transcript_context)
    if route_inference:
        chain.append(route_inference)

    # Step 7: Uncertainty label
    confidence = _estimate_confidence(market_summary, signal, transcript_context, news)
    chain.append(f'Confidence assessment: {confidence}')

    return chain


def _route_inference(route: str, signal: dict, transcript_context: str) -> str:
    """Generate a route-specific inference step."""
    verdict = signal.get('verdict', 'unclear') if isinstance(signal, dict) else 'unclear'
    strength = signal.get('signal_strength', 'unknown') if isinstance(signal, dict) else 'unknown'

    if route == 'price-movement':
        if verdict == 'signal':
            return f'Price move confirmed as {strength} signal — likely driven by external catalyst'
        return 'Price move pattern: inconclusive without catalyst identification'

    if route == 'macro':
        if transcript_context:
            return 'Macro context: transcript corpus provides relevant speaker positioning'
        return 'Macro context: no transcript data — rely on market pricing as implicit probability'

    if route == 'speaker-history':
        if transcript_context:
            return 'Speaker history found — cross-reference with current market pricing'
        return 'No speaker transcript data available — position unknown'

    if route == 'signal-or-noise':
        if verdict in ('signal', 'noise'):
            return f'Signal/noise classification: {verdict} (score-based verdict)'
        return 'Signal/noise: borderline — consider waiting for more data'

    if route == 'breaking-news':
        return 'Breaking news route: prioritize recency; market may not have fully priced in yet'

    if route == 'trend-analysis':
        return 'Trend analysis: requires multi-point history; single snapshots are insufficient'

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
        return 'high — multiple corroborating sources'
    if score >= 2:
        return 'medium — partial data available'
    if score >= 1:
        return 'low — limited data'
    return 'very low — no supporting data'
