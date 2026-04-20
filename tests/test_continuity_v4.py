"""Tests for continuity v4 schema.

Covers:
  * Default shape includes v4 buckets
  * Migration path v1 → v4 and v3 → v4
  * update(intent=..., speaker=..., ticker=...) populates the new
    buckets with bump semantics
  * _build_summary_dict surfaces top_intents / top_speakers /
    top_tickers
  * Empty intent/speaker/ticker values are no-ops
  * update_session carries intent + entity fields onto disk
"""
from __future__ import annotations

import pytest

from mentions_core.base.session import continuity as C
from mentions_core.base.state_store import KEY_CONTINUITY, KEY_SESSION_STATE


_counter = {'n': 0}


@pytest.fixture
def store(tmp_workspace):
    """A fresh FileSystemStore bound to the per-test tmp_workspace path.

    We construct directly (rather than via get_default_store()) to
    defeat any module-level caching.
    """
    from mentions_core.base.adapters.fs_store import FileSystemStore
    return FileSystemStore(tmp_workspace)


@pytest.fixture
def uid():
    """Unique user_id per test so state cannot leak between tests."""
    _counter['n'] += 1
    return f'u_{_counter["n"]}'


class TestSchema:
    def test_defaults_include_v4_buckets(self, store, uid):
        data = C.load(user_id=uid, store=store)
        assert data['version'] == 4
        for bucket in ('intents', 'speakers', 'tickers',
                       'recurring_themes', 'user_patterns',
                       'macro_loops', 'crypto_loops'):
            assert bucket in data
            assert data[bucket] == []

    def test_migrate_v1_to_v4(self, store, uid):
        store.put_json(uid, KEY_CONTINUITY, {
            'version': 1,
            'recurring_themes': [], 'user_patterns': [],
            'open_loops': [], 'resolved_loops': [],
        })
        data = C.load(user_id=uid, store=store)
        assert data['version'] == 4
        assert data['macro_loops'] == []
        assert data['intents'] == []
        assert data['speakers'] == []
        assert data['tickers'] == []

    def test_migrate_v3_to_v4_preserves_v3_data(self, store, uid):
        store.put_json(uid, KEY_CONTINUITY, {
            'version': 3,
            'recurring_themes': [{'name': 'crypto', 'count': 3, 'salience': 5,
                                  'first_seen': 't', 'last_seen': 't'}],
            'user_patterns': [], 'open_loops': [], 'resolved_loops': [],
            'macro_loops': [], 'crypto_loops': [],
        })
        data = C.load(user_id=uid, store=store)
        assert data['version'] == 4
        assert data['recurring_themes'][0]['name'] == 'crypto'
        assert data['intents'] == []


class TestUpdateV4:
    def test_intent_bucket_bump(self, store, uid):
        C.update('q1', intent='market_analysis', user_id=uid, store=store)
        C.update('q2', intent='market_analysis', user_id=uid, store=store)
        C.update('q3', intent='speaker_lookup', user_id=uid, store=store)
        data = C.load(user_id=uid, store=store)
        names = {i['name']: i for i in data['intents']}
        assert names['market_analysis']['count'] == 2
        assert names['speaker_lookup']['count'] == 1

    def test_speaker_bucket_bump(self, store, uid):
        C.update('q', speaker='Powell', user_id=uid, store=store)
        C.update('q', speaker='Powell', user_id=uid, store=store)
        C.update('q', speaker='Musk', user_id=uid, store=store)
        data = C.load(user_id=uid, store=store)
        names = {i['name']: i['count'] for i in data['speakers']}
        assert names == {'Powell': 2, 'Musk': 1}

    def test_ticker_bucket_bump(self, store, uid):
        C.update('q', ticker='KXBTCD-25DEC', user_id=uid, store=store)
        C.update('q', ticker='KXBTCD-25DEC', user_id=uid, store=store)
        data = C.load(user_id=uid, store=store)
        assert data['tickers'][0]['name'] == 'KXBTCD-25DEC'
        assert data['tickers'][0]['count'] == 2

    def test_empty_values_are_noop(self, store, uid):
        C.update('q', intent='', speaker='', ticker='',
                 user_id=uid, store=store)
        data = C.load(user_id=uid, store=store)
        assert data['intents'] == []
        assert data['speakers'] == []
        assert data['tickers'] == []

    def test_mixed_bump_one_call(self, store, uid):
        C.update('why is BTC moving?', route='price-movement',
                 category='crypto', intent='market_analysis',
                 ticker='KXBTCD-25DEC', user_id=uid, store=store)
        data = C.load(user_id=uid, store=store)
        assert data['recurring_themes'][0]['name'] == 'crypto'
        assert data['user_patterns'][0]['name'] == 'price-movement'
        assert data['intents'][0]['name'] == 'market_analysis'
        assert data['tickers'][0]['name'] == 'KXBTCD-25DEC'
        assert data['speakers'] == []  # not passed


class TestSummary:
    def test_summary_includes_v4_slices(self, store, uid):
        C.update('q', intent='market_analysis', speaker='Powell',
                 ticker='KXBTCD-25DEC', user_id=uid, store=store)
        summary = C.summarize(user_id=uid, store=store)
        assert summary['top_intents'][0]['name'] == 'market_analysis'
        assert summary['top_speakers'][0]['name'] == 'Powell'
        assert summary['top_tickers'][0]['name'] == 'KXBTCD-25DEC'

    def test_read_falls_back_to_fresh_summary(self, store, uid):
        C.update('q', intent='speaker_lookup', speaker='Musk',
                 user_id=uid, store=store)
        r = C.read(user_id=uid, store=store)
        assert 'top_intents' in r
        assert r['top_speakers'][0]['name'] == 'Musk'


class TestSessionStateV4:
    def test_update_session_carries_intent_fields(self, store, uid):
        from mentions_core.base.session.state import update_session
        update_session(
            'why is BTC moving?',
            route='price-movement', category='crypto',
            mode='deep', confidence='medium',
            intent='market_analysis', intent_confidence=0.82,
            intent_source='llm',
            speaker='', ticker='KXBTCD-25DEC',
            user_id=uid, store=store,
        )
        data = store.get_json(uid, KEY_SESSION_STATE)
        assert data['last_intent'] == 'market_analysis'
        assert data['last_intent_confidence'] == pytest.approx(0.82)
        assert data['last_intent_source'] == 'llm'
        assert data['last_ticker'] == 'KXBTCD-25DEC'
        assert data['last_speaker'] == ''
