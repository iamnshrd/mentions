from __future__ import annotations

import logging

from agents.mentions.module_contracts import ensure_dict, ensure_list, normalize_confidence

log = logging.getLogger('mentions')


def build_market_prior(market_data_bundle: dict) -> dict:
    market_data_bundle = ensure_dict(market_data_bundle)
    market = ensure_dict(market_data_bundle.get('market', {}))
    history = ensure_list(market_data_bundle.get('history', []))
    resolved = ensure_dict(market_data_bundle.get('resolved_market', {}))
    provider_status = ensure_dict(market_data_bundle.get('provider_status', {}))

    yes_price, prior_source = _extract_probability(market)
    history_points = len(history)
    liquidity = _extract_liquidity(market)
    spread = _extract_spread(market)
    volume = _extract_volume(market)

    prior_quality = _prior_quality(yes_price, liquidity, spread, volume, history_points, prior_source)
    diagnostics = _prior_diagnostics(yes_price, liquidity, spread, volume, history_points, prior_source, prior_quality)
    return {
        'ticker': resolved.get('ticker', market_data_bundle.get('ticker', '')),
        'title': resolved.get('title', market.get('title', '')),
        'prior_probability': yes_price,
        'prior_confidence': _prior_confidence(yes_price, liquidity, spread, history_points, provider_status, prior_source, prior_quality),
        'prior_quality': prior_quality,
        'market_regime': _market_regime(yes_price, liquidity, spread),
        'microstructure_flags': _microstructure_flags(liquidity, spread, volume, history_points, prior_source, prior_quality),
        'provider_status': provider_status,
        'prior_source': prior_source,
        'prior_diagnostics': diagnostics,
        'source': 'kalshi_market_prior',
    }


def _extract_probability(market: dict) -> tuple[float | None, str]:
    yes_bid = _normalize_probability(market.get('yes_bid_dollars') if market.get('yes_bid_dollars') is not None else market.get('yes_bid'))
    yes_ask = _normalize_probability(market.get('yes_ask_dollars') if market.get('yes_ask_dollars') is not None else market.get('yes_ask'))
    last_price = _normalize_probability(market.get('last_price_dollars') if market.get('last_price_dollars') is not None else market.get('last_price'))
    prev_bid = _normalize_probability(market.get('previous_yes_bid_dollars'))
    prev_ask = _normalize_probability(market.get('previous_yes_ask_dollars'))
    prev_last = _normalize_probability(market.get('previous_price_dollars'))

    if yes_bid is not None and yes_ask is not None:
        spread = yes_ask - yes_bid
        if spread <= 0.25:
            return round((yes_bid + yes_ask) / 2, 4), 'mid_from_bid_ask'
        return yes_bid, 'yes_bid_wide_ask_ignored'
    if yes_bid is not None:
        return yes_bid, 'yes_bid'
    if yes_ask is not None and yes_ask < 0.95:
        return yes_ask, 'yes_ask'
    if last_price is not None and 0.01 < last_price < 0.99:
        return last_price, 'last_price'
    if prev_bid is not None and prev_ask is not None:
        spread = prev_ask - prev_bid
        if spread <= 0.25:
            return round((prev_bid + prev_ask) / 2, 4), 'mid_from_previous_bid_ask'
        return prev_bid, 'previous_yes_bid_wide_ask_ignored'
    if prev_bid is not None:
        return prev_bid, 'previous_yes_bid'
    if prev_ask is not None and prev_ask < 0.95:
        return prev_ask, 'previous_yes_ask'
    if prev_last is not None and 0.01 < prev_last < 0.99:
        return prev_last, 'previous_last_price'
    return None, 'unavailable'


def _normalize_probability(value) -> float | None:
    if value is None or value == '':
        return None
    try:
        numeric = float(value)
    except Exception as exc:
        log.debug('Failed to normalize probability from %r: %s', value, exc)
        return None
    if numeric > 1:
        numeric = numeric / 100.0
    if 0 <= numeric <= 1:
        return round(numeric, 4)
    return None


def _extract_liquidity(market: dict) -> float:
    for key in ['liquidity', 'open_interest', 'volume', 'liquidity_dollars', 'open_interest_fp', 'volume_fp']:
        try:
            return float(market.get(key, 0) or 0)
        except Exception as exc:
            log.debug('Failed to parse liquidity field %s=%r: %s', key, market.get(key), exc)
            continue
    return 0.0


