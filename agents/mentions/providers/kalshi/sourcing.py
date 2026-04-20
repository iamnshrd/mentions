from __future__ import annotations

from mentions_domain.market_resolution import extract_market_entities
from .provider import get_event_bundle, get_markets_bundle, search_markets_bundle

SPEAKER_SERIES_HINTS = {
    'Donald Trump': ['KXTRUMPMENTIONB', 'KXTRUMPMENTION', 'TRUMP'],
    'Joe Biden': ['KXBIDENMENTION', 'BIDEN'],
    'Jerome Powell': ['FED', 'KXPOWELL', 'POWELL'],
    'Christine Lagarde': ['ECB', 'LAGARDE'],
}

SPEAKER_EVENT_HINTS = {
    'Donald Trump': ['TRUMPMENTION'],
    'Joe Biden': ['BIDENMENTION'],
}

TOPIC_EVENT_HINTS = {
    'iran': ['IRAN'],
    'fed': ['FED'],
    'rates': ['FED'],
    'inflation': ['CPI', 'INFLATION'],
    'bitcoin': ['BTC', 'BITCOIN'],
    'crypto': ['BTC', 'ETH', 'CRYPTO'],
    'ukraine': ['UKRAINE'],
    'china': ['CHINA'],
    'oil': ['OIL'],
}

TOPIC_ALIASES = {
    'iran': ['iran', 'iranian'],
    'israel': ['israel', 'israeli'],
    'ukraine': ['ukraine', 'ukrainian'],
    'china': ['china', 'chinese'],
    'oil': ['oil', 'crude'],
    'bitcoin': ['bitcoin', 'btc'],
    'crypto': ['crypto', 'cryptocurrency', 'btc', 'eth'],
}


def _append_market_set(result_sets: list[list[dict]], diagnostics: list[str], markets: list[dict], diagnostic: str) -> None:
    if markets:
        result_sets.append(markets)
        diagnostics.append(diagnostic)


def _collect_speaker_series_markets(*, speaker: str, entities: dict, result_sets: list[list[dict]], diagnostics: list[str], limit_per_call: int) -> None:
    for series_hint in SPEAKER_SERIES_HINTS.get(speaker, []):
        initial_limit = max(limit_per_call, 20)
        bundle = get_markets_bundle(category=series_hint, limit=initial_limit, status='open')
        markets = bundle.get('markets', [])
        _append_market_set(result_sets, diagnostics, markets, f'series:{series_hint}')
        if markets and _should_expand_series(markets, entities):
            expanded_bundle = get_markets_bundle(category=series_hint, limit=100, status='open')
            expanded_markets = expanded_bundle.get('markets', [])
            _append_market_set(result_sets, diagnostics, expanded_markets, f'series-expand:{series_hint}')


def _collect_speaker_event_markets(*, speaker: str, entities: dict, result_sets: list[list[dict]], diagnostics: list[str], limit_per_call: int) -> None:
    for event_hint in SPEAKER_EVENT_HINTS.get(speaker, []):
        event_bundle = search_markets_bundle(event_hint, limit=limit_per_call)
        event_markets = event_bundle.get('markets', [])
        filtered_event_markets = [m for m in event_markets if _eligible_event_seed(m, entities)]
        _append_market_set(result_sets, diagnostics, filtered_event_markets, f'event-search:{event_hint}')
        if filtered_event_markets:
            expanded_events = set()
            for market in filtered_event_markets[:5]:
                event_ticker = market.get('event_ticker', '')
                if not event_ticker or event_ticker in expanded_events:
                    continue
                expanded_events.add(event_ticker)
                expanded = get_markets_bundle(event_ticker=event_ticker, limit=50, status='open')
                expanded_markets = expanded.get('markets', [])
                _append_market_set(result_sets, diagnostics, expanded_markets, f'event-expand:{event_ticker}')


def _collect_topic_search_markets(*, topics: list[str], result_sets: list[list[dict]], diagnostics: list[str], limit_per_call: int) -> None:
    for topic in topics:
        for event_hint in TOPIC_EVENT_HINTS.get(topic, []):
            bundle = search_markets_bundle(event_hint, limit=limit_per_call)
            markets = bundle.get('markets', [])
            _append_market_set(result_sets, diagnostics, markets, f'topic-search:{event_hint}')


