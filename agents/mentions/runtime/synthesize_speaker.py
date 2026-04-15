"""Speaker event market synthesis — full structured analysis pipeline.

Triggered when the user provides a Kalshi URL or a known speaker-event ticker.
Produces a complete trade brief covering:
  - Market snapshot
  - Event context (venue, format, guests, timing, topics, Q&A)
  - Speaker profile (tendency, historical evidence)
  - Trade parameters (win condition, difficulty, invalidation, scaling, sizing)
  - Reasoning chain
  - Conclusion + confidence
"""
from __future__ import annotations

import logging

from agents.mentions.utils import timed

log = logging.getLogger('mentions')


@timed('synthesize_speaker')
def synthesize_speaker_market(ticker: str,
                               market_data: dict,
                               transcripts: list[dict],
                               news: list[dict],
                               url_info: dict | None = None) -> dict:
    """Run the full speaker-event analysis pipeline.

    Parameters
    ----------
    ticker:
        Kalshi market ticker (uppercase).
    market_data:
        Raw dict from ``kalshi.get_market()``.
    transcripts:
        Transcript chunks from FTS search (may be empty).
    news:
        News items from fetch layer (may be empty).
    url_info:
        Optional parsed URL dict from ``url_parser.parse_kalshi_url()``.

    Returns
    -------
    Structured dict with all analysis fields.
    """
    from agents.mentions.analysis.speaker_extract import (
        extract_speaker, analyse_speaker_tendency,
    )
    from agents.mentions.analysis.event_context import analyze_event_context
    from agents.mentions.analysis.trade_params import compute_trade_params
    from agents.mentions.analysis.signal import assess_signal
    from agents.mentions.analysis.reasoning import build_reasoning_chain

    url_info = url_info or {}

    # ── 1. Speaker extraction ──────────────────────────────────────────────
    speaker_info = extract_speaker(market_data, url_info=url_info)
    speaker_name = speaker_info.get('speaker_name', 'Unknown Speaker')
    speaker_slug = speaker_info.get('speaker_slug', '')

    # ── 2. Transcript evidence + tendency ─────────────────────────────────
    # Force transcript search if we know the speaker name
    if not transcripts and speaker_name and speaker_name != 'Unknown Speaker':
        transcripts = _fetch_speaker_transcripts(speaker_name, speaker_slug)

    tendency = analyse_speaker_tendency(speaker_name, speaker_slug, transcripts)

    transcript_evidence = _best_transcript_excerpt(transcripts, speaker_name)

    # ── 3. Event context ──────────────────────────────────────────────────
    event_ctx = analyze_event_context(market_data, news, {
        'speaker_name': speaker_name,
        'speaker_org':  speaker_info.get('speaker_org', ''),
    })

    # ── 4. Signal assessment (reuse existing module) ──────────────────────
    frame = {
        'route':    'speaker-event',
        'category': speaker_info.get('domain', 'general'),
        'mode':     'deep',
    }
    market_retrieval = {
        'market_data': market_data,
        'history':     [],
        'ticker':      ticker,
    }
    signal = assess_signal(market_retrieval, frame)

    # ── 5. Confidence ─────────────────────────────────────────────────────
    confidence = _compute_confidence(
        has_market=bool(market_data),
        has_transcripts=bool(transcripts),
        has_news=bool(news),
        tendency=tendency.get('tendency', 'unknown'),
    )

    # ── 6. Trade parameters ───────────────────────────────────────────────
    trade = compute_trade_params(
        market_data=market_data,
        speaker_tendency={**tendency, 'speaker_name': speaker_name},
        confidence=confidence,
        event_context=event_ctx,
    )

    # ── 7. Reasoning chain ────────────────────────────────────────────────
    reasoning = _build_speaker_reasoning(
        ticker=ticker,
        market_data=market_data,
        speaker_info=speaker_info,
        tendency=tendency,
        event_ctx=event_ctx,
        trade=trade,
        signal=signal,
    )

    # ── 8. Conclusion ─────────────────────────────────────────────────────
    conclusion = _build_conclusion(
        market_data=market_data,
        tendency=tendency,
        trade=trade,
        confidence=confidence,
    )

    # ── 9. News summary ───────────────────────────────────────────────────
    news_context = _summarize_news(news)

    return {
        # Market snapshot
        'ticker':    ticker,
        'market': {
            'title':      market_data.get('title', ticker),
            'ticker':     ticker,
            'yes_price':  market_data.get('yes_bid', market_data.get('yes_price')),
            'no_price':   market_data.get('no_bid',  market_data.get('no_price')),
            'volume':     market_data.get('volume'),
            'close_time': market_data.get('close_time', market_data.get('expiration_time', '')),
            'rules':      market_data.get('rules_primary', market_data.get('rules', '')),
            'status':     market_data.get('status', ''),
        },
        # Speaker
        'speaker': {
            'name':              speaker_name,
            'slug':              speaker_slug,
            'org':               speaker_info.get('speaker_org', ''),
            'domain':            speaker_info.get('domain', ''),
            'event_type':        speaker_info.get('event_type', ''),
            'tendency':          tendency.get('tendency', 'unknown'),
            'tendency_reasoning': tendency.get('reasoning', ''),
            'evidence_count':    tendency.get('evidence_count', 0),
        },
        # Event context
        'event_context': event_ctx,
        # Evidence
        'transcript_evidence': transcript_evidence,
        'news_context':        news_context,
        # Trade parameters
        'trade_params': trade,
        # Analysis
        'signal_assessment':  signal,
        'reasoning_chain':    reasoning,
        'conclusion':         conclusion,
        'confidence':         confidence,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_speaker_transcripts(speaker_name: str, speaker_slug: str,
                                limit: int = 10) -> list[dict]:
    try:
        from agents.mentions.kb.query import query_transcripts
        from agents.mentions.utils import fts_query
        search = fts_query(speaker_name or speaker_slug)
        if not search:
            return []
        return query_transcripts(search, limit=limit, speaker=speaker_name)
    except Exception as exc:
        log.debug('Transcript fetch failed: %s', exc)
        return []


def _best_transcript_excerpt(chunks: list[dict], speaker_name: str,
                              max_excerpts: int = 3) -> str:
    """Return the most representative excerpts for this speaker."""
    if not chunks:
        return ''
    relevant = [c for c in chunks
                if speaker_name.lower() in (c.get('speaker') or '').lower()
                or not c.get('speaker')]
    if not relevant:
        relevant = chunks

    parts: list[str] = []
    seen: set[str] = set()
    for chunk in relevant[:max_excerpts]:
        text = (chunk.get('text') or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        # Truncate to ~180 chars at sentence boundary
        if len(text) > 180:
            cut = text[:180].rfind('. ')
            text = text[:cut + 1] if cut > 80 else text[:180] + '…'
        label = chunk.get('speaker') or speaker_name
        parts.append(f'"{text}" — {label}')

    return '\n\n'.join(parts)


def _compute_confidence(has_market: bool, has_transcripts: bool,
                         has_news: bool, tendency: str) -> str:
    score = sum([has_market, has_transcripts, has_news])
    if tendency in ('hit_all', 'evasive'):  # known tendency = extra signal
        score += 1
    if score >= 3:
        return 'high'
    if score >= 2:
        return 'medium'
    return 'low'


def _build_speaker_reasoning(ticker: str, market_data: dict,
                               speaker_info: dict, tendency: dict,
                               event_ctx: dict, trade: dict,
                               signal: dict) -> list[str]:
    steps: list[str] = []

    title = market_data.get('title', ticker)
    steps.append(f'Market: {title} — resolution requires checking market rules.')

    yes_price = market_data.get('yes_bid', market_data.get('yes_price', '?'))
    steps.append(
        f'Current YES price: {yes_price}¢ — '
        f'market difficulty assessed as {trade.get("difficulty", "medium")}.'
    )

    speaker = speaker_info.get('speaker_name', 'Speaker')
    tend = tendency.get('tendency', 'unknown')
    steps.append(
        f'Speaker: {speaker} — tendency profile: {tend}. '
        f'{tendency.get("reasoning", "")}'
    )

    fmt = event_ctx.get('format', 'event')
    qa  = event_ctx.get('qa_likelihood', 'medium')
    venue = event_ctx.get('venue', 'unknown venue')
    steps.append(
        f'Event format: {fmt} at {venue}. '
        f'Q&A likelihood: {qa}. {event_ctx.get("qa_reasoning", "")}'
    )

    topics = event_ctx.get('likely_topics', [])
    if topics:
        steps.append(f'Likely topics based on current news: {", ".join(topics[:5])}.')

    verdict = signal.get('verdict', 'unclear') if isinstance(signal, dict) else 'unclear'
    steps.append(f'Signal assessment: {verdict}.')

    steps.append(
        f'Win condition: {trade.get("win_condition", "See market rules")[:120]}…'
        if len(trade.get("win_condition", "")) > 120
        else f'Win condition: {trade.get("win_condition", "See market rules")}'
    )

    steps.append(f'Invalidation: {trade.get("invalidation", "See above.")}')

    return steps


def _build_conclusion(market_data: dict, tendency: dict,
                       trade: dict, confidence: str) -> str:
    difficulty = trade.get('difficulty', 'medium')
    tend       = tendency.get('tendency', 'unknown')
    sizing     = trade.get('sizing_note', '')

    parts = [
        f'Difficulty: {difficulty}.',
        f'Speaker tendency: {tend}.',
        f'Confidence: {confidence}.',
        sizing,
    ]
    return ' '.join(p for p in parts if p)


def _summarize_news(news: list[dict]) -> str:
    if not news:
        return ''
    headlines = [
        n.get('headline', n.get('title', ''))
        for n in news[:3]
        if n.get('headline') or n.get('title')
    ]
    return '; '.join(h for h in headlines if h)
