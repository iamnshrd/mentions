"""Speaker extraction from Kalshi market data.

Given a market dict (from Kalshi API), extracts:
- Speaker name (canonical and slug)
- Event type (press_conference, speech, interview, ...)
- Organisation / domain

Also analyses speaker tendency from transcript corpus if available.
"""
from __future__ import annotations

import logging
import re

from agents.mentions.providers.kalshi import get_market_bundle

log = logging.getLogger('mentions')

# event-type keywords → label
_EVENT_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r'press conf',           'press_conference'),
    (r'press release',        'press_release'),
    (r'presser',              'press_conference'),
    (r'press briefing',       'press_conference'),
    (r'interview',            'interview'),
    (r'speech|address|remarks|delivers', 'speech'),
    (r'testimony|testif|senate|congress|house committee', 'congressional_testimony'),
    (r'panel|forum|summit|conference', 'panel'),
    (r'statement',            'statement'),
    (r'mention|will say|will refer', 'mention_market'),
    (r'q&a|questions?',       'qa_session'),
]

# Q&A likelihood by event type
_QA_BY_EVENT: dict[str, str] = {
    'press_conference':        'high',
    'interview':               'high',
    'qa_session':              'high',
    'congressional_testimony': 'high',
    'speech':                  'low',
    'press_release':           'low',
    'statement':               'low',
    'panel':                   'medium',
    'mention_market':          'medium',
    'event':                   'medium',
    'unknown':                 'medium',
}


def extract_speaker(market_data: dict,
                    url_info: dict | None = None) -> dict:
    """Extract speaker and event-type info from market data.

    Parameters
    ----------
    market_data:
        Dict returned by ``get_market_bundle(...)[\"market\"]``.
    url_info:
        Optional dict from ``services.intake.url_parser.parse_kalshi_url()``.

    Returns
    -------
    dict with keys:
        speaker_slug, speaker_name, speaker_org, domain,
        event_type, qa_likelihood
    """
    url_info = url_info or {}

    title  = market_data.get('title', '')
    ticker = market_data.get('ticker', '')
    rules  = market_data.get('rules_primary', market_data.get('rules', ''))

    combined = f'{title} {ticker} {rules}'.lower()

    # --- Speaker ---
    speaker_slug = url_info.get('speaker_slug', '')
    speaker_info = url_info.get('speaker_info', {})

    # If url_info didn't find a speaker, try from market title/rules
    if not speaker_slug:
        speaker_slug, speaker_info = _find_speaker_in_text(combined)

    speaker_name = speaker_info.get('name', _slugify_name(speaker_slug))
    speaker_org  = speaker_info.get('org', '')
    domain       = speaker_info.get('domain', 'general')

    # --- Event type ---
    event_type = url_info.get('event_type', '')
    if not event_type or event_type == 'unknown':
        event_type = _infer_event_type(combined)

    qa_likelihood = _QA_BY_EVENT.get(event_type, 'medium')

    return {
        'speaker_slug':   speaker_slug,
        'speaker_name':   speaker_name,
        'speaker_org':    speaker_org,
        'domain':         domain,
        'event_type':     event_type,
        'qa_likelihood':  qa_likelihood,
    }


def _infer_event_type(text: str) -> str:
    for pattern, etype in _EVENT_TYPE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return etype
    return 'event'


def _find_speaker_in_text(text: str) -> tuple[str, dict]:
    """Try to identify a known speaker from free text."""
    from agents.mentions.services.intake.url_parser import _SPEAKER_MAP
    for slug in sorted(_SPEAKER_MAP.keys(), key=len, reverse=True):
        if slug in text:
            return slug, _SPEAKER_MAP[slug]
    return '', {}


def extract_speaker_from_ticker(ticker: str, url_info: dict | None = None) -> dict:
    """Compatibility helper for callers that only have a market ticker."""
    bundle = get_market_bundle(ticker)
    return extract_speaker(bundle.get('market', {}), url_info=url_info)


