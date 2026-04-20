from __future__ import annotations

from agents.mentions.contracts import MarketCandidate, MarketQuery, ResolvedMarket
from .extraction import extract_market_entities

SPEAKER_HINTS = [
    'trump', 'powell', 'biden', 'lagarde', 'musk', 'fed', 'federal reserve',
    'donald trump', 'jerome powell',
]

MENTION_HINTS = [
    'mention', 'say', 'address', 'speech', 'press conference', 'interview',
    'briefing', 'statement', 'forum', 'conference',
]


def _score_market(query: str, market: dict) -> tuple[float, str]:
    q = (query or '').lower()
    title = (market.get('title') or '').lower()
    ticker = (market.get('ticker') or '').lower()
    yes_sub = (market.get('yes_sub_title') or '').lower()
    subtitle = (market.get('subtitle') or '').lower()
    event_ticker = (market.get('event_ticker') or '').lower()

    score = 0.0
    reasons: list[str] = []

    entities = extract_market_entities(query)

    for hint in SPEAKER_HINTS:
        if hint in q and hint in title:
            score += 4.0
            reasons.append(f'speaker-match:{hint}')

    for canonical in entities.get('speakers', []):
        lowered_name = canonical.lower()
        parts = lowered_name.split()
        if any(part in title or part in ticker or part in event_ticker for part in parts):
            score += 3.0
            reasons.append(f'canonical-speaker-match:{canonical}')

    for topic in entities.get('topics', []):
        if topic in title or topic in yes_sub or topic in subtitle or topic in ticker:
            score += 2.0
            reasons.append(f'topic-match:{topic}')
        if _matches_exact_topic_label(topic, yes_sub, subtitle):
            score += 4.0
            reasons.append(f'exact-topic-label:{topic}')

    if entities.get('is_mention_style') and ('mention' in title or 'what will' in title or 'say during' in title):
        score += 2.5
        reasons.append('mention-style-query-match')

    for hint in MENTION_HINTS:
        if hint in q and hint in title:
            score += 2.5
            reasons.append(f'mention-structure:{hint}')

    query_words = [w for w in q.replace('?', ' ').replace(',', ' ').split() if len(w) > 2]
    overlap = 0
    for word in query_words:
        if word in title or word in ticker:
            overlap += 1
    if overlap:
        score += min(3.0, overlap * 0.6)
        reasons.append(f'word-overlap:{overlap}')

    if 'mention' in title or 'what will' in title or 'say during' in title:
        score += 1.5
        reasons.append('title-contains-mention-family')

    if event_ticker and _looks_like_same_family(query, event_ticker):
        score += 2.0
        reasons.append('event-family-match')

    score += _date_signal_bonus(query, market, reasons)

    if any(bad in title for bad in ['1+1', 'screened by the tsa', 'toronto', 'points scored']):
        score -= 6.0
        reasons.append('irrelevant-pattern-penalty')

    volume = market.get('volume', 0) or 0
    if isinstance(volume, (int, float)) and volume > 0:
        score += min(1.5, float(volume) / 100000.0)
        reasons.append('volume-bias')

    return score, ','.join(reasons)


def resolve_market_candidates(query: str, markets: list[dict], limit: int = 5) -> list[MarketCandidate]:
    ranked: list[MarketCandidate] = []
    for market in markets or []:
        score, rationale = _score_market(query, market)
        ranked.append(MarketCandidate(
            ticker=market.get('ticker', ''),
            title=market.get('title', ''),
            score=score,
            rationale=rationale,
            meta={'raw_market': market},
        ))
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:limit]


def _matches_exact_topic_label(topic: str, yes_sub: str, subtitle: str) -> bool:
    aliases = {
        'iran': ['iran', 'iranian'],
        'israel': ['israel', 'israeli'],
        'ukraine': ['ukraine', 'ukrainian'],
        'china': ['china', 'chinese'],
    }.get(topic, [topic])
    normalized = [part.strip().lower() for part in [yes_sub, subtitle] if part.strip()]
    return any(label == alias for label in normalized for alias in aliases)


def _looks_like_same_family(query: str, event_ticker: str) -> bool:
    q = (query or '').lower()
    e = (event_ticker or '').lower()
    if 'trump' in q and 'trumpmention' in e:
        return True
    if 'biden' in q and 'bidenmention' in e:
        return True
    if 'powell' in q and ('powell' in e or 'fed' in e):
        return True
    return False


def _date_signal_bonus(query: str, market: dict, reasons: list[str]) -> float:
    q = (query or '').lower()
    ticker = (market.get('ticker') or '').lower()
    bonus = 0.0
    if 'this week' in q and 'week' in (market.get('subtitle') or '').lower():
        bonus += 1.0
        reasons.append('date-fit:this-week-subtitle')
    if 'april 15' in q and '26apr15' in ticker:
        bonus += 1.5
        reasons.append('date-fit:apr15')
    return bonus


def resolve_market_from_query(query: str, search_results: list[dict]) -> ResolvedMarket:
    market_query = MarketQuery(text=query)
    candidates = resolve_market_candidates(market_query.text, search_results, limit=5)
    if not candidates:
        return ResolvedMarket(ticker='', title='', confidence='low', rationale='no-candidates', candidates=())

    best = candidates[0]
    margin = best.score - candidates[1].score if len(candidates) > 1 else best.score
    confidence = 'high' if best.score >= 9 and margin >= 2 else 'medium' if best.score >= 5 else 'low'
    return ResolvedMarket(
        ticker=best.ticker,
        title=best.title,
        confidence=confidence,
        rationale=best.rationale,
        candidates=tuple(candidates),
        meta={'query': query, 'score_margin': margin},
    )
