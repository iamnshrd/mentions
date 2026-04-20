from __future__ import annotations

import logging
import re

from agents.mentions.workflows.retrieval_fallbacks import empty_news_context, empty_transcript_context
from agents.mentions.providers.kalshi import get_event_bundle, get_history_bundle, get_market_bundle, get_markets_bundle
from agents.mentions.utils import get_threshold

log = logging.getLogger('mentions')


def _build_series_fallback_market(ticker: str, series_guess: str, target_event: list[dict]) -> dict:
    representative = target_event[0]
    event_title = _canonical_recurring_title(series_guess, target_event)
    strike_title = representative.get('yes_sub_title', '')
    human_title = _best_market_title(representative, fallback=event_title)
    return {
        'ticker': ticker,
        'title': human_title,
        'event_title': event_title,
        'strike_title': strike_title,
        'series_ticker': series_guess,
        'event_ticker': representative.get('event_ticker', ticker),
        'status': representative.get('status', ''),
        'yes_sub_title': strike_title,
        'market_count': len(target_event),
        'event_markets': target_event,
        'strike_list': _extract_strike_list(target_event),
        'resolution_source': 'series-event-fallback',
        'close_time': representative.get('close_time', representative.get('expiration_time', '')),
        'expiration_time': representative.get('expiration_time', representative.get('close_time', '')),
        'open_time': representative.get('open_time', ''),
        'rules_primary': representative.get('rules_primary', representative.get('rules', '')),
        'rules_secondary': representative.get('rules_secondary', ''),
        'volume': representative.get('volume', representative.get('volume_dollars')),
        'subtitle': representative.get('subtitle', ''),
        'no_sub_title': representative.get('no_sub_title', ''),
    }


def _build_event_payload(event_ticker: str, event_payload: dict) -> dict:
    event = event_payload.get('event', {}) if isinstance(event_payload, dict) else {}
    markets = event_payload.get('markets', []) if isinstance(event_payload, dict) else []
    if not markets:
        return {}
    representative = markets[0]
    event_title = (event.get('title') or '').strip() or _canonical_recurring_title(event.get('series_ticker', ''), markets)
    strike_title = representative.get('yes_sub_title', '')
    human_title = _best_market_title(representative, fallback=event_title)
    return {
        'ticker': event_ticker,
        'title': human_title,
        'event_title': event_title,
        'strike_title': strike_title,
        'series_ticker': event.get('series_ticker', ''),
        'event_ticker': event.get('ticker', event_ticker),
        'status': representative.get('status', event.get('status', '')),
        'yes_sub_title': strike_title,
        'market_count': len(markets),
        'event_markets': markets,
        'strike_list': _extract_strike_list(markets),
        'entity_kind': 'event',
        'resolution_source': 'event-ticker',
        'close_time': representative.get('close_time', representative.get('expiration_time', '')),
        'expiration_time': representative.get('expiration_time', representative.get('close_time', '')),
        'open_time': representative.get('open_time', ''),
        'rules_primary': representative.get('rules_primary', event.get('rules_primary', representative.get('rules', ''))),
        'rules_secondary': representative.get('rules_secondary', event.get('rules_secondary', '')),
        'volume': representative.get('volume', representative.get('volume_dollars')),
        'subtitle': representative.get('subtitle', event.get('subtitle', '')),
        'no_sub_title': representative.get('no_sub_title', ''),
    }


