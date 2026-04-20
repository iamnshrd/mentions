"""Retrieval engine — fetch market data and search transcript corpus.

Combines:
1. Live market data from Kalshi (via fetch layer)
2. Cached analysis from DB
3. **Hybrid** retrieval (BM25 + optional embeddings + MMR + token budget)
   over the transcript corpus, via
   :mod:`library._core.retrieve.hybrid`.

This module is the integration layer between the runtime orchestrator
and the retrieval backends; keep policy (what to fetch, token caps,
speaker biases) here, keep mechanics (ranking, reranking) in
``library._core.retrieve``.
"""
from __future__ import annotations

import logging

from library.utils import timed, get_threshold, fts_query

log = logging.getLogger('mentions')


@timed('retrieve_market')
def retrieve_market_data(frame: dict) -> dict:
    """Retrieve market data relevant to the frame.

    Returns a dict with live market info, recent history, and cached analysis.
    Falls back gracefully when Kalshi API is unavailable.
    """
    query = frame.get('query', '')
    category = frame.get('category', 'general')

    market_data = {}
    history = []
    cached_analysis = []

    # Try to extract a ticker from the query
    ticker = _extract_ticker(query)

    if ticker:
        try:
            from library._core.fetch.kalshi import get_market, get_history
            market_data = get_market(ticker) or {}
            days = get_threshold('history_days_default', 30)
            history = get_history(ticker, days=days) or []
        except Exception as exc:
            log.warning('Kalshi fetch failed for ticker %s: %s', ticker, exc)
    else:
        try:
            from library._core.fetch.kalshi import search_markets
            results = search_markets(query, limit=5)
            if results:
                market_data = {'search_results': results}
        except Exception as exc:
            log.warning('Kalshi search failed: %s', exc)

    # Load cached analysis
    try:
        from library._core.kb.query import query_analysis_cache
        cached_analysis = query_analysis_cache(query, limit=3)
    except Exception as exc:
        log.debug('Analysis cache query failed: %s', exc)

    return {
        'ticker': ticker,
        'market_data': market_data,
        'history': history,
        'cached_analysis': cached_analysis,
    }


@timed('retrieve_transcripts')
def retrieve_transcripts(frame: dict) -> list[dict]:
    """Hybrid retrieval over the transcript corpus.

    BM25 + (optional) semantic rerank + MMR diversity + token budget.
    Returns a list of chunk dicts shaped like the v0.1 output
    (``id``/``text``/``speaker``/``section``/``event``/``event_date``)
    plus extra score fields (``score_bm25``, ``score_semantic``,
    ``score_final``) so downstream telemetry can see what happened.
    """
    if not frame.get('needs_transcript', False):
        return []

    query = frame.get('query', '')
    if not query:
        return []

    limit = get_threshold('fts_chunk_limit', 5)
    token_budget = get_threshold('transcript_token_budget', 2000)

    try:
        from library._core.retrieve.hybrid import hybrid_retrieve
        hits = hybrid_retrieve(
            query,
            limit=limit,
            token_budget=token_budget,
            speaker=frame.get('speaker', '') or '',
        )
        log.debug('hybrid_retrieve returned %d chunks (tokens=%d)',
                  len(hits), sum(h.token_count or 0 for h in hits))
        # Shape for backward compatibility with callers that expect dicts
        # with an `id` key — alias chunk_id → id.
        out = []
        for h in hits:
            d = h.as_dict()
            d['id'] = d['chunk_id']
            out.append(d)
        return out
    except Exception as exc:
        log.warning('Transcript hybrid retrieval failed: %s', exc)
        return []


@timed('retrieve_news')
def retrieve_news(frame: dict) -> list[dict]:
    """Retrieve recent news context for the market category."""
    category = frame.get('category', 'general')
    query = frame.get('query', '')

    try:
        from library._core.fetch.news import fetch_news
        return fetch_news(query, category=category,
                          limit=get_threshold('news_fetch_limit', 5))
    except Exception as exc:
        log.debug('News fetch failed: %s', exc)
        return []


