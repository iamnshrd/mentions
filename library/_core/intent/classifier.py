"""Intent classifier — LLM-preferred, rule-backed.

Returns an :class:`IntentResult` with:

* ``intent``    — one of :data:`INTENTS`
* ``confidence`` — float in ``[0, 1]``
* ``route``      — the legacy route name (for existing orchestrator)
* ``entities``   — extracted ticker / speaker / event / date_range
* ``source``     — ``'llm'`` or ``'rules'``

Behavior:

1. When an :class:`~library._core.llm.LLMClient` is supplied and
   returns a valid JSON response, that wins. The LLM is told the
   canonical intent list and the response schema.
2. When the LLM is unavailable or returns junk, fall back to
   deterministic keyword rules (a thin wrapper over
   :func:`library._core.runtime.routes.infer_route`) plus regex entity
   extraction.

Design notes:

* The system prompt is **static** per process — designed to be cached
  via Anthropic's prompt cache. Callers can pass
  ``cache_system=True`` to :meth:`complete_json`.
* Temperature is pinned at 0 — classification should be deterministic.
* The classifier never raises on malformed LLM output; it falls back.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field

from library._core.llm import LLMClient, NullClient, default_client
from library._core.obs import get_collector, trace_event
from library._core.runtime.routes import ROUTES, infer_route

log = logging.getLogger('mentions')


# ── Intent taxonomy ────────────────────────────────────────────────────────

INTENTS: tuple[str, ...] = (
    'market_analysis',   # "why is BTC moving today?"
    'speaker_lookup',    # "what has Powell said about rates?"
    'historical_case',   # "similar setup to 2024 election night"
    'heuristic_lookup',  # "what's the rule for entry pricing?"
    'breaking_news',     # "fed just announced"
    'portfolio_check',   # "should I close my BTC position?"
    'comparison',        # "kalshi vs polymarket on Trump"
    'general_chat',      # fallback
)

# Legacy route → default intent mapping for rule-based fallback.
_ROUTE_TO_INTENT: dict[str, str] = {
    'price-movement':    'market_analysis',
    'trend-analysis':    'market_analysis',
    'context-research':  'market_analysis',
    'comparison':        'comparison',
    'portfolio':         'portfolio_check',
    'breaking-news':     'breaking_news',
    'macro':             'market_analysis',
    'speaker-history':   'speaker_lookup',
    'signal-or-noise':   'market_analysis',
    'speaker-event':     'speaker_lookup',
    'general-market':    'general_chat',
}


# ── Output dataclass ───────────────────────────────────────────────────────

@dataclass
class IntentResult:
    intent:     str
    route:      str
    confidence: float
    source:     str   # 'llm' | 'rules'
    entities:   dict = field(default_factory=dict)
    raw:        dict | None = None   # original LLM JSON, if any

    def as_dict(self) -> dict:
        return asdict(self)


# ── LLM prompt (static, cacheable) ─────────────────────────────────────────

_SYSTEM_PROMPT = f"""You are a query-intent classifier for a prediction-market analyst agent named Mentions.

Given a single user query, return ONLY a JSON object (no prose, no fences) with this schema:

{{
  "intent":      one of {list(INTENTS)},
  "route":       one of {sorted(ROUTES.keys())},
  "confidence":  float in [0, 1],
  "entities": {{
    "ticker":       string or null,       // Kalshi-style ticker like 'KXBTCD-25DEC' if clearly present
    "speaker":      string or null,       // person name if the query references a named speaker
    "event":        string or null,       // named event (e.g. 'FOMC 2024-12', 'World Cup final')
    "date_range":   string or null,       // natural-language range (e.g. 'last week', 'since October')
    "market_type":  string or null        // 'binary', 'multi', 'scalar' if inferable
  }}
}}

Rules:
- Queries mix English and Russian; treat them equivalently.
- If multiple intents fit, pick the most specific.
- Use 'general_chat' only when nothing else fits (e.g. greetings).
- Confidence reflects your certainty about 'intent', NOT about 'entities'.
- Omit fields you cannot infer by setting their value to null (not an empty string).
- Never add commentary. Never wrap in code fences. Output ONLY the JSON object.
"""


# ── Public entry point ─────────────────────────────────────────────────────

def classify_intent(query: str, client: LLMClient | None = None) -> IntentResult:
    """Classify *query* into an :class:`IntentResult`.

    The *client* arg lets tests and specialised callers inject a fake
    or a specific model; when omitted we use :func:`default_client`.
    """
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

    # Skip the LLM when we know it's a no-op — saves a function call.
    if not isinstance(client, NullClient):
        metrics.incr('intent.llm_attempt')
        with metrics.timed('intent.llm_latency_ms'):
            result = _classify_via_llm(query, client)
        if result is not None:
            metrics.incr('intent.llm_success')
            metrics.incr('intent.result', tags={'source': 'llm',
                                                'intent': result.intent})
            trace_event('intent.classify',
                        source='llm',
                        intent=result.intent,
                        route=result.route,
                        confidence=result.confidence)
            return result
        metrics.incr('intent.llm_failure')

    metrics.incr('intent.rules_fallback')
    result = _classify_via_rules(query)
    metrics.incr('intent.result', tags={'source': 'rules',
                                        'intent': result.intent})
    trace_event('intent.classify',
                source='rules',
                intent=result.intent,
                route=result.route,
                confidence=result.confidence)
    return result


# ── LLM path ───────────────────────────────────────────────────────────────

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
    route  = raw.get('route', '')
    if intent not in INTENTS:
        log.debug('LLM returned unknown intent=%r; falling back', intent)
        return None
    if route not in ROUTES:
        # Repair by mapping via intent.
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
            'ticker':      _s(entities_in.get('ticker')),
            'speaker':     _s(entities_in.get('speaker')),
            'event':       _s(entities_in.get('event')),
            'date_range':  _s(entities_in.get('date_range')),
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
    """Coerce to trimmed str, treating 'null'/empty as empty."""
    if v is None:
        return ''
    s = str(v).strip()
    if s.lower() in {'null', 'none', ''}:
        return ''
    return s


# ── Rule-based fallback ────────────────────────────────────────────────────

_TICKER_RE   = re.compile(r'\b([A-Z]{2,10}-[A-Z0-9]{2,10}(?:-[A-Z0-9]{2,10})*)\b')
_PERSON_RE   = re.compile(
    r'\b([A-ZА-Я][a-zа-я]{2,}(?:\s+[A-ZА-Я][a-zа-я]{2,}){0,2})\b'
)
# Known single-name signals — cheap and mostly unambiguous for this domain.
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
            route  = 'speaker-history'

    # Confidence heuristic: scale by number of keyword hits for the winning
    # route. Zero hits = we defaulted, so low confidence.
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
    # Proper-noun heuristic: two capitalised tokens in a row, not at start
    # of sentence, to reduce false positives.
    for m in _PERSON_RE.finditer(query):
        name = m.group(1)
        if ' ' in name:
            return name
    return ''
