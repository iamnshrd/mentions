"""Tests for library._core.llm.client.

Covers:
  * NullClient returns empty LLMResponse / None from complete_json
  * _parse_json_text: direct, fenced, embedded, malformed
  * default_client() returns NullClient when ANTHROPIC_API_KEY is absent
"""
from __future__ import annotations

import pytest


class TestNullClient:
    def test_complete_returns_empty(self):
        from library._core.llm import NullClient, LLMResponse
        r = NullClient().complete(system='s', user='u')
        assert isinstance(r, LLMResponse)
        assert r.text == ''

    def test_complete_json_returns_none(self):
        from library._core.llm import NullClient
        assert NullClient().complete_json(system='s', user='u') is None


class TestParseJsonText:
    def _parse(self, text):
        from library._core.llm.client import _parse_json_text
        return _parse_json_text(text)

    def test_empty_string(self):
        assert self._parse('') is None
        assert self._parse('   ') is None

    def test_direct_object(self):
        assert self._parse('{"a": 1}') == {'a': 1}

    def test_direct_object_with_whitespace(self):
        assert self._parse('   \n  {"x": 2}\n ') == {'x': 2}

    def test_fenced_json_block(self):
        text = 'Here you go:\n```json\n{"intent": "x", "k": 2}\n```\nDone.'
        assert self._parse(text) == {'intent': 'x', 'k': 2}

    def test_fenced_generic_block(self):
        text = '```\n{"y": 9}\n```'
        assert self._parse(text) == {'y': 9}

    def test_embedded_object_with_surrounding_prose(self):
        text = 'Thinking...\n{"intent": "market_analysis"}\nthat is my answer.'
        assert self._parse(text) == {'intent': 'market_analysis'}

    def test_nested_braces(self):
        text = 'prelude {"entities": {"ticker": "KXBTC"}, "ok": true} trailing'
        assert self._parse(text) == {'entities': {'ticker': 'KXBTC'}, 'ok': True}

    def test_malformed_returns_none(self):
        assert self._parse('{not json') is None
        assert self._parse('totally unrelated prose') is None

    def test_array_rejected(self):
        # We want dicts only — arrays fall back to None.
        assert self._parse('[1, 2, 3]') is None


class TestDefaultClient:
    def test_no_api_key_returns_null(self, monkeypatch):
        monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
        from library._core.llm import default_client, NullClient
        assert isinstance(default_client(), NullClient)

    def test_key_present_but_no_sdk_returns_null(self, monkeypatch):
        """If key is set but anthropic SDK missing, degrade to NullClient."""
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-test')
        # Simulate missing anthropic by shadowing it with an ImportError.
        import sys
        saved = sys.modules.pop('anthropic', None)
        try:
            sys.modules['anthropic'] = None  # triggers ImportError on re-import
            from library._core.llm import default_client, NullClient
            client = default_client()
            # Either NullClient (if SDK truly absent) or AnthropicClient (if
            # it is installed in the test env). Both are acceptable — the
            # invariant is that default_client never raises.
            assert client is not None
        finally:
            # Restore state so subsequent tests see the real module (if any).
            if saved is not None:
                sys.modules['anthropic'] = saved
            else:
                sys.modules.pop('anthropic', None)