def _slugify_name(slug: str) -> str:
    """Best-effort capitalisation of a slug: 'infantino' → 'Infantino'."""
    return slug.replace('-', ' ').replace('_', ' ').title() if slug else 'Unknown Speaker'


def analyse_speaker_tendency(speaker_name: str, speaker_slug: str,
                              transcript_chunks: list[dict]) -> dict:
    """Determine speaker tendency from transcript corpus.

    Returns::

        {
            'tendency': str,       # hit_all / selective / evasive / mixed / unknown
            'reasoning': str,
            'evidence_count': int,
        }
    """
    if not transcript_chunks:
        # Fallback: query DB directly
        transcript_chunks = _fetch_speaker_chunks(speaker_name, speaker_slug)

    if not transcript_chunks:
        return {
            'tendency': 'unknown',
            'reasoning': 'No transcript data available for this speaker.',
            'evidence_count': 0,
        }

    texts = [c.get('text', '') for c in transcript_chunks if c.get('text')]
    combined = ' '.join(texts).lower()

    # Evasive signals
    evasive_hits = sum(bool(re.search(p, combined)) for p in [
        r"won'?t comment", r"not going to (comment|discuss|address)",
        r"that'?s not (on|part of) (the )?(agenda|topic)",
        r"no comment", r"decline to",
        r"(not|don'?t) (want to|wish to) (get into|discuss|speculate)",
        r"off[- ]topic", r"not (appropriate|the right time)",
    ])

    # Hit-all / comprehensive signals
    hit_all_hits = sum(bool(re.search(p, combined)) for p in [
        r"happy to (answer|address|discuss|take)",
        r"great question", r"let me address",
        r"on that (point|question|topic)",
        r"as (i|we) mentioned", r"i (want|wanted) to (add|emphasize|note)",
        r"to (directly|specifically) answer",
        r"yes[,.]? (i|we) (can|will|would)",
    ])

    # Selective / cautious signals
    selective_hits = sum(bool(re.search(p, combined)) for p in [
        r"data[- ]dependent", r"monitor(ing)?", r"wait and see",
        r"premature to", r"too (early|soon) to",
        r"(carefully|closely) watching",
    ])

    total = evasive_hits + hit_all_hits + selective_hits or 1  # avoid /0

    if evasive_hits / total >= 0.5:
        tendency  = 'evasive'
        reasoning = (f'{speaker_name} shows a pattern of avoiding direct answers '
                     f'or deflecting specific topics ({evasive_hits} evasive signals).')
    elif hit_all_hits / total >= 0.5:
        tendency  = 'hit_all'
        reasoning = (f'{speaker_name} typically addresses questions broadly and directly '
                     f'({hit_all_hits} comprehensive-response signals).')
    elif selective_hits / total >= 0.4:
        tendency  = 'selective'
        reasoning = (f'{speaker_name} tends toward cautious, data-dependent responses '
                     f'({selective_hits} selective signals).')
    else:
        tendency  = 'mixed'
        reasoning = (f'No dominant pattern detected for {speaker_name}. '
                     f'Evasive: {evasive_hits}, hit-all: {hit_all_hits}, '
                     f'selective: {selective_hits}.')

    return {
        'tendency':       tendency,
        'reasoning':      reasoning,
        'evidence_count': len(transcript_chunks),
    }


def _fetch_speaker_chunks(speaker_name: str, speaker_slug: str,
                          limit: int = 15) -> list[dict]:
    """Query the transcript DB for this speaker."""
    try:
        from agents.mentions.services.knowledge import query_transcripts
        from agents.mentions.utils import fts_query
        search = fts_query(speaker_name or speaker_slug)
        if not search:
            return []
        return query_transcripts(search, limit=limit, speaker=speaker_name)
    except Exception as exc:
        log.debug('Speaker chunk fetch failed: %s', exc)
        return []
