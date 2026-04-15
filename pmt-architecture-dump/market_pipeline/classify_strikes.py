#!/usr/bin/env python3
import argparse, json, requests
from pathlib import Path

API='https://api.elections.kalshi.com/trade-api/v2/events/{ticker}'
OVERRIDES = Path('/root/.openclaw/workspace/market_pipeline/overrides.json')

IRAN_CORE = {'iran', 'nuclear', 'uranium', 'israel', 'israeli', 'negotiate', 'ceasefire'}
IRAN_SELECTIVE = {'oil', 'nato', 'peace in the middle east', 'peace', 'deal', 'war'}
IRAN_PASSIVE_NO = {'supreme leader', 'ayatollah', 'khamenei', 'epic fury', 'midnight hammer'}
NO_TOUCH_HINTS = {'biden', 'barack hussein obama', 'crypto', 'bitcoin', 'venezuela', 'rescue', 'withdraw', 'obliterate'}
GENERIC_LIVE_QA_CORE = {'economy', 'inflation', 'border', 'immigration', 'china', 'tax', 'tariff', 'jobs', 'trade', 'russia', 'ukraine', 'iran', 'israel'}
GENERIC_LIVE_QA_SELECTIVE = {'oil', 'nato', 'deal', 'peace', 'ceasefire', 'putin', 'xi', 'federal reserve', 'fed'}
GENERIC_LIVE_QA_PASSIVE_NO = {'bitcoin', 'crypto', 'barack hussein obama', 'hunter biden', 'epstein', 'qanon'}


def fetch_event(ticker):
    return requests.get(API.format(ticker=ticker), timeout=20).json()


def midpoint(m):
    yb, ya, last = m.get('yes_bid_dollars'), m.get('yes_ask_dollars'), m.get('last_price_dollars')
    if isinstance(yb, (int,float)) and isinstance(ya, (int,float)):
        return round((yb+ya)/2, 3)
    return last


def classify_iran_press(label):
    parts = split_variants(label)
    if any_match(parts, IRAN_CORE):
        return 'core yes', 'high', 'direct Iran-core match'
    if any_match(parts, IRAN_SELECTIVE):
        return 'selective', 'high', 'direct adjacent Iran-theme match'
    if any_match(parts, IRAN_PASSIVE_NO):
        return 'passive no', 'high', 'direct narrow/detail-heavy Iran-path match'
    if any_match(parts, NO_TOUCH_HINTS):
        return 'no-touch', 'high', 'explicit no-touch hint match'
    # heuristic fallbacks
    if any_contains(parts, ['iran', 'nuclear', 'uranium', 'israel', 'negotia', 'ceasefire']):
        return 'core yes', 'medium', 'keyword overlap with Iran direct core'
    if any_contains(parts, ['peace', 'war', 'oil', 'nato', 'deal', 'settle']):
        return 'selective', 'medium', 'keyword overlap with broader geopolitical / negotiation branch'
    if any_contains(parts, ['leader', 'ayatollah', 'khamenei', 'hammer', 'fury']):
        return 'passive no', 'medium', 'keyword overlap with narrow branded / detail-heavy branch'
    return 'no-touch', 'low', 'no strong Iran-press rule match'


def normalize_label(label):
    l = label.lower().strip()
    replacements = [
        ('(5+ times)', ''),
        ('(3+ times)', ''),
        ('(2+ times)', ''),
        ('(1+ times)', ''),
        (' / ', ' | '),
        ('/', ' | '),
        ('-', ' '),
        ('(', ' '),
        (')', ' '),
        (',', ' '),
    ]
    for old, new in replacements:
        l = l.replace(old, new)
    return ' '.join(l.split())


def split_variants(label):
    l = normalize_label(label)
    parts = [p.strip() for p in l.split('|') if p.strip()]
    return parts or [l]


def any_match(parts, candidates):
    return any(p in candidates for p in parts)


def any_contains(parts, needles):
    return any(any(n in p for n in needles) for p in parts)


