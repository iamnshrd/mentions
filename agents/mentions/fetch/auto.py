"""Auto-fetch pipeline — fetch and cache top market data on demand or schedule."""
from __future__ import annotations

import logging

from agents.mentions.utils import now_iso, get_threshold, save_json
from agents.mentions.config import INGEST_REPORT

log = logging.getLogger('mentions')


def fetch_all(dry_run: bool = False) -> dict:
    """Fetch and persist the top active Kalshi markets.

    With *dry_run=True*, returns what would be fetched without persisting.
    """
    limit = get_threshold('top_movers_limit', 10)

    try:
        from agents.mentions.fetch.kalshi import get_top_movers
        markets = get_top_movers(limit=limit)
    except Exception as exc:
        log.warning('Kalshi top movers fetch failed: %s', exc)
        markets = []

    fetched = []
    errors = []

    for market in markets:
        ticker = market.get('ticker', '')
        if not ticker:
            continue
        if dry_run:
            fetched.append({'ticker': ticker, 'dry_run': True})
            continue
        try:
            _persist_market(market)
            fetched.append({'ticker': ticker})
        except Exception as exc:
            log.exception('Failed to persist market %s: %s', ticker, exc)
            errors.append({'ticker': ticker, 'error': str(exc)})

    report = {
        'fetched': fetched,
        'errors': errors,
        'dry_run': dry_run,
        'timestamp': now_iso(),
    }
    if not dry_run:
        save_json(INGEST_REPORT, report)
    return report


def _persist_market(market: dict) -> None:
    """Upsert a market record to the DB."""
    from agents.mentions.db import connect
    ts = now_iso()
    ticker = market.get('ticker', '')
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            '''INSERT INTO markets
               (ticker, title, category, status, yes_price, no_price,
                volume, open_interest, close_time, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET
                   yes_price=excluded.yes_price,
                   no_price=excluded.no_price,
                   volume=excluded.volume,
                   open_interest=excluded.open_interest,
                   status=excluded.status,
                   fetched_at=excluded.fetched_at''',
            (
                ticker,
                market.get('title', ''),
                market.get('category', ''),
                market.get('status', ''),
                market.get('yes_bid', market.get('yes_price', 0)),
                market.get('no_bid', market.get('no_price', 0)),
                market.get('volume', 0),
                market.get('open_interest', 0),
                market.get('close_time', ''),
                ts,
            ),
        )
