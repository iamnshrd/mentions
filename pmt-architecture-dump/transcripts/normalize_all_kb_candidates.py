#!/usr/bin/env python3
import json
import re
from pathlib import Path
from collections import defaultdict

BASE = Path('/root/.openclaw/workspace/transcripts/kb_candidates')
OUT = Path('/root/.openclaw/workspace/transcripts/kb_normalized')
OUT.mkdir(parents=True, exist_ok=True)

# Family-based practical dedupe. We intentionally collapse broad idea clusters
# into canonical reusable rows with evidence attached.
SCHEMES = {
    'market_archetypes': [
        ('recurring-announcer-mentions', ['announcer', 'fourth quarter', 'broadcast', 'booth', 'prime time', 'espn', 'network']),
        ('trump-live-qna-mentions', ['trump', 'q&a', 'prepared remarks', 'open press', 'closed press', 'east room']),
        ('rare-speaker-or-thin-history-mentions', ['jd vance', 'out of my element', 'thin', 'rare', 'do not get them that often', 'sparse']),
        ('name-linked-policy-announcement-mentions', ['eli lilly', 'novo', 'drug', 'counterparty', 'named', 'company']),
        ('performer-field-markets', ['performer', 'field', 'lady gaga', 'travis scott', 'cardi', 'ricky martin']),
        ('high-probability-bond-like-markets', ['bond', '99', '95', 'one cent', 'cash out', 'clarification']),
        ('manual-orderbook-execution-markets', ['orderbook', 'rfq', 'quote', 'maker', 'queue', 'review first']),
        ('open-vs-closed-press-misread-mentions', ['open press', 'closed press', 'setup', 'roll call']),
    ],
    'event_formats': [
        ('sports-broadcast-live', ['announcer', 'broadcast', 'game', 'fourth quarter', 'replay']),
        ('trump-live-event-with-qna-risk', ['trump', 'q&a', 'prepared remarks', 'questions']),
        ('trump-announcement-with-setup-fud', ['open press', 'closed press', 'setup', 'announcement']),
        ('rare-political-speech-format', ['jd vance', 'rare', 'thin history', 'out of my element']),
        ('named-policy-announcement', ['eli lilly', 'novo', 'drug', 'announcement', 'company']),
        ('culture-live-performer-event', ['performer', 'halftime', 'super bowl', 'show', 'stage']),
        ('manual-quoting-market', ['orderbook', 'quote', 'rfq', 'maker', 'review first']),
        ('white-house-briefing', ['karoline', 'briefing', 'press briefing']),
    ],
    'speaker_profiles': [
        ('Donald Trump', ['trump', 'detour', 'unhinged', 'q&a', 'vibes']),
        ('JD Vance', ['jd vance', 'rare speaker', 'out of my element']),
        ('Karoline Leavitt', ['karoline', 'briefing', 'press secretary']),
        ('Recurring NFL announcer pair', ['announcer', 'broadcast', 'booth', 'network', 'fourth quarter']),
        ('Culture live-event host / production flow', ['performer', 'stage', 'production', 'halftime', 'show flow']),
        ('Powell / earnings-style formulaic speaker', ['powell', 'earnings', 'formulaic', 'prepared remarks']),
    ],
    'pricing_signals': [
        ('pooled-historical-rate-is-lying', ['pooled', 'all games', 'prime time', 'segment', 'historical rate']),
        ('setup-label-overreaction', ['open press', 'closed press', 'setup', 'roll call']),
        ('field-negative-inference-after-insider-buying', ['field', 'insider', 'performer', 'rest of the field', 'untouched names']),
        ('copy-trader-price-premium', ['copy trade', 'tail', 'worse price', 'follower']),
        ('phase-blind-pricing', ['prepared remarks', 'q&a', 'late path', 'dead yet', 'not said yet']),
        ('thin-history-fake-precision', ['thin history', 'rare', 'sparse', 'out of my element']),
        ('direct-name-path-underpriced', ['eli lilly', 'novo', 'named', 'counterparty']),
        ('small-account-spread-harvest', ['small portfolio', 'small account', 'wide spread', 'stale quote']),
        ('maker-quality-beats-theoretical-ev', ['maker', 'queue', 'fill quality', 'realized ev', 'entry quality']),
        ('bond-capital-lockup-tradeoff', ['capital allocation', 'bond-style', 'lock up', 'opportunity cost']),
    ],
    'crowd_mistakes': [
        ('overweighting-setup-labels', ['open press', 'closed press', 'setup', 'roll call']),
        ('trusting-pooled-historicals', ['all games', 'pooled', 'historical rate', 'prime time']),
        ('copy-trading-after-price-move', ['copy trade', 'tail', 'follower', 'worse price']),
        ('misreading-field-information', ['field', 'performer', 'rest of the field', 'untouched names']),
        ('assuming-setup-kills-late-paths', ['late path', 'not said yet', 'q&a', 'kills', 'dead too early']),
        ('confusing-logistics-with-probability-zero', ['logistics', 'stage', 'stadium', 'production', 'rehearsal']),
        ('assuming-random-yap-is-variance-not-structure', ['garbage time', 'fourth quarter', 'random yap', 'variance']),
    ],
    'dispute_patterns': [
        ('sub-brand-vs-parent-brand-ambiguity', ['brand', 'parent', 'sub-brand', 'claude', 'anthropic']),
        ('false-bond-via-rules-or-tail-risk', ['bond', '95', '99', 'tail risk', 'false bond']),
        ('speaker-vs-display-vs-context-resolution-confusion', ['display', 'context', 'spoken', 'count', 'counted']),
    ],
    'live_trading_tells': [
        ('full-size-fill-from-one-side', ['filled my whole', 'full fill', 'wiped the book', 'all at once']),
        ('book-moves-before-you-finish-thinking', ['moving away', 'kept moving', 'before i could fill', 'running away']),
        ('informed-pump-implies-rest-of-field-weaker', ['field', 'pumped', 'rest of the field', 'untouched names']),
        ('setup-cue-price-spike-without-live-confirmation', ['open press', 'closed press', 'setup', 'spike']),
        ('late-path-stays-too-cheap-after-silence', ['not said yet', 'late path', 'q&a', 'still cheap']),
        ('garbage-time-broadcast-drift', ['garbage time', 'fourth quarter', 'dead game', 'drift']),
        ('logistics-signal-before-performance', ['stadium', 'stage', 'rehearsal', 'production', 'logistics']),
    ],
    'execution_patterns': [
        ('segment-before-sizing-recurring-markets', ['all games', 'prime time', 'segment', 'announcer', 'network']),
        ('do-not-copy-trade-after-the-move', ['copy trade', 'tail', 'follower', 'worse price']),
        ('field-reprice-after-informed-flow', ['field', 'performer', 'rest of the field', 'untouched names']),
        ('model-the-event-in-phases', ['prepared remarks', 'q&a', 'late path', 'phase']),
        ('go-one-layer-deeper-than-the-crowd', ['one step deeper', 'extra level', 'specific quarter', 'additional step']),
        ('price-named-counterparties-above-theme-basket', ['eli lilly', 'novo', 'named', 'counterparty']),
        ('use-microstructure-edges-when-small', ['small account', 'small portfolio', 'wide spread', 'stale quote']),
        ('maker-first-unless-edge-is-decaying', ['limit order', 'maker', 'moving away', 'aggressive', 'decaying']),
        ('quote-where-ui-friction-gives-you-edge', ['review first', 'orderbook', 'rfq', 'manual', 'queue']),
        ('separate-setup-signal-from-true-path', ['open press', 'closed press', 'setup', 'path']),
    ],
    'sizing_lessons': [
        ('undersizing-is-a-leak', ['undersized', 'should have sized', 'should have gone bigger', 'regret']),
        ('size-down-under-thin-history', ['thin history', 'rare', 'sparse', 'uncertain']),
        ('small-account-microstructure-first', ['small account', 'small portfolio', 'wide spread', 'stale quote']),
        ('bond-size-by-tail-risk-not-win-rate', ['bond', '95', '99', 'tail risk']),
        ('capital-allocation-beats-isolated-ev', ['capital allocation', 'bond-style', 'lock up', 'opportunity cost']),
        ('execution-adjusted-sizing', ['fill quality', 'entry quality', 'realized ev']),
    ],
    'phase_logic': [
        ('prepared-remarks', ['prepared remarks', 'opening remarks', 'scripted']),
        ('q-and-a-window', ['q&a', 'questions', 'reporters']),
        ('late-q-and-a-detour', ['late path', 'late q&a', 'not said yet']),
        ('garbage-time-yap', ['garbage time', 'dead game', 'fourth quarter']),
        ('setup-fud-phase', ['open press', 'closed press', 'setup', 'roll call']),
    ],
}


