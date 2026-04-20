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

# ── Thresholds (cents, days) ──────────────────────────────────────────────

_HIGH_VOL_RANGE_C = 20.0   # YES-price range ≥ this → high_vol
_LOW_VOL_RANGE_C  = 5.0    # YES-price range ≤ this → low_vol
_TREND_DELTA_C    = 15.0   # |last − first| ≥ this → trending_*
_EVENT_DAY_HOURS  = 24
_PRE_FOMC_DAYS    = 3

# Ticker prefixes whose proximity triggers the ``pre_fomc`` tag. Kept
# narrow on purpose; other central banks can be added when we have
# matching event markets.
_FOMC_PREFIXES = ('KXFED', 'FED', 'FOMC')


# ── Public API ────────────────────────────────────────────────────────────

def detect_regime(bundle: dict) -> str | None:
    """Return the single canonical regime label for *bundle*.

    *bundle* follows the retrieval-bundle convention: a dict with a
    ``market`` sub-dict carrying ``market_data`` and ``history``. All
    fields are optional — a bundle with no signal returns ``None`` so
    callers can leave the ``regime`` column NULL rather than writing
    an uninformative ``calm``.
    """
    tags = detect_regime_tags(bundle)
    return tags[0] if tags else None


def detect_regime_tags(bundle: dict) -> list[str]:
    """Return all regime tags the bundle matches, in priority order.

    Empty list when nothing fires — including for bundles with no
    price history and no calendar signal. A caller that insists on a
    default can pick ``'calm'`` themselves; we don't fabricate one.
    """
    if not isinstance(bundle, dict):
        return []
    market = bundle.get('market') or {}
    if not isinstance(market, dict):
        market = {}
    market_data = market.get('market_data') or {}
    history = market.get('history') or []

    tags: list[str] = []

    # Calendar — checked first, wins ties.
    cal = _calendar_tag(market_data)
    if cal:
        tags.append(cal)

    # Volatility and trend — from the price history.
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

    # Fallback only when we saw *any* input at all — if the bundle is
    # empty we return [] so callers leave regime NULL.
    if not tags and (market_data or prices):
        tags.append('calm')

    # Deduplicate preserving order (calendar tag can overlap).
    seen: set[str] = set()
    uniq: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


# ── Calendar helpers ──────────────────────────────────────────────────────

def _calendar_tag(market_data: dict) -> str | None:
    """Derive calendar-based regime tags from market metadata."""
    close = market_data.get('close_time') or market_data.get('expiration_time')
    ticker = (market_data.get('ticker') or '').upper()
    when = _parse_iso(close) if close else None
    if when is None:
        return None
    now = datetime.now(timezone.utc)
    delta = when - now
    # Past-close events aren't a regime signal — the market has
    # already resolved.
    if delta < timedelta(0):
        return None
    is_fomc = any(ticker.startswith(p) for p in _FOMC_PREFIXES)
    if is_fomc and delta <= timedelta(days=_PRE_FOMC_DAYS):
        return 'pre_fomc'
    if delta <= timedelta(hours=_EVENT_DAY_HOURS):
        return 'event_day'
    return None


def _parse_iso(ts: str) -> datetime | None:
    """Best-effort ISO / Kalshi-timestamp parser → aware UTC datetime."""
    if not isinstance(ts, str) or not ts.strip():
        return None
    s = ts.strip().replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Pure date fallback — treat as end-of-day UTC.
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
            try:
                dt = datetime.strptime(s, '%Y-%m-%d')
            except ValueError:
                return None
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ── Price helpers ─────────────────────────────────────────────────────────

def _extract_prices(history: list) -> list[float]:
    """Pull YES-price series from a history list; drop unparseable rows."""
    if not isinstance(history, list):
        return []
    out: list[float] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        p = entry.get('yes_price', entry.get('price'))
        if p is None:
            continue
        try:
            out.append(float(p))
        except (TypeError, ValueError):
            continue
    return out
