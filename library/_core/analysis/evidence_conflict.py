"""Evidence-conflict detection — downweight p_signal when sources disagree.

The retrieve bundle pulls transcripts, news, and market history based
on the query. Pre-v0.13.1 we fed them straight into synthesis without
checking whether they **agreed**. Imagine retrieving two Fed-speech
snippets where one says "inflation is cooling" and the other says
"we remain hawkish" — the agent would happily emit a confident
directional call on contradictory evidence.

This module tags each snippet with a bullish / bearish / neutral
stance via a compact keyword lexicon, then measures disagreement:

* If the split between bullish and bearish is large enough
  (threshold: minority ≥ 30 % of polarized signals), we flag the
  bundle as *conflicted* and return a probability factor < 0.5.
* That factor flows through the same log-odds combinator used by
  :mod:`signal` and :mod:`anti_patterns`, so one conflict flag shaves
  a few percentage points off ``p_signal``; a perfect 50/50 split
  hits harder.

The lexicon is intentionally domain-tuned to Fed / macro / Kalshi
political-and-rate markets — it's not a general sentiment analyser.
For anything deeper we'd pass each snippet through an NLI model, but
keyword coverage is ~80 % accurate on the corpus and costs nothing.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger('mentions')


# Domain lexicon — stems + common inflections. Order matters only for
# readability; matching is set-based.
_BULLISH = frozenset({
    # Fed / rates — cuts are bullish for risk assets, the direction
    # we tag below is "pro YES on the standard 'will asset go up'
    # question" which in Kalshi terms maps to hawk→bear, dove→bull
    # most of the time. Callers that care about a specific market
    # should frame accordingly.
    'dovish', 'cut', 'cuts', 'ease', 'easing', 'loose', 'loosen',
    'accommodative', 'stimulus', 'pause',
    # Markets
    'bullish', 'rally', 'surge', 'breakout', 'uptrend',
    'gain', 'gains', 'advance', 'upgrade', 'upgraded',
    # Macro positive
    'beat', 'beats', 'outperform', 'strong', 'robust', 'resilient',
    'expansion', 'growth',
})

_BEARISH = frozenset({
    # Fed / rates
    'hawkish', 'hike', 'hikes', 'raise', 'raising', 'tighten',
    'tightening', 'restrictive',
    # Markets
    'bearish', 'selloff', 'plunge', 'plunged', 'decline', 'declined',
    'downtrend', 'crash', 'collapse', 'downgrade', 'downgraded',
    # Macro negative
    'miss', 'misses', 'underperform', 'weak', 'weaken', 'recession',
    'slowdown', 'contraction', 'stagflation',
})


# Threshold: below this fraction the bundle is unanimous enough to
# ignore a few stray opposing tokens. Tuned so 1-out-of-4 disagreeing
# is tolerated (0.25 < 0.30) but 1-out-of-3 is flagged.
_CONFLICT_THRESHOLD = 0.30

# Factor-p mapping. See module docstring.
#   factor_p = 0.50 − 0.40 × conflict_ratio
# conflict_ratio ranges [0, 0.5]; at 0.5 (perfect split) p=0.30.
_BASE_P = 0.50
_MAX_SHIFT = 0.40


def classify_stance(text: str) -> str:
    """Return ``'bullish' | 'bearish' | 'neutral'`` for a single text.

    Tokenisation is deliberately dumb: split on non-alphanum,
    lowercase, drop length-<3 tokens. Rich parsing isn't worth the
    complexity — the whole point is a cheap coarse signal.
    """
    if not text:
        return 'neutral'
    tokens = {t for t in re.split(r'[^a-z]+', text.lower()) if len(t) > 2}
    bulls = len(tokens & _BULLISH)
    bears = len(tokens & _BEARISH)
    if bulls > bears:
        return 'bullish'
    if bears > bulls:
        return 'bearish'
    return 'neutral'


def _iter_snippets(bundle: dict):
    """Yield ``(source, text)`` pairs from the relevant bundle sections.

    Skips sections that don't exist or are empty; the caller doesn't
    need to worry about shape.
    """
    for t in bundle.get('transcripts') or []:
        # Transcript rows carry a 'text' field (see hybrid.py).
        text = t.get('text') or t.get('snippet') or ''
        if text:
            yield ('transcript', text)
    for n in bundle.get('news') or []:
        text = ' '.join(
            str(n.get(k, '')) for k in ('headline', 'summary', 'text')
        ).strip()
        if text:
            yield ('news', text)


def detect_conflict(bundle: dict) -> dict:
    """Measure directional-stance disagreement across the bundle.

    Returns::

        {
            'stances':         list[dict],   # {source, stance, snippet}
            'counts':          {'bullish': n, 'bearish': n, 'neutral': n},
            'conflict_ratio':  float,        # minority / (minority+majority)
            'conflicted':      bool,
            'factor_p':        float | None, # ready for combine_independent
            'flag':            str | None,   # human-readable one-liner
        }
    """
    stances: list[dict] = []
    counts = {'bullish': 0, 'bearish': 0, 'neutral': 0}
    for source, text in _iter_snippets(bundle):
        stance = classify_stance(text)
        counts[stance] += 1
        stances.append({
            'source':  source,
            'stance':  stance,
            'snippet': text[:160],
        })

    polarised = counts['bullish'] + counts['bearish']
    if polarised < 2:
        # Need at least two polarised signals to define a conflict.
        return {
            'stances':        stances,
            'counts':         counts,
            'conflict_ratio': 0.0,
            'conflicted':     False,
            'factor_p':       None,
            'flag':           None,
        }
    minority = min(counts['bullish'], counts['bearish'])
    majority = max(counts['bullish'], counts['bearish'])
    ratio = minority / (minority + majority) if (minority + majority) else 0.0
    conflicted = ratio >= _CONFLICT_THRESHOLD
    factor_p = None
    flag = None
    if conflicted:
        factor_p = max(0.0, min(1.0, _BASE_P - _MAX_SHIFT * ratio))
        flag = (f'Evidence conflict: {counts["bullish"]} bullish vs '
                f'{counts["bearish"]} bearish across {polarised} snippets')
    return {
        'stances':        stances,
        'counts':         counts,
        'conflict_ratio': round(ratio, 4),
        'conflicted':     conflicted,
        'factor_p':       round(factor_p, 4) if factor_p is not None else None,
        'flag':           flag,
    }


def apply_to_p_signal(p_signal: float | None,
                      conflict: dict) -> float | None:
    """Fold the conflict ``factor_p`` into an existing p_signal.

    Mirrors :func:`anti_patterns.apply_to_p_signal` — same combinator,
    different source of evidence. Returns the input unchanged when
    there's no active conflict.
    """
    from library._core.analysis.probability import (
        clamp01, combine_independent,
    )
    if p_signal is None or not conflict.get('conflicted'):
        return p_signal
    factor = conflict.get('factor_p')
    if factor is None:
        return p_signal
    return clamp01(combine_independent(p_signal, [factor]))
