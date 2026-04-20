"""Intent classifier — LLM-preferred, rule-backed."""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field

from mentions_domain.llm import LLMClient, NullClient, default_client
from mentions_core.base.obs import get_collector, trace_event
from agents.mentions.workflows.routes import ROUTES, infer_route

log = logging.getLogger('mentions')

INTENTS: tuple[str, ...] = (
    'market_analysis',
    'speaker_lookup',
    'historical_case',
    'heuristic_lookup',
    'breaking_news',
    'portfolio_check',
    'comparison',
    'general_chat',
)

_ROUTE_TO_INTENT: dict[str, str] = {
    'price-movement': 'market_analysis',
    'trend-analysis': 'market_analysis',
    'context-research': 'market_analysis',
    'comparison': 'comparison',
    'portfolio': 'portfolio_check',
    'breaking-news': 'breaking_news',
    'macro': 'market_analysis',
    'speaker-history': 'speaker_lookup',
    'signal-or-noise': 'market_analysis',
    'speaker-event': 'speaker_lookup',
    'general-market': 'general_chat',
}


@dataclass
class IntentResult:
    intent: str
    route: str
    confidence: float
    source: str
    entities: dict = field(default_factory=dict)
    raw: dict | None = None

    def as_dict(self) -> dict:
        return asdict(self)


_SYSTEM_PROMPT = f"""You are a query-intent classifier for a prediction-market analyst agent named Mentions.

Given a single user query, return ONLY a JSON object (no prose, no fences) with this schema:

{{
  "intent":      one of {list(INTENTS)},
  "route":       one of {sorted(ROUTES.keys())},
  "confidence":  float in [0, 1],
  "entities": {{
    "ticker":       string or null,
    "speaker":      string or null,
    "event":        string or null,
    "date_range":   string or null,
    "market_type":  string or null
  }}
}}

Rules:
- Queries mix English and Russian; treat them equivalently.
- If multiple intents fit, pick the most specific.
- Use 'general_chat' only when nothing else fits.
- Confidence reflects your certainty about 'intent', not about 'entities'.
- Omit fields you cannot infer by setting their value to null.
- Output ONLY the JSON object.
"""


def classify_intent(query: str, client: LLMClient | None = None) -> IntentResult:
    if not query or not query.strip():
        return IntentResult(
            intent='general_chat',
            route='general-market',
            confidence=0.0,
            source='rules',
            entities={},
        )

    client = client or default_client()
    metrics = get_collector()

    if not isinstance(client, NullClient):
        metrics.incr('intent.llm_attempt')
        with metrics.timed('intent.llm_latency_ms'):
            result = _classify_via_llm(query, client)
        if result is not None:
            metrics.incr('intent.llm_success')
            metrics.incr('intent.result', tags={'source': 'llm', 'intent': result.intent})
            trace_event(
                'intent.classify',
                source='llm',
                intent=result.intent,
                route=result.route,
                confidence=result.confidence,
            )
            return result
        metrics.incr('intent.llm_failure')

    metrics.incr('intent.rules_fallback')
    result = _classify_via_rules(query)
    metrics.incr('intent.result', tags={'source': 'rules', 'intent': result.intent})
    trace_event(
        'intent.classify',
        source='rules',
        intent=result.intent,
        route=result.route,
        confidence=result.confidence,
    )
    return result


def _classify_via_llm(query: str, client: LLMClient) -> IntentResult | None:
    try:
        raw = client.complete_json(
            system=_SYSTEM_PROMPT,
            user=query,
            max_tokens=300,
            temperature=0.0,
            cache_system=True,
        )
    except Exception as exc:
        log.debug('LLM classify_intent failed: %s', exc)
        return None

    if not raw or not isinstance(raw, dict):
        return None

    intent = raw.get('intent', '')
    route = raw.get('route', '')
    if intent not in INTENTS:
        log.debug('LLM returned unknown intent=%r; falling back', intent)
        return None
    if route not in ROUTES:
        for r, i in _ROUTE_TO_INTENT.items():
            if i == intent:
                route = r
                break
        else:
            route = 'general-market'

    try:
        confidence = float(raw.get('confidence', 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    entities_in = raw.get('entities') or {}
    entities = {
        k: v for k, v in {
            'ticker': _s(entities_in.get('ticker')),
            'speaker': _s(entities_in.get('speaker')),
            'event': _s(entities_in.get('event')),
            'date_range': _s(entities_in.get('date_range')),
            'market_type': _s(entities_in.get('market_type')),
        }.items() if v
    }

    return IntentResult(
        intent=intent,
        route=route,
        confidence=confidence,
        source='llm',
        entities=entities,
        raw=raw,
    )


def _s(v) -> str:
    if v is None:
        return ''
    s = str(v).strip()
    if s.lower() in {'null', 'none', ''}:
        return ''
    return s


_TICKER_RE = re.compile(r'\b([A-Z]{2,10}-[A-Z0-9]{2,10}(?:-[A-Z0-9]{2,10})*)\b')
_PERSON_RE = re.compile(r'\b([A-ZА-Я][a-zа-я]{2,}(?:\s+[A-ZА-Я][a-zа-я]{2,}){0,2})\b')
_KNOWN_SPEAKERS = {
    'powell', 'trump', 'biden', 'lagarde', 'infantino', 'putin', 'xi',
    'yellen', 'bernanke', 'musk', 'navalny',
}


def _classify_via_rules(query: str) -> IntentResult:
    route = infer_route(query)
    intent = _ROUTE_TO_INTENT.get(route, 'general_chat')

    entities: dict = {}
    ticker_match = _TICKER_RE.search(query.upper())
    if ticker_match:
        entities['ticker'] = ticker_match.group(1)

    speaker = _extract_speaker(query)
    if speaker:
        entities['speaker'] = speaker
        if intent == 'general_chat':
            intent = 'speaker_lookup'
            route = 'speaker-history'

    spec = ROUTES.get(route, {'keywords': []})
    q = query.lower()
    hits = sum(1 for kw in spec['keywords'] if kw in q)
    confidence = min(0.9, 0.3 + 0.15 * hits)

    return IntentResult(
        intent=intent,
        route=route,
        confidence=confidence,
        source='rules',
        entities=entities,
    )


def _extract_speaker(query: str) -> str:
    ql = query.lower()
    for known in _KNOWN_SPEAKERS:
        if known in ql:
            return known.capitalize()
    for m in _PERSON_RE.finditer(query):
        name = m.group(1)
        if ' ' in name:
            return name
    return ''