def _extract_ticker(query: str) -> str:
    """Try to extract a Kalshi ticker from the query string.

    Kalshi tickers are typically uppercase alphanumeric with dashes.
    Examples: KXBTCD-25DEC, PRES-2024-DJT, INXD-24NOV1499
    """
    import re
    # Match patterns like: WORD-WORD, WORD-25DEC, PRES-2024-DJT, etc.
    pattern = r'\b([A-Z]{2,10}-[A-Z0-9]{2,10}(?:-[A-Z0-9]{2,10})*)\b'
    matches = re.findall(pattern, query.upper())
    return matches[0] if matches else ''


def build_retrieval_bundle(query: str, frame: dict) -> dict:
    """Build a complete retrieval bundle for the given query and frame.

    Returns dict with market_data, transcripts, news, and metadata.
    """
    market = retrieve_market_data(frame)
    transcripts = retrieve_transcripts(frame)
    news = retrieve_news(frame)

    has_data = bool(
        market.get('market_data') or
        market.get('history') or
        transcripts or
        news
    )

    return {
        'market': market,
        'transcripts': transcripts,
        'news': news,
        'has_data': has_data,
        'sources_used': _sources_used(market, transcripts, news),
    }


@timed('retrieve_by_ticker')
def retrieve_by_ticker(ticker: str, speaker: str = '') -> dict:
    """Directed retrieval for a known ticker + optional speaker name.

    Unlike ``retrieve_market_data()``, this always fetches market data and
    forces transcript search for the speaker when provided.

    Returns a dict compatible with ``build_retrieval_bundle()`` output.
    """
    from library._core.fetch.kalshi import get_market, get_history
    from library._core.fetch.news import fetch_news

    ticker = ticker.upper()

    # ── Market data ────────────────────────────────────────────────────────
    market_data: dict = {}
    history: list = []
    try:
        market_data = get_market(ticker) or {}
        days = get_threshold('history_days_default', 30)
        history = get_history(ticker, days=days) or []
    except Exception as exc:
        log.warning('Kalshi fetch failed for ticker %s: %s', ticker, exc)

    # ── Transcripts (forced if speaker given) ──────────────────────────────
    transcripts: list = []
    search_term = speaker or ticker
    if search_term:
        try:
            from library._core.retrieve.hybrid import hybrid_retrieve
            limit = get_threshold('fts_chunk_limit', 8)
            budget = get_threshold('transcript_token_budget', 2500)
            hits = hybrid_retrieve(
                search_term,
                limit=limit,
                token_budget=budget,
                speaker=speaker or '',
            )
            transcripts = [{**h.as_dict(), 'id': h.chunk_id} for h in hits]
        except Exception as exc:
            log.debug('Transcript fetch failed: %s', exc)

    # ── News ───────────────────────────────────────────────────────────────
    news: list = []
    try:
        query_hint = speaker or market_data.get('title', ticker)
        news = fetch_news(query_hint, limit=get_threshold('news_fetch_limit', 5))
    except Exception as exc:
        log.debug('News fetch failed: %s', exc)

    market = {
        'ticker':          ticker,
        'market_data':     market_data,
        'history':         history,
        'cached_analysis': [],
    }

    return {
        'market':      market,
        'transcripts': transcripts,
        'news':        news,
        'has_data':    bool(market_data or transcripts or news),
        'sources_used': _sources_used(market, transcripts, news),
    }


def _sources_used(market: dict, transcripts: list, news: list) -> list[str]:
    sources = []
    if market.get('market_data'):
        sources.append('kalshi-live')
    if market.get('history'):
        sources.append('kalshi-history')
    if market.get('cached_analysis'):
        sources.append('analysis-cache')
    if transcripts:
        sources.append('transcript-corpus')
    if news:
        sources.append('news-context')
    return sources
