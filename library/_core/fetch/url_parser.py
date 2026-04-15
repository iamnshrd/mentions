"""Kalshi URL parser — extract ticker and speaker info from market URLs.

Supported URL formats:
  https://www.kalshi.com/markets/{series}/{ticker}
  https://kalshi.com/markets/{series}/{ticker}
  https://trading.kalshi.com/markets/{series}/{ticker}
"""
from __future__ import annotations

import re


# Known series-slug → speaker name/context mappings
_SPEAKER_MAP: dict[str, dict] = {
    # FIFA / Sports
    'infantino':      {'name': 'Gianni Infantino',  'org': 'FIFA',            'domain': 'sports'},
    # US Federal Reserve
    'powell':         {'name': 'Jerome Powell',     'org': 'Federal Reserve', 'domain': 'macro'},
    'waller':         {'name': 'Christopher Waller','org': 'Federal Reserve', 'domain': 'macro'},
    'jefferson':      {'name': 'Philip Jefferson',  'org': 'Federal Reserve', 'domain': 'macro'},
    'kugler':         {'name': 'Adriana Kugler',    'org': 'Federal Reserve', 'domain': 'macro'},
    'cook':           {'name': 'Lisa Cook',         'org': 'Federal Reserve', 'domain': 'macro'},
    'daly':           {'name': 'Mary Daly',         'org': 'Federal Reserve', 'domain': 'macro'},
    'bostic':         {'name': 'Raphael Bostic',    'org': 'Federal Reserve', 'domain': 'macro'},
    'logan':          {'name': 'Lorie Logan',       'org': 'Federal Reserve', 'domain': 'macro'},
    'barkin':         {'name': 'Tom Barkin',        'org': 'Federal Reserve', 'domain': 'macro'},
    'goolsbee':       {'name': 'Austan Goolsbee',   'org': 'Federal Reserve', 'domain': 'macro'},
    'kashkari':       {'name': 'Neel Kashkari',     'org': 'Federal Reserve', 'domain': 'macro'},
    'musalem':        {'name': 'Alberto Musalem',   'org': 'Federal Reserve', 'domain': 'macro'},
    'schmid':         {'name': 'Jeff Schmid',       'org': 'Federal Reserve', 'domain': 'macro'},
    # White House / Politics
    'trump':          {'name': 'Donald Trump',      'org': 'White House',     'domain': 'politics'},
    'biden':          {'name': 'Joe Biden',         'org': 'White House',     'domain': 'politics'},
    'harris':         {'name': 'Kamala Harris',     'org': 'US Government',   'domain': 'politics'},
    'leavitt':        {'name': 'Karoline Leavitt',  'org': 'White House',     'domain': 'politics'},
    # Other institutions
    'lagarde':        {'name': 'Christine Lagarde', 'org': 'ECB',             'domain': 'macro'},
    'yellen':         {'name': 'Janet Yellen',      'org': 'US Treasury',     'domain': 'macro'},
    'musk':           {'name': 'Elon Musk',         'org': 'DOGE / Tesla',    'domain': 'tech'},
    'zelensky':       {'name': 'Volodymyr Zelensky','org': 'Ukraine',         'domain': 'geopolitics'},
    'putin':          {'name': 'Vladimir Putin',    'org': 'Russia',          'domain': 'geopolitics'},
}

# Prefixes to strip when extracting speaker slug from series slug
_STRIP_PREFIXES = ('kx', 'kxnew', 'kalshi')

# Event-type keywords inside series slugs
_EVENT_TYPE_HINTS: dict[str, str] = {
    'mention':     'mention_market',     # "will X mention Y"
    'say':         'mention_market',
    'speech':      'speech',
    'pressconf':   'press_conference',
    'presser':     'press_conference',
    'conference':  'press_conference',
    'interview':   'interview',
    'panel':       'panel',
    'statement':   'statement',
    'testimony':   'congressional_testimony',
    'congress':    'congressional_testimony',
    'senate':      'congressional_testimony',
}


def parse_kalshi_url(url: str) -> dict:
    """Extract ticker, series, and speaker info from a Kalshi market URL.

    Returns::

        {
            'ticker': str,         # e.g. 'KXINFANTINOMENTION-26APR15'
            'series_slug': str,    # e.g. 'kxinfantinomention'
            'speaker_slug': str,   # e.g. 'infantino'
            'speaker_info': dict,  # from _SPEAKER_MAP or {}
            'event_type': str,     # mention_market / press_conference / speech / …
            'raw_url': str,
            'is_kalshi_url': bool,
        }
    """
    url = (url or '').strip()
    result: dict = {
        'ticker': '',
        'series_slug': '',
        'speaker_slug': '',
        'speaker_info': {},
        'event_type': 'unknown',
        'raw_url': url,
        'is_kalshi_url': False,
    }

    if not url:
        return result

    # Check it's a Kalshi URL at all
    if 'kalshi.com' not in url.lower():
        # Maybe it's just a ticker passed directly
        if re.match(r'^[A-Z]{2,20}[-][A-Z0-9]{2,20}', url.upper()):
            result['ticker'] = url.upper()
            result['is_kalshi_url'] = False
            result['event_type'] = _infer_event_type(url.lower())
            result['speaker_slug'], result['speaker_info'] = _extract_speaker(url.lower())
        return result

    result['is_kalshi_url'] = True

    # Extract /markets/{series}/{ticker}
    m = re.search(r'/markets/([^/?#]+)/([^/?#]+)', url, re.IGNORECASE)
    if m:
        series_slug = m.group(1).lower()
        ticker_raw  = m.group(2)
        result['series_slug'] = series_slug
        result['ticker']      = ticker_raw.upper()
    else:
        # Try to pull any ticker-looking token from the URL
        m2 = re.search(r'([A-Z]{2,20}-[A-Z0-9]{2,20}(?:-[A-Z0-9]{2,10})*)', url.upper())
        if m2:
            result['ticker'] = m2.group(1)
        return result

    slug = result['series_slug']
    result['event_type'] = _infer_event_type(slug)
    result['speaker_slug'], result['speaker_info'] = _extract_speaker(slug)

    return result


def _strip_prefix(slug: str) -> str:
    """Remove known prefixes from a series slug."""
    for pfx in sorted(_STRIP_PREFIXES, key=len, reverse=True):
        if slug.startswith(pfx):
            return slug[len(pfx):]
    return slug


def _extract_speaker(slug: str) -> tuple[str, dict]:
    """Return (speaker_slug, speaker_info) by matching _SPEAKER_MAP against *slug*."""
    core = _strip_prefix(slug)
    # Try longest-match first
    for name in sorted(_SPEAKER_MAP.keys(), key=len, reverse=True):
        if name in core:
            return name, _SPEAKER_MAP[name]
    # Fallback: first word of core slug (up to first digit or event keyword)
    first_word = re.split(r'[0-9]|mention|say|speech|press|interview|panel', core)[0]
    first_word = first_word.strip('-_')
    return first_word, {}


def _infer_event_type(slug: str) -> str:
    """Infer event type from series slug keywords."""
    for kw, etype in _EVENT_TYPE_HINTS.items():
        if kw in slug:
            return etype
    return 'event'