def retrieve_market_context_by_ticker(ticker: str, ticker_kind: str = 'unknown') -> dict:
    ticker = ticker.upper()
    market_data: dict = {}
    history: list = []
    resolved_market = {'ticker': ticker, 'title': ''}
    try:
        if ticker_kind == 'market':
            market_bundle = get_market_bundle(ticker)
            market_data = market_bundle.get('market', {}) or {}
        else:
            market_bundle = {'market': {}, 'market_source': 'skipped-direct-market-lookup'}

        if not market_data and ticker_kind in {'event', 'unknown'}:
            event_bundle = get_event_bundle(ticker, with_nested_markets=True)
            event_payload = {
                'event': event_bundle.get('event', {}),
                'markets': event_bundle.get('markets', []),
            }
            market_data = _build_event_payload(ticker, event_payload)

        if not market_data:
            series_guess = _series_from_event_ticker(ticker)
            if series_guess:
                series_bundle = get_markets_bundle(category=series_guess, limit=200, status='')
                series_markets = series_bundle.get('markets', []) or []
                target_event = _pick_event_market_group(ticker, series_markets)
                if target_event:
                    market_data = _build_series_fallback_market(ticker, series_guess, target_event)

        series_ticker = market_data.get('series_ticker', '') if isinstance(market_data, dict) else ''
        days = get_threshold('history_days_default', 30)
        if market_data.get('ticker') and market_data.get('resolution_source') not in {'series-fallback', 'series-event-fallback'}:
            history_bundle = get_history_bundle(ticker, series_ticker=series_ticker, days=days)
            history = history_bundle.get('history', []) or []
        resolved_market = {
            'ticker': (market_data or {}).get('ticker', ticker),
            'title': (market_data or {}).get('title', ''),
        }
    except Exception as exc:
        log.warning('Kalshi fetch failed for ticker %s: %s', ticker, exc)
    if market_data and 'entity_kind' not in market_data:
        market_data['entity_kind'] = 'market' if ticker_kind == 'market' else 'event' if market_data.get('event_markets') else 'market'
    if market_data and 'resolution_source' not in market_data:
        market_data['resolution_source'] = 'direct-market' if ticker_kind == 'market' else 'event-ticker'
    return {
        'ticker': ticker,
        'ticker_kind': ticker_kind,
        'market_data': market_data,
        'history': history,
        'resolved_market': resolved_market,
        'entity_kind': market_data.get('entity_kind', 'unknown') if market_data else 'unknown',
        'resolution_source': market_data.get('resolution_source', 'unavailable') if market_data else 'unavailable',
    }


def _pick_event_market_group(ticker: str, markets: list[dict]) -> list[dict]:
    target = (ticker or '').upper().strip()
    if not target:
        return []
    exact = [m for m in markets if (m.get('event_ticker') or '').upper() == target]
    if exact:
        return exact
    event_date = target.split('-')[-1] if '-' in target else ''
    if event_date:
        close_match = [m for m in markets if event_date in (m.get('event_ticker') or '').upper()]
        if close_match:
            return close_match
    return markets[:1]


def _stable_series_title(markets: list[dict]) -> str:
    if not markets:
        return ''
    titles = [(m.get('title') or '').strip() for m in markets if (m.get('title') or '').strip()]
    if not titles:
        return ''
    first = titles[0]
    prefix = first
    for title in titles[1:]:
        while prefix and not title.startswith(prefix):
            prefix = prefix[:-1]
    prefix = prefix.rstrip(' ,:-')
    if prefix and len(prefix) >= 20:
        return prefix
    return first


_RECURRING_SERIES_TITLES = {
    'KXSECPRESSMENTION': 'What will the White House Press Secretary say at the next press briefing?',
    'KXTRUMPMENTION': 'What will Donald Trump say at the event?',
}


def _canonical_recurring_title(series_ticker: str, markets: list[dict]) -> str:
    series = (series_ticker or '').upper().strip()
    best = _stable_series_title(markets)
    if series == 'KXTRUMPMENTION':
        return best or _RECURRING_SERIES_TITLES[series]
    return _RECURRING_SERIES_TITLES.get(series, '') or best


def _best_market_title(market: dict, fallback: str = '') -> str:
    title = (market.get('title') or '').strip()
    if title:
        return title
    strike = (market.get('yes_sub_title') or '').strip()
    if strike and fallback:
        return f'{fallback} — `{strike}`'
    return fallback


def _extract_strike_list(markets: list[dict]) -> list[str]:
    strikes: list[str] = []
    seen: set[str] = set()
    for market in markets or []:
        strike = (market.get('yes_sub_title') or market.get('strike_title') or market.get('title') or '').strip()
        if not strike:
            continue
        key = strike.lower()
        if key in seen:
            continue
        seen.add(key)
        strikes.append(strike)
    return strikes


