"""Canonical route registry for Mentions workflows."""
from __future__ import annotations

ROUTES: dict[str, dict] = {
    'price-movement': {
        'keywords': [
            'pump', 'dump', 'spike', 'crash', 'jump', 'drop', 'surge', 'fell',
            'rose', 'moved', 'резко', 'skyrocket', 'plunge', 'rally', 'selloff',
            'what happened', 'что случилось', 'why did', 'почему упал', 'почему вырос',
        ],
        'voice_bias': 'quick',
    },
    'trend-analysis': {
        'keywords': [
            'trend', 'тренд', 'direction', 'куда идёт', 'where is it going',
            'heading', 'momentum', 'trajectory', 'over time', 'over the past',
            'long-term', 'short-term', 'pattern', 'паттерн',
        ],
        'voice_bias': 'deep',
    },
    'context-research': {
        'keywords': [
            'why', 'почему', 'what caused', 'reason', 'причина', 'catalyst',
            'behind', 'context', 'контекст', 'explain', 'объясни', 'background',
            'what happened', 'history', 'история',
        ],
        'voice_bias': 'deep',
    },
    'comparison': {
        'keywords': [
            'vs', 'versus', 'против', 'compare', 'сравни', 'difference',
            'relative', 'vs market', 'better than', 'worse than', 'which',
        ],
        'voice_bias': 'analytical',
    },
    'portfolio': {
        'keywords': [
            'portfolio', 'портфель', 'position', 'позиция', 'exposure',
            'allocation', 'bet', 'risk', 'hedge', 'sizing',
        ],
        'voice_bias': 'deep',
    },
    'breaking-news': {
        'keywords': [
            'breaking', 'just happened', 'just announced', 'just now', 'live',
            'only just', 'latest', 'новость', 'only now', 'прямо сейчас',
            'сегодня', 'today', 'right now',
        ],
        'voice_bias': 'quick',
    },
    'macro': {
        'keywords': [
            'fed', 'federal reserve', 'rate', 'fomc', 'powell', 'inflation',
            'cpi', 'gdp', 'recession', 'economy', 'jobs report', 'unemployment',
            'macro', 'interest rate', 'yield', 'bond', 'treasury',
        ],
        'voice_bias': 'deep',
    },
    'speaker-history': {
        'keywords': [
            'said', 'speech', 'говорил', 'transcript', 'transcript', 'statement',
            'comments', 'remarked', 'noted', 'historically said', 'in the past',
            'has said', 'quote', 'цитата', 'what did',
        ],
        'voice_bias': 'deep',
    },
    'signal-or-noise': {
        'keywords': [
            'signal', 'noise', 'real', 'fake', 'meaningful', 'significant',
            'should I', 'worth watching', 'ignore', 'matters', 'имеет значение',
            'real move', 'just noise',
        ],
        'voice_bias': 'analytical',
    },
    'speaker-event': {
        'keywords': [
            'mention', 'will mention', 'will say', 'will address',
            'press conference', 'presser', 'speech', 'interview',
            'will speak', 'statement', 'briefing', 'testimony',
            'conference', 'summit', 'forum', 'panel',
            'infantino', 'powell', 'trump', 'biden', 'lagarde',
        ],
        'voice_bias': 'deep',
    },
    'general-market': {
        'keywords': [
            'market', 'рынок', 'kalshi', 'prediction', 'contract', 'ticker',
            'price', 'цена', 'yes', 'no', 'resolve', 'expires', 'trading',
            'volume', 'объём', 'liquidity', 'orderbook',
        ],
        'voice_bias': None,
    },
}

ALL_KB_KEYWORDS: list[str] = sorted(
    {kw for route in ROUTES.values() for kw in route['keywords']}
)


def infer_route(query: str) -> str:
    """Return the best-matching route name for *query*, or 'general-market'."""
    q = query.lower()
    best_route = 'general-market'
    best_score = 0
    for route_name, spec in ROUTES.items():
        score = sum(1 for kw in spec['keywords'] if kw in q)
        if score > best_score:
            best_score = score
            best_route = route_name
    return best_route


def route_voice_bias(route_name: str) -> str | None:
    """Return the voice bias for a route, or None."""
    spec = ROUTES.get(route_name)
    return spec['voice_bias'] if spec else None


__all__ = ['ALL_KB_KEYWORDS', 'ROUTES', 'infer_route', 'route_voice_bias']
