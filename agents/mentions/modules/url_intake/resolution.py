from __future__ import annotations

from agents.mentions.modules.kalshi_provider import get_markets_bundle


def recover_canonical_ticker(intake: dict, limit: int = 100) -> dict:
    if not intake.get('is_url'):
        return intake

    if intake.get('has_explicit_url_ticker') and intake.get('pretty_slug'):
        out = dict(intake)
        out['resolved_from_url_slug'] = False
        out['url_resolution_confidence'] = 'explicit-url-ticker'
        return out

    series_slug = intake.get('series_slug', '')
    raw_slug = ((intake.get('pretty_slug') or intake.get('ticker') or '').lower())
    if not series_slug or not raw_slug:
        return intake

    bundle = get_markets_bundle(category=series_slug.upper(), limit=limit, status='open')
    markets = bundle.get('markets', [])
    best = _match_market_slug(raw_slug, markets)
    if best:
        out = dict(intake)
        out['ticker'] = best.get('ticker', out.get('ticker', ''))
        out['resolved_from_url_slug'] = True
        out['url_resolution_confidence'] = 'high'
        out['url_resolution_title'] = best.get('title', '')
        return out

    out = dict(intake)
    out['resolved_from_url_slug'] = False
    out['url_resolution_confidence'] = 'low'
    return out


def _match_market_slug(raw_slug: str, markets: list[dict]) -> dict:
    slug_tokens = set(_tokenize_slug(raw_slug))
    best = None
    best_score = -1
    generic_tokens = {'what', 'will', 'say', 'during', 'trump', 'donald'}
    content_tokens = [token for token in slug_tokens if token not in generic_tokens]

    for market in markets:
        title = (market.get('title', '') or '').lower()
        yes_sub = (market.get('yes_sub_title', '') or '').lower()
        subtitle = (market.get('subtitle', '') or '').lower()
        ticker = (market.get('ticker', '') or '').lower()
        combined = ' '.join([title, yes_sub, subtitle, ticker])
        score = 0

        for token in slug_tokens:
            if token and token in combined:
                score += 1
        for token in content_tokens:
            if token and (token == yes_sub or token in yes_sub or token in subtitle):
                score += 4
        if yes_sub:
            yes_tokens = set(_tokenize_slug(yes_sub))
            overlap = len(yes_tokens.intersection(content_tokens))
            score += overlap * 3

        if score > best_score:
            best_score = score
            best = market
    return best if best_score > 0 else {}


def _tokenize_slug(value: str) -> list[str]:
    return [token for token in value.lower().replace('-', ' ').split() if len(token) > 2]
