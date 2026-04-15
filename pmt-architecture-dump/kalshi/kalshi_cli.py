#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.parse
import urllib.request

BASE='https://api.elections.kalshi.com/trade-api/v2'


def fetch_json(path, params=None):
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'OpenClaw-Kalshi-CLI/1.0'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))


def print_market_pretty(data):
    market = data['market'] if 'market' in data else (data.get('markets') or [{}])[0]
    print(f"Ticker: {market.get('ticker')}")
    print(f"Title: {market.get('title')}")
    if market.get('yes_sub_title'):
        print(f"Yes subtitle: {market.get('yes_sub_title')}")
    if market.get('event_ticker'):
        print(f"Event: {market.get('event_ticker')}")
    print(f"Status: {market.get('status')}")
    print(f"Yes bid/ask: {market.get('yes_bid_dollars')} / {market.get('yes_ask_dollars')}")
    print(f"No bid/ask: {market.get('no_bid_dollars')} / {market.get('no_ask_dollars')}")
    print(f"Last price: {market.get('last_price_dollars')}")
    print(f"Volume: {market.get('volume_fp')} | OI: {market.get('open_interest_fp')}")
    print(f"Close: {market.get('close_time')}")
    rp = market.get('rules_primary')
    if rp:
        print(f"Rules: {rp}")


def cmd_market(args):
    try:
        data = fetch_json(f'/markets/{args.ticker}')
    except Exception:
        data = fetch_json('/markets', {'ticker': args.ticker, 'limit': 1})
    if args.pretty:
        print_market_pretty(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_event(args):
    data = fetch_json(f'/events/{args.event_ticker}')
    if args.pretty:
        event = data.get('event', {})
        markets = data.get('markets', [])
        event_ticker = event.get('event_ticker') or event.get('ticker')
        print(f"Event: {event_ticker}")
        print(f"Title: {event.get('title')}")
        sub = event.get('sub_title') or event.get('subtitle')
        if sub:
            print(f"Subtitle: {sub}")
        print(f"Category: {event.get('category')}")
        print(f"Series: {event.get('series_ticker')}")
        print(f"Markets: {len(markets)}")
        for m in markets[:25]:
            label = m.get('yes_sub_title') or m.get('title') or (m.get('custom_strike') or {}).get('Word')
            print(f"- {m.get('ticker')} :: {label} :: yes {m.get('yes_bid_dollars')}/{m.get('yes_ask_dollars')} :: no {m.get('no_bid_dollars')}/{m.get('no_ask_dollars')} :: last {m.get('last_price_dollars')} :: oi {m.get('open_interest_fp')}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_orderbook(args):
    data = fetch_json(f'/markets/{args.ticker}/orderbook')
    if args.pretty:
        ob = data.get('orderbook_fp', {})
        print(f"Ticker: {args.ticker}")
        print('YES bids:')
        for level in ob.get('yes_dollars', [])[:10]:
            print(f"  {level[0]} x {level[1]}")
        print('NO bids:')
        for level in ob.get('no_dollars', [])[:10]:
            print(f"  {level[0]} x {level[1]}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_series(args):
    data = fetch_json(f'/series/{args.series_ticker}')
    if args.pretty:
        s = data.get('series', {})
        print(f"Series: {s.get('ticker')}")
        print(f"Title: {s.get('title')}")
        print(f"Category: {s.get('category')}")
        print(f"Frequency: {s.get('frequency')}")
        tags = s.get('tags') or []
        if tags:
            print('Tags:', ', '.join(tags))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_search(args):
    params = {'limit': args.limit}
    if args.status:
        params['status'] = args.status
    if args.series_ticker:
        params['series_ticker'] = args.series_ticker
    data = fetch_json('/markets', params=params)
    markets = data.get('markets', [])
    q = args.query.lower()
    if args.series_ticker and (q == args.series_ticker.lower() or q in ('*','all')):
        if args.pretty:
            print(f"Matches: {len(markets)}")
            for m in markets[:25]:
                print(f"- {m.get('ticker')} :: {m.get('yes_sub_title') or m.get('title')} :: yes {m.get('yes_bid_dollars')}/{m.get('yes_ask_dollars')} :: event {m.get('event_ticker')}")
        else:
            print(json.dumps({'count': len(markets), 'markets': markets}, ensure_ascii=False, indent=2))
        return
    filtered = []
    for m in markets:
        hay = ' '.join([
            str(m.get('ticker', '')),
            str(m.get('title', '')),
            str(m.get('subtitle', '')),
            str(m.get('yes_sub_title', '')),
            str(m.get('no_sub_title', '')),
            str(m.get('event_ticker', '')),
            str(m.get('series_ticker', '')),
            str((m.get('custom_strike') or {}).get('Word', '')),
            str(m.get('rules_primary', '')),
        ]).lower()
        if q in hay:
            filtered.append(m)
    if args.pretty:
        print(f"Matches: {len(filtered)}")
        for m in filtered[:25]:
            print(f"- {m.get('ticker')} :: {m.get('yes_sub_title') or m.get('title')} :: yes {m.get('yes_bid_dollars')}/{m.get('yes_ask_dollars')} :: event {m.get('event_ticker')}")
    else:
        print(json.dumps({'count': len(filtered), 'markets': filtered}, ensure_ascii=False, indent=2))


def build_parser():
    p = argparse.ArgumentParser(description='Read-only Kalshi public market data CLI')
    sub = p.add_subparsers(dest='command', required=True)

    p_market = sub.add_parser('market', help='Get market details by ticker')
    p_market.add_argument('ticker')
    p_market.add_argument('--pretty', action='store_true')
    p_market.set_defaults(func=cmd_market)

    p_event = sub.add_parser('event', help='Get event details by event ticker')
    p_event.add_argument('event_ticker')
    p_event.add_argument('--pretty', action='store_true')
    p_event.set_defaults(func=cmd_event)

    p_orderbook = sub.add_parser('orderbook', help='Get market orderbook by ticker')
    p_orderbook.add_argument('ticker')
    p_orderbook.add_argument('--pretty', action='store_true')
    p_orderbook.set_defaults(func=cmd_orderbook)

    p_series = sub.add_parser('series', help='Get series details by series ticker')
    p_series.add_argument('series_ticker')
    p_series.add_argument('--pretty', action='store_true')
    p_series.set_defaults(func=cmd_series)

    p_search = sub.add_parser('search', help='Search public markets by substring over fetched results')
    p_search.add_argument('query')
    p_search.add_argument('--limit', type=int, default=1000)
    p_search.add_argument('--status', default=None)
    p_search.add_argument('--series-ticker', default=None)
    p_search.add_argument('--pretty', action='store_true')
    p_search.set_defaults(func=cmd_search)

    return p


if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)