def classify_generic_live_qa(label):
    parts = split_variants(label)
    if any_match(parts, GENERIC_LIVE_QA_CORE):
        return 'core yes', 'high', 'direct generic live-Q&A core match'
    if any_match(parts, GENERIC_LIVE_QA_SELECTIVE):
        return 'selective', 'medium', 'direct adjacent-theme match'
    if any_match(parts, GENERIC_LIVE_QA_PASSIVE_NO) or any_match(parts, NO_TOUCH_HINTS):
        return 'passive no', 'high', 'direct narrow/detail-heavy or obvious off-theme match'
    if any_contains(parts, ['economy','inflation','border','immigration','china','tax','tariff','jobs','trade','russia','ukraine','iran','israel']):
        return 'core yes', 'medium', 'keyword overlap with direct live-Q&A macro/policy core'
    if any_contains(parts, ['oil','nato','deal','peace','ceasefire','putin','xi','fed']):
        return 'selective', 'medium', 'keyword overlap with adjacent Q&A expansion themes'
    if any_contains(parts, ['bitcoin','crypto','epstein','qanon','hunter biden','barack hussein obama']):
        return 'passive no', 'medium', 'keyword overlap with narrow or off-theme crowd-overpay names'
    return 'no-touch', 'low', 'no strong preset rule match'


def fv_generic_live_qa(bucket):
    return {
        'core yes': 'TBD-high',
        'selective': 'TBD-mid',
        'passive no': 'TBD-low',
        'no-touch': 'TBD'
    }[bucket]


def fv_iran_press(label, bucket):
    parts = split_variants(label)
    mapping = {
        'iran': '0.78-0.88',
        'nuclear': '0.62-0.74',
        'uranium': '0.55-0.68',
        'israel': '0.58-0.70',
        'israeli': '0.50-0.64',
        'negotiate': '0.52-0.66',
        'negotiated': '0.52-0.66',
        'negotiation': '0.52-0.66',
        'ceasefire': '0.44-0.58',
        'oil': '0.25-0.38',
        'nato': '0.18-0.30',
        'peace in the middle east': '0.28-0.42',
        'peace': '0.20-0.34',
        'deal': '0.24-0.40',
        'settle': '0.24-0.40',
        'war': '0.22-0.36',
        'supreme leader': '0.12-0.22',
        'ayatollah': '0.10-0.20',
        'khamenei': '0.08-0.16',
        'epic fury': '0.03-0.08',
        'midnight hammer': '0.03-0.08',
    }
    for p in parts:
        if p in mapping:
            return mapping[p]
    return {'core yes': 'TBD-high', 'selective': 'TBD-mid', 'passive no': 'TBD-low', 'no-touch': 'TBD'}[bucket]


def action_from_bucket(bucket):
    return {
        'core yes': 'buy / core yes',
        'selective': 'selective buy',
        'passive no': 'passive no',
        'no-touch': 'no-touch',
    }[bucket]


def load_overrides():
    if not OVERRIDES.exists():
        return {'ticker_overrides': {}, 'label_overrides': {}, 'preset_overrides': {}}
    return json.loads(OVERRIDES.read_text())


def apply_overrides(row, ticker, preset, overrides):
    ticker_map = overrides.get('ticker_overrides', {}).get(ticker, {})
    label_map = overrides.get('label_overrides', {}).get(row['label'], {})
    preset_map = overrides.get('preset_overrides', {}).get(preset, {}).get(row['label'], {})
    merged = {}
    merged.update(preset_map)
    merged.update(label_map)
    merged.update(ticker_map.get(row['label'], {}))
    row.update(merged)
    return row


def classify_event(ticker, preset):
    data = fetch_event(ticker)
    markets = data.get('markets', [])
    overrides = load_overrides()
    out = []
    for m in markets:
        label = m.get('yes_sub_title') or m.get('title') or ''
        if not label:
            continue
        if preset == 'iran-press':
            bucket, confidence, reason = classify_iran_press(label)
            fv = fv_iran_press(label, bucket)
        elif preset in {'trump-live-qa', 'briefing-style'}:
            bucket, confidence, reason = classify_generic_live_qa(label)
            fv = fv_generic_live_qa(bucket)
        else:
            bucket, confidence, reason = 'no-touch', 'low', 'unknown preset'
            fv = 'TBD'
        row = {
            'ticker': m.get('ticker'),
            'label': label,
            'bucket': bucket,
            'confidence': confidence,
            'reason': reason,
            'action': action_from_bucket(bucket),
            'current_price': midpoint(m),
            'fv': fv,
        }
        out.append(apply_overrides(row, ticker, preset, overrides))
    # sort by bucket then label
    order = {'core yes': 0, 'selective': 1, 'passive no': 2, 'no-touch': 3}
    out.sort(key=lambda x: (order.get(x['bucket'], 9), x['label'].lower()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ticker')
    ap.add_argument('--preset', default='iran-press')
    args = ap.parse_args()
    print(json.dumps(classify_event(args.ticker, args.preset), indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