def _series_from_event_ticker(ticker: str) -> str:
    value = (ticker or '').upper().strip()
    if not value or '-' not in value:
        return ''
    parts = value.split('-')
    if len(parts) >= 2:
        suffix = parts[-1]
        if re.fullmatch(r'\d{6}[A-Z]?', suffix):
            return parts[0]
        if suffix.startswith('26') and len(suffix) in {7, 8}:
            return parts[0]
    return ''


def retrieve_transcript_context_by_ticker(ticker: str, speaker: str = '', market_data: dict | None = None) -> tuple[dict, list]:
    market_data = market_data or {}
    search_term = _build_transcript_query_target(ticker, speaker=speaker, market_data=market_data)
    transcript_bundle = empty_transcript_context(search_term or (speaker or ticker), speaker=speaker, status='empty', risk='')
    transcripts: list = []
    if search_term:
        try:
            from agents.mentions.services.transcripts.intelligence import build_transcript_intelligence_bundle
            limit = get_threshold('fts_chunk_limit', 8)
            transcript_bundle = build_transcript_intelligence_bundle(
                search_term,
                limit=limit,
                speaker=speaker or '',
            )
            transcripts = transcript_bundle.get('chunks', [])
        except Exception as exc:
            log.debug('Transcript fetch failed: %s', exc)
    return transcript_bundle, transcripts


_TRANSCRIPT_FORMAT_HINTS = ['roundtable', 'press conference', 'interview', 'remarks', 'meeting', 'announcement']
_TRANSCRIPT_TOPIC_HINTS = ['no tax on tips', 'tax', 'tips', 'ratepayer', 'economy', 'energy', 'iran']
_FAMILY_TITLE_PATTERNS = [
    r'^(What will Donald Trump say during .+?)\?$',
    r'^(What will Donald Trump say at .+?)\?$',
]


def _append_matching_hints(parts: list[str], lowered_text: str, hints: list[str]) -> None:
    for needle in hints:
        if needle in lowered_text and needle not in parts:
            parts.append(needle)


def _build_transcript_query_target(ticker: str, speaker: str = '', market_data: dict | None = None) -> str:
    market_data = market_data or {}
    parts: list[str] = []
    if speaker:
        parts.append(speaker)
    title_blob = ' '.join([
        market_data.get('title', ''),
        market_data.get('event_title', ''),
        market_data.get('rules_primary', ''),
    ])
    lowered = title_blob.lower()
    _append_matching_hints(parts, lowered, _TRANSCRIPT_FORMAT_HINTS)
    _append_matching_hints(parts, lowered, _TRANSCRIPT_TOPIC_HINTS)
    return ' '.join(part for part in parts if part).strip() or (speaker or ticker)


def retrieve_news_context_by_ticker(ticker: str, market_data: dict, speaker: str = '') -> tuple[dict, list, str]:
    family_title = market_data.get('event_title', '') or _family_title_from_market_title(market_data) or market_data.get('title', ticker)
    query_hint = speaker or family_title
    news_bundle = empty_news_context(query_hint, 'general', risk='')
    try:
        from agents.mentions.services.news.context_builder import build_news_context_bundle
        news_bundle = build_news_context_bundle(
            query_hint,
            limit=get_threshold('news_fetch_limit', 5),
            require_live=False,
            market_data=market_data,
            speaker_info={'speaker': speaker} if speaker else None,
        )
    except Exception as exc:
        log.debug('News fetch failed: %s', exc)
    news = news_bundle.get('news', [])
    news_status = news_bundle.get('status', 'unavailable')
    return news_bundle, news, news_status


def _family_title_from_market_title(market_data: dict) -> str:
    title = (market_data.get('title') or '').strip()
    if not title:
        return ''
    for pattern in _FAMILY_TITLE_PATTERNS:
        match = re.match(pattern, title)
        if match:
            return match.group(1) + '?'
    return ''