def load(name):
    path = BASE / f'{name}.json'
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8'))


def normalize_text(s):
    return re.sub(r'\s+', ' ', s.lower()).strip()


def cluster_candidates(candidates, families):
    buckets = defaultdict(list)
    unmatched = []
    for cand in candidates:
        text = normalize_text(cand['text'])
        matched = False
        for family_name, hints in families:
            if any(h in text for h in hints):
                buckets[family_name].append(cand)
                matched = True
                break
        if not matched:
            unmatched.append(cand)
    rows = []
    for family_name, hints in families:
        ev = buckets.get(family_name, [])
        if not ev:
            continue
        ev_sorted = sorted(ev, key=lambda x: (-x['score'], x['video_id'], x['chunk_index']))
        rows.append({
            'canonical_name': family_name,
            'evidence_count': len(ev_sorted),
            'videos': sorted(list({x['video_id'] for x in ev_sorted})),
            'sample_evidence': ev_sorted[:12],
        })
    return rows, unmatched

summary = {}

for category, families in SCHEMES.items():
    cands = load(category)
    rows, unmatched = cluster_candidates(cands, families)
    out_path = OUT / f'{category}.json'
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    unmatched_path = OUT / f'{category}_unmatched.json'
    unmatched_path.write_text(json.dumps(unmatched[:200], ensure_ascii=False, indent=2), encoding='utf-8')
    summary[category] = {
        'raw_candidates': len(cands),
        'normalized_rows': len(rows),
        'matched_candidates': sum(r['evidence_count'] for r in rows),
        'unmatched_candidates': len(unmatched),
        'path': str(out_path),
    }

summary_path = OUT / 'summary.json'
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
print('OUT', OUT)
