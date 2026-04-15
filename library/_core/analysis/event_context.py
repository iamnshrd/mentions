"""Event context analysis for speaker event markets.

Given market data + news, determines:
  - Event venue and format
  - Expected guests / participants
  - Event date and timing
  - Likely discussion topics (from news)
  - Q&A session likelihood

All inference is rule-based; no LLM calls.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

log = logging.getLogger('mentions')

# Venue hints: keyword → canonical venue name
_VENUE_HINTS: list[tuple[str, str]] = [
    (r'federal reserve|fomc|fed',              'Federal Reserve, Washington D.C.'),
    (r'white house|briefing room',             'White House, Washington D.C.'),
    (r'pentagon',                              'Pentagon, Arlington VA'),
    (r'congress|capitol hill|senate|house',   'U.S. Capitol, Washington D.C.'),
    (r'fifa|zürich|zurich',                   'FIFA Headquarters, Zurich'),
    (r'davos|wef',                            'World Economic Forum, Davos'),
    (r'imf|international monetary fund',      'IMF Headquarters, Washington D.C.'),
    (r'world bank',                           'World Bank, Washington D.C.'),
    (r'ecb|european central bank|frankfurt',  'ECB Headquarters, Frankfurt'),
    (r'bank of england|boe|london',           'Bank of England, London'),
    (r'un |united nations|new york',          'United Nations, New York'),
    (r'nato|brussels',                        'NATO Headquarters, Brussels'),
    (r'g7|g20',                               'G7/G20 Summit venue'),
]

# Format inference: patterns in title/rules → format label
_FORMAT_PATTERNS: list[tuple[str, str]] = [
    (r'press conf|presser|briefing',   'press_conference'),
    (r'interview',                     'interview'),
    (r'speech|address|remarks|delivers','speech'),
    (r'testif|testimony|senate hearing|house hearing', 'congressional_testimony'),
    (r'panel|forum|summit|roundtable', 'panel'),
    (r'statement|announces',           'statement'),
    (r'mention|will say|will refer',   'mention_market'),
    (r'q&a',                           'qa_session'),
]

# Q&A likelihood by format
_QA_LIKELIHOOD: dict[str, tuple[str, str]] = {
    'press_conference':       ('high',   'Press conferences always include Q&A from reporters.'),
    'congressional_testimony':('high',   'Congressional testimonies include member questions.'),
    'interview':              ('high',   'Interviews are inherently Q&A format.'),
    'qa_session':             ('high',   'This is explicitly a Q&A format.'),
    'panel':                  ('medium', 'Panels often include audience questions.'),
    'mention_market':         ('medium', 'Format unclear; Q&A depends on specific event structure.'),
    'event':                  ('medium', 'Format unclear; Q&A unknown.'),
    'speech':                 ('low',    'Formal speeches are typically one-way; limited Q&A.'),
    'statement':              ('low',    'Statements are read; questions usually not taken.'),
    'press_release':          ('low',    'Press releases do not include Q&A.'),
    'unknown':                ('medium', 'Event format unknown.'),
}


def analyze_event_context(market_data: dict,
                           news_items: list[dict],
                           speaker_info: dict) -> dict:
    """Build a full event context dict from market data and news.

    Returns::

        {
            'venue': str,
            'format': str,
            'guests': list[str],
            'event_date': str,         # ISO or human-readable
            'event_date_iso': str,
            'likely_topics': list[str],
            'qa_likelihood': str,      # high / medium / low
            'qa_reasoning': str,
        }
    """
    title  = market_data.get('title', '')
    rules  = market_data.get('rules_primary', market_data.get('rules', ''))
    close  = market_data.get('close_time', market_data.get('expiration_time', ''))

    combined = f'{title} {rules}'.lower()

    venue          = _infer_venue(combined, speaker_info)
    fmt            = _infer_format(combined)
    guests         = _extract_guests(combined, speaker_info.get('speaker_name', ''))
    event_date, event_date_iso = _parse_event_date(close)
    likely_topics  = _extract_topics(title, rules, news_items)
    qa_lvl, qa_why = _QA_LIKELIHOOD.get(fmt, ('medium', 'Format unclear.'))

    return {
        'venue':          venue,
        'format':         fmt,
        'guests':         guests,
        'event_date':     event_date,
        'event_date_iso': event_date_iso,
        'likely_topics':  likely_topics,
        'qa_likelihood':  qa_lvl,
        'qa_reasoning':   qa_why,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_venue(text: str, speaker_info: dict) -> str:
    for pattern, venue in _VENUE_HINTS:
        if re.search(pattern, text, re.IGNORECASE):
            return venue
    # Fallback: derive from org
    org = speaker_info.get('speaker_org', '')
    if org:
        return f'{org} (exact venue TBD)'
    return 'Venue not identified from available data'


def _infer_format(text: str) -> str:
    for pattern, fmt in _FORMAT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return fmt
    return 'event'


def _extract_guests(text: str, main_speaker: str) -> list[str]:
    """Extract likely other participants mentioned in the text."""
    guests: list[str] = []

    # Generic guest patterns
    patterns = [
        r'joined by ([A-Z][a-z]+ [A-Z][a-z]+)',
        r'alongside ([A-Z][a-z]+ [A-Z][a-z]+)',
        r'moderator[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)',
        r'host(?:ed)? by ([A-Z][a-z]+ [A-Z][a-z]+)',
    ]
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            g = m.group(1).strip()
            if g.lower() not in main_speaker.lower():
                guests.append(g)

    # For press conferences: mention "press corps" / "reporters"
    if re.search(r'press conf|presser|briefing', text, re.IGNORECASE):
        guests.append('Press corps / reporters')

    # For congressional testimonies: mention members of committee
    if re.search(r'testif|senate|congress|house committee', text, re.IGNORECASE):
        guests.append('Committee members (senators/representatives)')

    return list(dict.fromkeys(guests))[:5]  # deduplicate, max 5


def _parse_event_date(close_time: str) -> tuple[str, str]:
    """Parse close_time into (human-readable, ISO) strings."""
    if not close_time:
        return 'Date not available', ''
    try:
        # Try ISO parse
        dt_str = close_time.replace('Z', '+00:00')
        dt = datetime.fromisoformat(dt_str)
        human = dt.strftime('%B %d, %Y at %H:%M UTC')
        return human, dt.isoformat()
    except Exception:
        return close_time, close_time


def _extract_topics(title: str, rules: str, news_items: list[dict]) -> list[str]:
    """Extract likely discussion topics from title, rules, and news."""
    topics: set[str] = set()

    # From rules (look for quoted topics or explicit mentions)
    rule_text = f'{title} {rules}'.lower()
    topic_patterns = [
        r'"([^"]{5,60})"',          # quoted strings
        r'mention(?:s|ed)?\s+([a-z][a-z\s]{4,40})',
        r'(?:discuss|address|comment on)\s+([a-z][a-z\s]{4,40})',
        r'(?:topic|subject)[:\s]+([a-z][a-z\s]{4,40})',
    ]
    for p in topic_patterns:
        for m in re.finditer(p, rule_text):
            t = m.group(1).strip().rstrip('.,')
            if 4 < len(t) < 60:
                topics.add(t)

    # From news headlines
    for item in news_items[:5]:
        headline = item.get('headline', item.get('title', ''))
        if headline:
            # Extract noun phrases heuristically (capitalised sequences)
            for m in re.finditer(r'[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*', headline):
                phrase = m.group(0)
                if len(phrase) > 4:
                    topics.add(phrase)

    # Limit and convert to list
    return sorted(topics)[:8]
