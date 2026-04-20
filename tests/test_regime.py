"""Tests for market-regime auto-classification (v0.14.5)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mentions_domain.analysis.regime import (
    detect_regime, detect_regime_tags, _parse_iso, _extract_prices,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _iso_in(hours: float = 0, days: float = 0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(hours=hours, days=days)
    return dt.isoformat()


def _bundle(*, ticker='', close=None, prices=()) -> dict:
    hist = [{'yes_price': p} for p in prices]
    md: dict = {}
    if ticker:
        md['ticker'] = ticker
    if close is not None:
        md['close_time'] = close
    return {'market': {'market_data': md, 'history': hist}}


# ── _parse_iso ────────────────────────────────────────────────────────────

class TestParseIso:
    def test_iso_with_z_suffix(self):
        dt = _parse_iso('2025-03-15T10:00:00Z')
        assert dt is not None
        assert dt.tzinfo is not None

    def test_iso_with_offset(self):
        dt = _parse_iso('2025-03-15T10:00:00+00:00')
        assert dt is not None

    def test_naive_iso_treated_utc(self):
        dt = _parse_iso('2025-03-15T10:00:00')
        assert dt is not None and dt.tzinfo is timezone.utc

    def test_date_only(self):
        dt = _parse_iso('2025-03-15')
        assert dt is not None

    def test_garbage(self):
        assert _parse_iso('') is None
        assert _parse_iso('not-a-date') is None
        assert _parse_iso(None) is None  # type: ignore[arg-type]


# ── _extract_prices ───────────────────────────────────────────────────────

class TestExtractPrices:
    def test_yes_price_key(self):
        assert _extract_prices([{'yes_price': 60}, {'yes_price': 65}]) == [60.0, 65.0]

    def test_fallback_price_key(self):
        assert _extract_prices([{'price': 50}]) == [50.0]

    def test_skips_unparseable(self):
        assert _extract_prices([
            {'yes_price': 60},
            {'yes_price': 'oops'},
            {'other': 99},
            None,
        ]) == [60.0]

    def test_empty(self):
        assert _extract_prices([]) == []
        assert _extract_prices('nonsense') == []  # type: ignore[arg-type]


# ── Calendar regimes ──────────────────────────────────────────────────────

class TestCalendarRegimes:
    def test_pre_fomc_within_three_days(self):
        b = _bundle(ticker='KXFED-25MAR-T25', close=_iso_in(days=2))
        assert detect_regime(b) == 'pre_fomc'

    def test_pre_fomc_prefix_variants(self):
        for prefix in ('KXFED-25MAR', 'FED-25MAR', 'FOMC-25MAR'):
            b = _bundle(ticker=f'{prefix}-T25', close=_iso_in(days=1))
            assert detect_regime(b) == 'pre_fomc', prefix

    def test_fomc_far_future_is_not_pre_fomc(self):
        b = _bundle(ticker='KXFED-25MAR-T25', close=_iso_in(days=30))
        # Could still be calm — must not be 'pre_fomc'.
        assert detect_regime(b) != 'pre_fomc'

    def test_event_day_non_fomc(self):
        b = _bundle(ticker='KXNFL-SB', close=_iso_in(hours=6))
        assert detect_regime(b) == 'event_day'

    def test_past_close_is_not_calendar(self):
        b = _bundle(ticker='KXFED-25MAR-T25', close=_iso_in(hours=-5))
        assert detect_regime(b) != 'pre_fomc'
        assert detect_regime(b) != 'event_day'

    def test_missing_close_time(self):
        b = _bundle(ticker='KXFED-25MAR-T25')
        # No close time → no calendar tag. With market_data present
        # we still fall into the calm fallback.
        assert detect_regime(b) == 'calm'


# ── Volatility regimes ────────────────────────────────────────────────────

class TestVolatility:
    def test_high_vol(self):
        b = _bundle(prices=[40, 70, 35, 60])
        assert detect_regime(b) == 'high_vol'

    def test_low_vol(self):
        b = _bundle(prices=[50, 51, 52, 51, 50])
        assert 'low_vol' in detect_regime_tags(b)

    def test_moderate_is_calm(self):
        # Range 8 cents — between low and high thresholds, no trend.
        b = _bundle(prices=[50, 55, 58, 53])
        assert detect_regime(b) == 'calm'


# ── Trend regimes ─────────────────────────────────────────────────────────

class TestTrend:
    def test_trending_up(self):
        b = _bundle(prices=[40, 45, 50, 58])
        tags = detect_regime_tags(b)
        assert 'trending_up' in tags

    def test_trending_down(self):
        b = _bundle(prices=[70, 60, 55, 50])
        tags = detect_regime_tags(b)
        assert 'trending_down' in tags

    def test_no_trend_flat(self):
        b = _bundle(prices=[50, 50, 50])
        tags = detect_regime_tags(b)
        assert 'trending_up' not in tags
        assert 'trending_down' not in tags


# ── Priority & combinations ───────────────────────────────────────────────

class TestPriority:
    def test_calendar_beats_price(self):
        # High vol *and* pre-FOMC — calendar wins the single-label call.
        b = _bundle(
            ticker='KXFED-25MAR-T25',
            close=_iso_in(days=1),
            prices=[40, 70, 35, 60],
        )
        assert detect_regime(b) == 'pre_fomc'
        # But tags expose both.
        tags = detect_regime_tags(b)
        assert tags[0] == 'pre_fomc'
        assert 'high_vol' in tags

    def test_vol_and_trend_coexist(self):
        b = _bundle(prices=[40, 65, 50, 70])  # range 30, delta +30
        tags = detect_regime_tags(b)
        assert 'high_vol' in tags
        assert 'trending_up' in tags


# ── Empty / degenerate bundles ────────────────────────────────────────────

class TestEmpty:
    def test_empty_bundle_is_none(self):
        assert detect_regime({}) is None
        assert detect_regime({'market': {}}) is None
        assert detect_regime_tags({}) == []

    def test_non_dict_bundle(self):
        assert detect_regime(None) is None  # type: ignore[arg-type]
        assert detect_regime('oops') is None  # type: ignore[arg-type]

    def test_single_price_no_regime(self):
        # Need at least two points for vol/trend.
        b = _bundle(prices=[50])
        # Falls into calm fallback because market_data-empty + prices
        # exist → triggers calm.
        assert detect_regime(b) == 'calm'

    def test_market_data_without_prices_is_calm(self):
        b = {'market': {'market_data': {'ticker': 'X'}, 'history': []}}
        assert detect_regime(b) == 'calm'
