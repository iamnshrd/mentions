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
    (r'fox news sunday|meet the press|face the nation|state of the union|this week', 'interview'),
    (r'interview',                     'interview'),
    (r'speech|address|remarks|delivers','speech'),
    (r'testif|testimony|senate hearing|house hearing', 'congressional_testimony'),
    (r'turning point|tpusa|conference', 'conference'),
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
    'conference':             ('medium', 'Conference appearances often have a prepared core plus possible side-branch expansion.'),
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
    likely_topics  = _extract_topics(title, rules, news_items, market_data)
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
        'title':          title,
        'event_title':    market_data.get('event_title', title),
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
        dt_str = close_time.replace('Z', '+00:00')
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        human = dt.astimezone(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')
        return human, dt.astimezone(timezone.utc).isoformat()
    except Exception as exc:
        log.debug('Failed to parse event date from %r: %s', close_time, exc)
        return close_time, close_time


def _clean_topic_candidate(value: str) -> str:
    t = (value or '').strip().strip('`').strip('"').strip("'")
    t = re.sub(r'\s+', ' ', t).strip()
    if not t or len(t) <= 2:
        return ''
    lowered = t.lower()
    if lowered.startswith('what will '):
        return ''
    blocked_exact = {
        'donald trump', 'trump', 'yes', 'no', 'you', 'vegas', 'las vegas',
        'the nevada independent', 'pbs', 'coinbase', 'ksnv', 'news3lv.com',
    }
    if lowered in blocked_exact:
        return ''
    if re.fullmatch(r'[A-Z][a-z]{2,}', t) and lowered in {'you', 'watch'}:
        return ''
    return t


def _headline_topic_phrases(headline: str) -> list[str]:
    phrases = []
    patterns = [
        r'\bno tax on tips\b',
        r'\btax day\b',
        r'\blas vegas\b',
        r'\broundtable\b',
    ]
    lowered = (headline or '').lower()
    for pattern in patterns:
        m = re.search(pattern, lowered)
        if m:
            phrases.append(m.group(0).title() if m.group(0) != 'no tax on tips' else 'No Tax on Tips')
    return phrases


def _finalize_topics(topics: list[str]) -> list[str]:
    finalized = []
    seen = set()
    for topic in topics:
        cleaned = _clean_topic_candidate(topic)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        if key in {'tax', 'tips'} and 'no tax on tips' in {t.lower() for t in topics}:
            continue
        seen.add(key)
        finalized.append(cleaned)
    return finalized


def _extract_topics(title: str, rules: str, news_items: list[dict], market_data: dict | None = None) -> list[str]:
    """Extract likely discussion topics from title, rules, and news."""
    market_data = market_data or {}
    topics: list[str] = []
    seen: set[str] = set()

    strike_labels = {
        ((market_data.get('yes_sub_title') or market_data.get('strike_title') or '').strip().lower())
    }

    def add_topic(value: str, *, low_priority: bool = False):
        t = _clean_topic_candidate(value)
        if not t:
            return
        if t.lower() in strike_labels and not low_priority:
            return
        key = t.lower()
        if key in seen:
            return
        if low_priority:
            topics.append(f'__LOW__::{t}')
        else:
            topics.append(t)
        seen.add(key)

    lower_title = (title or '').lower()
    lower_rules = (rules or '').lower()
    combined = f'{title} {rules}'
    is_media_case = any(token in lower_title for token in [
        'fox news', 'fox news sunday', 'meet the press', 'face the nation', 'this week',
        'state of the union', 'hannity', 'ingraham', 'watters', 'bret baier', 'interview'
    ])

    roundtable_match = re.search(r'roundtable on ([^?.,\n]{4,80})', combined, re.IGNORECASE)
    if roundtable_match:
        add_topic(roundtable_match.group(1))
    on_match = re.search(r'\bat ([A-Z][^?]+?)\b', title)
    if on_match and 'What will' not in on_match.group(1):
        add_topic(on_match.group(1))
    if 'no tax on tips' in lower_title or 'no tax on tips' in lower_rules:
        add_topic('No Tax on Tips')

    explicit_patterns = [
        r'if\s+.+?\s+says\s+([^.,\n]{3,60})\s+as part of',
        r'mention(?:s|ed)?\s+([a-z][a-z\s]{4,40})',
        r'(?:discuss|address|comment on)\s+([a-z][a-z\s]{4,40})',
        r'(?:topic|subject)[:\s]+([a-z][a-z\s]{4,40})',
    ]
    for pattern in explicit_patterns:
        for m in re.finditer(pattern, lower_rules, re.IGNORECASE):
            add_topic(m.group(1))

    for item in news_items[:5]:
        headline = item.get('headline', item.get('title', ''))
        if not headline:
            continue
        normalized_headline = re.sub(r'\s+-\s+[^-]+$', '', headline).strip()
        for phrase in _headline_topic_phrases(normalized_headline):
            add_topic(phrase)

    cleaned: list[str] = []
    strike_label = (market_data.get('yes_sub_title') or market_data.get('strike_title') or '').strip()
    if strike_label and not topics and not is_media_case:
        add_topic(strike_label, low_priority=True)

    deferred: list[str] = []
    for topic in topics:
        if topic.startswith('__LOW__::'):
            deferred.append(topic.replace('__LOW__::', '', 1))
        else:
            cleaned.append(topic)
    cleaned.extend(deferred)
    return _finalize_topics(cleaned)[:8]
