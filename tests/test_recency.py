"""Tests for event-date recency boost (v0.14.7 — T4)."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from library._core.retrieve.recency import (
    DEFAULT_HALF_LIFE_DAYS, RECENCY_FLOOR,
    _parse_event_date, apply_recency, recency_weight,
)
from library._core.retrieve.hybrid import RetrievalHit


def _hit(event_date='', chunk_id=1):
    h = RetrievalHit(chunk_id=chunk_id, document_id=1, text='', speaker='',
                     section='', event='', event_date=event_date,
                     token_count=0)
    h.score_final = 1.0
    return h


# ── _parse_event_date ─────────────────────────────────────────────────────

class TestParse:
    def test_iso_with_z(self):
        assert _parse_event_date('2024-01-01T10:00:00Z') is not None

    def test_iso_naive(self):
        dt = _parse_event_date('2024-01-01T10:00:00')
        assert dt is not None and dt.tzinfo is timezone.utc

    def test_date_only(self):
        assert _parse_event_date('2024-01-01') is not None

    def test_garbage(self):
        assert _parse_event_date('') is None
        assert _parse_event_date(None) is None
        assert _parse_event_date('wat') is None


# ── recency_weight math ───────────────────────────────────────────────────

class TestWeight:
    def test_today_is_one(self):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        assert recency_weight('2025-01-01', now=now) == 1.0

    def test_one_half_life_is_half(self):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        past = (now - timedelta(days=365)).date().isoformat()
        w = recency_weight(past, now=now, half_life_days=365.0)
        assert w == pytest.approx(0.5, abs=1e-3)

    def test_two_half_lives_is_quarter(self):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        past = (now - timedelta(days=730)).date().isoformat()
        w = recency_weight(past, now=now, half_life_days=365.0)
        assert w == pytest.approx(0.25, abs=1e-3)

    def test_respects_floor(self):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        past = (now - timedelta(days=365 * 20)).date().isoformat()
        w = recency_weight(past, now=now, half_life_days=365.0)
        assert w == RECENCY_FLOOR

    def test_missing_date_is_neutral(self):
        assert recency_weight('') == 1.0
        assert recency_weight(None) == 1.0
        assert recency_weight('garbage') == 1.0

    def test_future_date_is_neutral(self):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        future = (now + timedelta(days=30)).date().isoformat()
        assert recency_weight(future, now=now) == 1.0

    def test_half_life_none_disables(self):
        assert recency_weight('1900-01-01', half_life_days=None) == 1.0

    def test_half_life_zero_disables(self):
        assert recency_weight('1900-01-01', half_life_days=0) == 1.0


# ── apply_recency on hit list ─────────────────────────────────────────────

class TestApply:
    def test_attaches_weight_and_scales_score(self):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        h = _hit(event_date=(now - timedelta(days=365)).date().isoformat())
        h.score_final = 1.0
        apply_recency([h], half_life_days=365.0, now=now)
        assert h.score_recency == pytest.approx(0.5, abs=1e-3)
        assert h.score_final == pytest.approx(0.5, abs=1e-3)

    def test_disabled_leaves_scores_untouched(self):
        h = _hit(event_date='1900-01-01')
        h.score_final = 1.0
        apply_recency([h], half_life_days=None)
        assert h.score_recency == 1.0
        assert h.score_final == 1.0

    def test_floor_applied(self):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        h = _hit(event_date='1900-01-01')
        h.score_final = 2.0
        apply_recency([h], half_life_days=365.0, now=now)
        # Floor is 0.1 → score drops to 0.2, not near zero.
        assert h.score_recency == RECENCY_FLOOR
        assert h.score_final == pytest.approx(2.0 * RECENCY_FLOOR)

    def test_preserves_ranking_between_same_date_hits(self):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        same = '2024-01-01'
        h1, h2 = _hit(event_date=same, chunk_id=1), _hit(event_date=same, chunk_id=2)
        h1.score_final, h2.score_final = 2.0, 1.0
        apply_recency([h1, h2], half_life_days=365.0, now=now)
        # Same recency multiplier → relative order preserved.
        assert h1.score_final > h2.score_final


# ── RetrievalHit shape ────────────────────────────────────────────────────

class TestHitShape:
    def test_score_recency_default(self):
        h = _hit()
        assert h.score_recency == 1.0
