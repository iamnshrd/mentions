"""Tests for canonical intent classification.

Covers:
  * Empty query → general_chat / confidence 0
  * NullClient path → rules-based IntentResult (source='rules')
  * FakeClient returning valid JSON → IntentResult (source='llm')
  * FakeClient returning unknown intent → rules fallback
  * FakeClient returning malformed JSON (None) → rules fallback
  * FakeClient raising → rules fallback
  * Rule path: ticker regex, known-speaker promotion to speaker_lookup
  * Rule path: multi-token proper-noun speaker detection
  * Route repair when LLM returns a valid intent but a garbage route
"""
from __future__ import annotations

import pytest

from mentions_domain.intent import INTENTS, IntentResult, classify_intent
from mentions_domain.llm import LLMResponse, NullClient


# ── Fakes ──────────────────────────────────────────────────────────────────

class FakeClient:
    """Canned LLM client. ``payload`` is what ``complete_json`` returns.

    Set ``payload=RuntimeError('boom')`` to simulate a raising call.
    """
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[dict] = []

    def complete(self, **kwargs) -> LLMResponse:
        # Not used by classifier, but must satisfy the protocol.
        import json
        self.calls.append(kwargs)
        if isinstance(self.payload, BaseException):
            raise self.payload
        return LLMResponse(text=json.dumps(self.payload) if self.payload else '')

    def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


# ── Empty / trivial ────────────────────────────────────────────────────────

class TestEmptyQuery:
    def test_empty_string(self):
        r = classify_intent('')
        assert r.intent == 'general_chat'
        assert r.route == 'general-market'
        assert r.confidence == 0.0
        assert r.source == 'rules'
        assert r.entities == {}

    def test_whitespace_only(self):
        r = classify_intent('   \n\t ')
        assert r.intent == 'general_chat'
        assert r.confidence == 0.0


# ── Rule-based path (NullClient) ───────────────────────────────────────────

class TestRulePath:
    def test_null_client_uses_rules(self):
        r = classify_intent('why is BTC moving today?', client=NullClient())
        assert r.source == 'rules'
        assert r.intent in INTENTS
        assert 0.0 <= r.confidence <= 1.0

    def test_known_speaker_promotes_to_speaker_lookup(self):
        # Use a bare mention with no route keywords, so intent defaults to
        # general_chat and the speaker promotion path kicks in.
        r = classify_intent('musk', client=NullClient())
        assert r.entities.get('speaker') == 'Musk'
        assert r.intent == 'speaker_lookup'
        assert r.route == 'speaker-history'

    def test_ticker_extracted(self):
        r = classify_intent('what about KXBTC-25DEC liquidity',
                            client=NullClient())
        assert r.entities.get('ticker') == 'KXBTC-25DEC'

    def test_proper_noun_multi_token_speaker(self):
        r = classify_intent('I was reading about Gianni Infantino yesterday',
                            client=NullClient())
        assert r.entities.get('speaker')  # non-empty

    def test_route_maps_to_intent(self):
        # "portfolio" route keyword should push to portfolio_check intent.
        r = classify_intent('should I close my position?', client=NullClient())
        assert r.source == 'rules'
        # Rule-based lookup still returns some valid intent from taxonomy.
        assert r.intent in INTENTS


# ── LLM path (FakeClient) ──────────────────────────────────────────────────

class TestLLMPath:
    def test_valid_llm_response(self):
        fake = FakeClient({
            'intent': 'market_analysis',
            'route':  'price-movement',
            'confidence': 0.87,
            'entities': {
                'ticker':      'KXBTCD-25DEC',
                'speaker':     None,
                'event':       None,
                'date_range':  'today',
                'market_type': 'binary',
            },
        })
        r = classify_intent('why is BTC moving today?', client=fake)
        assert r.source == 'llm'
        assert r.intent == 'market_analysis'
        assert r.route == 'price-movement'
        assert r.confidence == pytest.approx(0.87)
        assert r.entities.get('ticker') == 'KXBTCD-25DEC'
        assert r.entities.get('date_range') == 'today'
        assert r.entities.get('market_type') == 'binary'
        assert 'speaker' not in r.entities  # null stripped
        assert r.raw is not None

    def test_llm_call_is_cached_system(self):
        fake = FakeClient({
            'intent': 'general_chat', 'route': 'general-market',
            'confidence': 0.5, 'entities': {},
        })
        classify_intent('hi', client=fake)
        assert fake.calls, 'expected complete_json to be invoked'
        assert fake.calls[0].get('cache_system') is True
        assert fake.calls[0].get('temperature') == 0.0

    def test_unknown_intent_falls_back_to_rules(self):
        fake = FakeClient({
            'intent': 'not_a_real_intent',
            'route':  'price-movement',
            'confidence': 0.9,
        })
        r = classify_intent('Powell said rates will stay', client=fake)
        assert r.source == 'rules'
        # Rules should still detect the known speaker.
        assert r.entities.get('speaker') == 'Powell'

    def test_none_payload_falls_back(self):
        fake = FakeClient(None)
        r = classify_intent('anything', client=fake)
        assert r.source == 'rules'

    def test_non_dict_payload_falls_back(self):
        fake = FakeClient(['not', 'a', 'dict'])
        r = classify_intent('anything', client=fake)
        assert r.source == 'rules'

    def test_exception_falls_back(self):
        fake = FakeClient(RuntimeError('upstream down'))
        r = classify_intent('anything', client=fake)
        assert r.source == 'rules'

    def test_invalid_route_repaired_via_intent(self):
        fake = FakeClient({
            'intent': 'speaker_lookup',
            'route':  'not-a-real-route',
            'confidence': 0.8,
            'entities': {'speaker': 'Powell'},
        })
        r = classify_intent('what did Powell say', client=fake)
        assert r.source == 'llm'
        assert r.intent == 'speaker_lookup'
        assert r.route == 'speaker-history'  # repaired via _ROUTE_TO_INTENT

    def test_confidence_clamped(self):
        fake = FakeClient({
            'intent': 'market_analysis', 'route': 'price-movement',
            'confidence': 5.0, 'entities': {},
        })
        r = classify_intent('q', client=fake)
        assert r.confidence == 1.0

    def test_confidence_non_numeric_defaults(self):
        fake = FakeClient({
            'intent': 'market_analysis', 'route': 'price-movement',
            'confidence': 'high', 'entities': {},
        })
        r = classify_intent('q', client=fake)
        assert r.confidence == 0.5

    def test_null_strings_stripped_from_entities(self):
        fake = FakeClient({
            'intent': 'market_analysis', 'route': 'price-movement',
            'confidence': 0.7,
            'entities': {
                'ticker': 'null', 'speaker': '', 'event': 'None',
                'date_range': 'this week', 'market_type': None,
            },
        })
        r = classify_intent('q', client=fake)
        assert r.entities == {'date_range': 'this week'}


# ── IntentResult dataclass ─────────────────────────────────────────────────

class TestIntentResult:
    def test_as_dict_roundtrip(self):
        r = IntentResult(
            intent='market_analysis', route='price-movement',
            confidence=0.9, source='llm', entities={'ticker': 'KXBTC'},
        )
        d = r.as_dict()
        assert d['intent'] == 'market_analysis'
        assert d['entities'] == {'ticker': 'KXBTC'}
        assert d['source'] == 'llm'
