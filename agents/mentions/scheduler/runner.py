"""Autonomous scheduled runner — no user input required.

Pipeline:
1. Fetch top movers from Kalshi
2. For each market: frame → retrieve → analyze
3. Write structured JSON to dashboard/latest_analysis.json
4. Log checkpoint for each market analyzed

Designed to run via cron or OpenClaw scheduler:
    python -m mentions_core schedule mentions run
"""
from __future__ import annotations

import logging

from agents.mentions.utils import now_iso, get_threshold, save_json
from agents.mentions.config import DASHBOARD, DASHBOARD_LATEST

log = logging.getLogger('mentions')


def run_autonomous(dry_run: bool = False) -> dict:
    """Run an autonomous market scan.

    Fetches top movers, analyzes each, writes results to dashboard/.
    With *dry_run=True*, performs analysis but does not write to disk.
    """
    DASHBOARD.mkdir(parents=True, exist_ok=True)

    limit = get_threshold('top_movers_limit', 10)
    markets = _fetch_top_movers(limit)

    results = []
    errors = []

    for market in markets:
        ticker = market.get('ticker', '')
        if not ticker:
            continue
        try:
            analysis = _analyze_market(ticker, market)
            results.append(analysis)
        except Exception as exc:
            log.exception('Autonomous analysis failed for %s: %s', ticker, exc)
            errors.append({'ticker': ticker, 'error': str(exc)})

    report = {
        'scan_time': now_iso(),
        'markets_analyzed': len(results),
        'errors': errors,
        'dry_run': dry_run,
        'results': results,
    }

    if not dry_run and results:
        save_json(DASHBOARD_LATEST, report)
        log.info('Autonomous scan complete: %d markets, %d errors',
                 len(results), len(errors))

    return report


def _fetch_top_movers(limit: int) -> list[dict]:
    """Fetch top active markets. Returns [] on failure."""
    try:
        from agents.mentions.modules.kalshi_provider import get_top_movers_bundle
        return get_top_movers_bundle(limit=limit).get('markets', [])
    except Exception as exc:
        log.warning('Top movers fetch failed: %s', exc)
        return []


def _analyze_market(ticker: str, market: dict) -> dict:
    """Run the full analysis pipeline for a single market."""
    from agents.mentions.runtime.frame import select_frame
    from agents.mentions.runtime.retrieve import retrieve_bundle_for_frame
    from agents.mentions.runtime.synthesize import synthesize
    from mentions_core.base.session.checkpoint import log as log_checkpoint

    query = market.get('title', ticker)
    frame = select_frame(query)
    frame['mode'] = 'autonomous'

    # Inject known market data directly into retrieval bundle
    bundle = retrieve_bundle_for_frame(query, frame)
    if not bundle['market']['market_data']:
        bundle['market']['market_data'] = market

    synth = synthesize(query, frame, bundle)

    log_checkpoint({
        'mode': 'autonomous',
        'ticker': ticker,
        'route': frame.get('route', ''),
        'confidence': synth.get('confidence', ''),
        'verdict': synth.get('signal_assessment', {}).get('verdict', ''),
    })

    return {
        'ticker': ticker,
        'title': market.get('title', ''),
        'yes_price': market.get('yes_bid', market.get('yes_price', None)),
        'volume': market.get('volume', None),
        'route': frame.get('route', ''),
        'confidence': synth.get('confidence', ''),
        'signal': synth.get('signal_assessment', {}),
        'conclusion': synth.get('conclusion', ''),
        'recommended_action': synth.get('recommended_action', ''),
        'sources': bundle.get('sources_used', []),
        'analyzed_at': now_iso(),
    }