def _extract_spread(market: dict) -> float | None:
    bid_keys = ['yes_bid', 'yes_bid_dollars', 'previous_yes_bid_dollars']
    ask_keys = ['yes_ask', 'yes_ask_dollars', 'previous_yes_ask_dollars']
    for bid_key in bid_keys:
        for ask_key in ask_keys:
            try:
                yes_bid = float(market.get(bid_key))
                yes_ask = float(market.get(ask_key))
                if yes_bid > 1 or yes_ask > 1:
                    yes_bid /= 100.0
                    yes_ask /= 100.0
                if 0 <= yes_bid <= 1 and 0 <= yes_ask <= 1 and yes_ask >= yes_bid:
                    return round(yes_ask - yes_bid, 4)
            except Exception as exc:
                log.debug('Failed to parse spread fields %s/%s: %s', bid_key, ask_key, exc)
                continue
    return None


def _extract_volume(market: dict) -> float:
    for key in ['volume', 'volume_fp', 'volume_24h_fp']:
        try:
            return float(market.get(key, 0) or 0)
        except Exception as exc:
            log.debug('Failed to parse volume field %s=%r: %s', key, market.get(key), exc)
            continue
    return 0.0


def _prior_confidence(probability: float | None, liquidity: float, spread: float | None, history_points: int, provider_status: dict, prior_source: str, prior_quality: str) -> str:
    if probability is None or provider_status.get('market') != 'ok':
        return 'low'
    score = 0
    if spread is not None and spread <= 0.06:
        score += 1
    if liquidity >= 1000:
        score += 1
    if history_points >= 5:
        score += 1
    if prior_source in ('mid_from_bid_ask', 'mid_from_previous_bid_ask', 'yes_bid', 'previous_yes_bid'):
        score += 1
    if prior_quality == 'credible':
        score += 1
    elif prior_quality == 'fragile':
        score -= 1
    elif prior_quality == 'quoted_only':
        score -= 2
    if liquidity == 0 and history_points == 0:
        score -= 1
    if score >= 4:
        return normalize_confidence('high')
    if score >= 1:
        return normalize_confidence('medium')
    return normalize_confidence('low')


def _market_regime(probability: float | None, liquidity: float, spread: float | None) -> str:
    if probability is None:
        return 'unpriced'
    if liquidity < 200 or (spread is not None and spread >= 0.12):
        return 'thin_noisy_market'
    if 0.35 <= probability <= 0.65:
        return 'ambiguous_mid_confidence'
    if probability <= 0.15 or probability >= 0.85:
        return 'high_confidence_market'
    return 'tradable_market'


def _microstructure_flags(liquidity: float, spread: float | None, volume: float, history_points: int, prior_source: str, prior_quality: str) -> list[str]:
    flags = []
    if liquidity < 200:
        flags.append('low_liquidity')
    if spread is None:
        flags.append('spread_unknown')
    elif spread >= 0.12:
        flags.append('wide_spread')
    if volume < 100:
        flags.append('light_volume')
    if history_points == 0:
        flags.append('no_history')
    if 'ask' in prior_source and 'bid' not in prior_source:
        flags.append('ask_only_prior')
    if 'wide_ask_ignored' in prior_source:
        flags.append('wide_ask_ignored')
    if prior_quality == 'fragile':
        flags.append('fragile_prior')
    if prior_quality == 'quoted_only':
        flags.append('quoted_only_prior')
    return flags


def _prior_quality(probability: float | None, liquidity: float, spread: float | None, volume: float, history_points: int, prior_source: str) -> str:
    if probability is None:
        return 'unavailable'
    if liquidity == 0 and volume == 0 and history_points == 0:
        return 'quoted_only'
    if spread is not None and spread >= 0.2:
        return 'fragile'
    if liquidity < 200 and volume < 100:
        return 'fragile'
    if prior_source in ('mid_from_bid_ask', 'yes_bid', 'mid_from_previous_bid_ask', 'previous_yes_bid'):
        return 'credible'
    return 'fragile'


def _prior_diagnostics(probability: float | None, liquidity: float, spread: float | None, volume: float, history_points: int, prior_source: str, prior_quality: str) -> dict:
    return {
        'probability': probability,
        'liquidity': liquidity,
        'spread': spread,
        'volume': volume,
        'history_points': history_points,
        'prior_source': prior_source,
        'prior_quality': prior_quality,
    }