def build_candidate_market_pool(query: str, limit_per_call: int = 12) -> dict:
    entities = extract_market_entities(query)
    result_sets: list[list[dict]] = []
    diagnostics: list[str] = []

    for speaker in entities.get('speakers', []):
        _collect_speaker_series_markets(
            speaker=speaker,
            entities=entities,
            result_sets=result_sets,
            diagnostics=diagnostics,
            limit_per_call=limit_per_call,
        )

        _collect_speaker_event_markets(
            speaker=speaker,
            entities=entities,
            result_sets=result_sets,
            diagnostics=diagnostics,
            limit_per_call=limit_per_call,
        )

    _collect_topic_search_markets(
        topics=entities.get('topics', []),
        result_sets=result_sets,
        diagnostics=diagnostics,
        limit_per_call=limit_per_call,
    )

    fallback = search_markets_bundle(query, limit=limit_per_call)
    _append_market_set(result_sets, diagnostics, fallback.get('markets', []), 'fallback-search')

    merged = _merge_market_sets(result_sets)
    filtered, filtering_diagnostics = _filter_market_pool(merged, entities)
    return {
        'query': query,
        'entities': entities,
        'markets': filtered,
        'diagnostics': diagnostics + filtering_diagnostics,
        'raw_market_count': len(merged),
        'filtered_market_count': len(filtered),
    }


def _merge_market_sets(result_sets: list[list[dict]]) -> list[dict]:
    merged = []
    seen = set()
    for market_list in result_sets:
        for market in market_list:
            ticker = market.get('ticker', '')
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            merged.append(market)
    return merged


def _eligible_event_seed(market: dict, entities: dict) -> bool:
    if not _looks_like_mention_market(market):
        return False
    speakers = [speaker.lower() for speaker in entities.get('speakers', [])]
    if speakers and not _matches_speaker(market, speakers):
        return False
    return True


def _should_expand_series(markets: list[dict], entities: dict) -> bool:
    if not markets:
        return False
    if not entities.get('is_mention_style'):
        return False
    topics = [topic.lower() for topic in entities.get('topics', [])]
    if not topics:
        return False
    return not any(_matches_topic(market, topics) for market in markets)


def _filter_market_pool(markets: list[dict], entities: dict) -> tuple[list[dict], list[str]]:
    if not markets:
        return [], []

    filtered = markets
    diagnostics: list[str] = []
    topics = [topic.lower() for topic in entities.get('topics', [])]
    is_mention_style = bool(entities.get('is_mention_style'))
    speakers = [speaker.lower() for speaker in entities.get('speakers', [])]

    if is_mention_style:
        mention_only = [m for m in filtered if _looks_like_mention_market(m)]
        if mention_only:
            filtered = mention_only
            diagnostics.append('filter:mention-series-priority')

    if speakers:
        speaker_only = [m for m in filtered if _matches_speaker(m, speakers)]
        if speaker_only:
            filtered = speaker_only
            diagnostics.append('filter:speaker-match')

    if topics:
        exact_topic = [m for m in filtered if _matches_topic_exact_label(m, topics)]
        if exact_topic:
            filtered = exact_topic
            diagnostics.append('filter:exact-topic-label')
        else:
            topic_only = [m for m in filtered if _matches_topic(m, topics)]
            if topic_only:
                filtered = topic_only
                diagnostics.append('filter:topic-match')

    return filtered, diagnostics


def _looks_like_mention_market(market: dict) -> bool:
    ticker = (market.get('ticker', '') or '').lower()
    title = (market.get('title', '') or '').lower()
    return 'mention' in ticker or 'what will' in title or 'say during' in title or 'mention' in title


def _matches_speaker(market: dict, speakers: list[str]) -> bool:
    title = (market.get('title', '') or '').lower()
    ticker = (market.get('ticker', '') or '').lower()
    for speaker in speakers:
        parts = speaker.split()
        if any(part in title or part in ticker for part in parts if len(part) > 2):
            return True
    return False


def _matches_topic_exact_label(market: dict, topics: list[str]) -> bool:
    label = (market.get('yes_sub_title', '') or market.get('subtitle', '') or '').lower().strip()
    ticker = (market.get('ticker', '') or '').lower()
    for topic in topics:
        aliases = TOPIC_ALIASES.get(topic, [topic])
        if any(label == alias for alias in aliases):
            return True
    return False


def _matches_topic(market: dict, topics: list[str]) -> bool:
    title = (market.get('title', '') or '').lower()
    ticker = (market.get('ticker', '') or '').lower()
    subtitle = (market.get('subtitle', '') or '').lower()
    yes_sub = (market.get('yes_sub_title', '') or '').lower()
    no_sub = (market.get('no_sub_title', '') or '').lower()
    combined = ' '.join([title, ticker, subtitle, yes_sub, no_sub])
    label_tokens = _normalized_label_tokens(market)

    for topic in topics:
        aliases = TOPIC_ALIASES.get(topic, [topic])
        if any(alias in combined for alias in aliases):
            return True
        if any(alias in label_tokens for alias in aliases):
            return True
    return False


def _normalized_label_tokens(market: dict) -> set[str]:
    raw = ' '.join([
        market.get('ticker', '') or '',
        market.get('subtitle', '') or '',
        market.get('yes_sub_title', '') or '',
        market.get('no_sub_title', '') or '',
    ]).lower()

    cleaned = []
    token = []
    for ch in raw:
        if ch.isalnum():
            token.append(ch)
        else:
            if token:
                cleaned.append(''.join(token))
                token = []
    if token:
        cleaned.append(''.join(token))
    return set(cleaned)
