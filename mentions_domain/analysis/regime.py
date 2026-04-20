"""Market-regime auto-classification.

Regime-conditioned posteriors (v0.14.4) let us slice heuristic and
speaker track records by context — *"does this heuristic work in high
volatility?"*, *"is this speaker reliable pre-FOMC?"*. But a posterior
is only useful if callers actually *tag* their ``record_application``
calls with a regime label. Asking humans to hand-tag every write is a
reliability footgun: either the tagging is inconsistent across code
paths, or it's forgotten entirely and the regime column is always
``NULL``.

This module closes the loop. Given a retrieval bundle (the same dict
the synthesis path already sees), :func:`detect_regime` returns a
canonical regime string the caller can pass straight through. The
classifier is rule-based and cheap:

* **Calendar-based tags** win first — ``pre_fomc`` (FOMC-type ticker
  closing within ~3 days), ``event_day`` (any event closing within
  24 h). A hand-tagged calendar always beats price noise.
* **Volatility** from the price history — ``high_vol`` when the range
  of observed YES prices spans ≥ 20 cents, ``low_vol`` when it spans
  ≤ 5 cents. The thresholds are coarse on purpose so the label is
  stable under one-tick noise.
* **Trend** — ``trending_up`` / ``trending_down`` when the final
  price differs from the first by ≥ 15 cents. Checked after
  volatility so a price that *moved* a lot but *finished* far from
  where it started gets the trend label (more informative for
  decision review than the raw range).
* Fallback: ``calm``.

Priority is deliberate: calendar > vol > trend > calm. The single
label is what :func:`record_application` needs; callers wanting the
full multi-label set can use :func:`detect_regime_tags`.

Kept pure and synchronous: no I/O, no LLM, no database. The only
inputs are fields the retrieval bundle already carries, so this is
safe to call on every synthesis pass.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

log = logging.getLogger('mentions')

_HIGH_VOL_RANGE_C = 20.0
_LOW_VOL_RANGE_C = 5.0
_TREND_DELTA_C = 15.0
_EVENT_DAY_HOURS = 24
_PRE_FOMC_DAYS = 3

_FOMC_PREFIXES = ('KXFED', 'FED', 'FOMC')


def detect_regime(bundle: dict) -> str | None:
    """Return the single canonical regime label for *bundle*."""
    tags = detect_regime_tags(bundle)
    return tags[0] if tags else None


def detect_regime_tags(bundle: dict) -> list[str]:
    """Return all regime tags the bundle matches, in priority order."""
    if not isinstance(bundle, dict):
        return []
    market = bundle.get('market') or {}
    if not isinstance(market, dict):
        market = {}
    market_data = market.get('market_data') or {}
    history = market.get('history') or []

    tags: list[str] = []

    cal = _calendar_tag(market_data)
    if cal:
        tags.append(cal)

    prices = _extract_prices(history)
    if len(prices) >= 2:
        rng = max(prices) - min(prices)
        delta = prices[-1] - prices[0]
        if rng >= _HIGH_VOL_RANGE_C:
            tags.append('high_vol')
        elif rng <= _LOW_VOL_RANGE_C:
            tags.append('low_vol')
        if delta >= _TREND_DELTA_C:
            tags.append('trending_up')
        elif delta <= -_TREND_DELTA_C:
            tags.append('trending_down')

    if not tags and (market_data or prices):
        tags.append('calm')

    seen: set[str] = set()
    uniq: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            uniq.append(tag)
    return uniq


def _calendar_tag(market_data: dict) -> str | None:
    """Derive calendar-based regime tags from market metadata."""
    close = market_data.get('close_time') or market_data.get('expiration_time')
    ticker = (market_data.get('ticker') or '').upper()
    when = _parse_iso(close) if close else None
    if when is None:
        return None
    now = datetime.now(timezone.utc)
    delta = when - now
    if delta < timedelta(0):
        return None
    is_fomc = any(ticker.startswith(prefix) for prefix in _FOMC_PREFIXES)
    if is_fomc and delta <= timedelta(days=_PRE_FOMC_DAYS):
        return 'pre_fomc'
    if delta <= timedelta(hours=_EVENT_DAY_HOURS):
        return 'event_day'
    return None


def _parse_iso(ts: str) -> datetime | None:
    """Best-effort ISO / Kalshi-timestamp parser -> aware UTC datetime."""
    if not isinstance(ts, str) or not ts.strip():
        return None
    value = ts.strip().replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            try:
                dt = datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                return None
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _extract_prices(history: list) -> list[float]:
    """Pull YES-price series from a history list; drop unparseable rows."""
    if not isinstance(history, list):
        return []
    out: list[float] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        price = entry.get('yes_price', entry.get('price'))
        if price is None:
            continue
        try:
            out.append(float(price))
        except (TypeError, ValueError):
            continue
    return out
