"""Trade parameter computation for speaker event markets.

All logic is rule-based (no LLM). Computes:
  - Win condition (verbatim from market rules)
  - Difficulty level (easy / medium / hard)
  - Speaker tendency contribution
  - Invalidation conditions
  - Scaling-out plan
  - Sizing recommendation (fractional-Kelly from v0.13)

Thresholds are read from the canonical pack assets file.

v0.13: sizing is now derived from :func:`mentions_domain.posteriors.
probability.kelly_fraction` when a subjective probability ``p`` is
available. The legacy 3×3 ``(confidence, difficulty)`` lookup table
is kept as a fallback when the caller only has a label. The output
dict carries ``sizing_multiplier`` (fractional-Kelly result) plus
``p_edge`` (p − q) for explicit edge reporting.
"""
from __future__ import annotations

import logging
import re

from agents.mentions.utils import get_threshold

from mentions_domain.posteriors.probability import (
    clamp01, kelly_fraction, p_from_label,
)

log = logging.getLogger('mentions')

# Difficulty price bands (YES price in cents, 0–100)
# Overridable via thresholds.json
_EASY_LOW  = None   # loaded lazily
_EASY_HIGH = None
_HARD_LOW  = None
_HARD_HIGH = None


def _load_thresholds():
    global _EASY_LOW, _EASY_HIGH, _HARD_LOW, _HARD_HIGH
    if _EASY_LOW is None:
        easy  = get_threshold('difficulty_easy_threshold', 0.30)   # 30¢
        hard  = get_threshold('difficulty_hard_threshold', 0.45)   # 45¢
        _EASY_LOW  = easy * 100          # <30¢  (strong NO)
        _EASY_HIGH = (1 - easy) * 100    # >70¢  (strong YES)
        _HARD_LOW  = hard * 100          # 45¢
        _HARD_HIGH = (1 - hard) * 100    # 55¢


# Scaling-out plans by difficulty
_SCALING_PLAN: dict[str, str] = {
    'easy': (
        'Take 50% off at 70% of entry price. '
        'Let remaining 50% run to resolution or stop at break-even.'
    ),
    'medium': (
        'Take 30% off at 60% of entry price. '
        'Reduce to 50% if price approaches invalidation level. '
        'Hold remainder to resolution.'
    ),
    'hard': (
        'Hold full position or exit entirely — '
        'coin-flip markets do not reward partial scaling. '
        'Set hard stop at 50% loss of entry price.'
    ),
}

# NOTE: the pre-v0.13 3×3 (confidence, difficulty) sizing table has been
# removed. Sizing is now Kelly-driven via
# :func:`mentions_domain.posteriors.probability.kelly_fraction`; the
# ``kelly_cap`` and ``kelly_fraction`` thresholds tune the conservatism.


def compute_trade_params(market_data: dict,
                          speaker_tendency: dict,
                          confidence: str = 'medium',
                          event_context: dict | None = None,
                          *,
                          p_yes: float | None = None) -> dict:
    """Compute rule-based trade parameters for a speaker event market.

    Parameters
    ----------
    market_data:
        Raw market dict from Kalshi API.
    speaker_tendency:
        Dict from ``speaker_extract.analyse_speaker_tendency()``.
    confidence:
        Overall analysis confidence: ``'high' | 'medium' | 'low'``.
        Used only when *p_yes* is not supplied (fallback).
    event_context:
        Optional dict from ``event_context.analyze_event_context()``.
    p_yes:
        Subjective probability of YES resolution, in [0, 1]. When
        supplied, sizing is computed via fractional Kelly against
        the market-implied price. When ``None``, falls back to the
        legacy ``confidence × difficulty`` lookup.

    Returns
    -------
    dict with all trade parameters, including ``p_edge`` and
    ``sizing_method`` ('kelly' | 'lookup') so the caller knows which
    path produced the size.
    """
    _load_thresholds()
    event_context = event_context or {}

    yes_price = _get_yes_price(market_data)                # 0..100 (cents)
    q = yes_price / 100.0                                  # implied p
    rules     = market_data.get('rules_primary', market_data.get('rules', ''))
    title     = market_data.get('title', '')
    close     = market_data.get('close_time', market_data.get('expiration_time', ''))

    win_condition = _extract_win_condition(rules, title)
    difficulty, diff_factors = _assess_difficulty(yes_price, speaker_tendency, event_context)
    invalidation  = _build_invalidation(market_data, speaker_tendency, event_context)
    scaling_out   = _SCALING_PLAN.get(difficulty, _SCALING_PLAN['medium'])

    # ── Sizing ────────────────────────────────────────────────────────────
    if p_yes is not None:
        p = clamp01(p_yes)
        cap = float(get_threshold('kelly_cap', 0.25))
        frac = float(get_threshold('kelly_fraction', 0.25))
        sizing_mult = kelly_fraction(p=p, q=q, fractional=frac, cap=cap)
        p_edge = p - q
        sizing_method = 'kelly'
        sizing_note = _kelly_note(sizing_mult, p_edge, p, q)
    else:
        # Legacy fallback: compose p from the label and run the same Kelly.
        # This keeps the number path unified — we just degrade gracefully
        # when the caller only has a coarse label.
        p = p_from_label(confidence)
        cap = float(get_threshold('kelly_cap', 0.25))
        frac = float(get_threshold('kelly_fraction', 0.25))
        sizing_mult = kelly_fraction(p=p, q=q, fractional=frac, cap=cap)
        p_edge = p - q
        sizing_method = 'kelly_from_label'
        sizing_note = _kelly_note(sizing_mult, p_edge, p, q)

    return {
        'win_condition':      win_condition,
        'difficulty':         difficulty,
        'difficulty_factors': diff_factors,
        'invalidation':       invalidation,
        'scaling_out':        scaling_out,
        'p_yes':              round(p, 4),
        'q_market':           round(q, 4),
        'p_edge':             round(p_edge, 4),
        'sizing_multiplier':  round(sizing_mult, 4),
        'sizing_method':      sizing_method,
        'sizing_note':        sizing_note,
    }


def _kelly_note(size: float, edge: float, p: float, q: float) -> str:
    """Build a human-readable sizing note from the Kelly result."""
    if size <= 0.0:
        if edge <= 0:
            return (
                f'Skip — no positive edge (subjective p={p:.2f} ≤ market q={q:.2f}).'
            )
        return f'Skip — edge {edge:+.3f} too small after fractional-Kelly cap.'
    pct = size * 100
    return (
        f'Fractional-Kelly size {pct:.1f}% of bankroll '
        f'(edge {edge:+.3f}; p={p:.2f}, q={q:.2f}).'
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_yes_price(market_data: dict) -> float:
    """Return YES price in cents (0–100)."""
    for key in ('yes_bid', 'yes_ask', 'yes_price', 'last_price'):
        val = market_data.get(key)
        if val is not None:
            try:
                p = float(val)
                # Kalshi returns prices in cents (0–100) or fractions (0–1)
                return p if p > 1 else p * 100
            except (TypeError, ValueError):
                pass
    return 50.0  # unknown → coin flip


def _extract_win_condition(rules: str, title: str) -> str:
    """Pull the resolution condition from market rules text."""
    if not rules:
        return f'Win condition: {title} resolves YES. See market rules for full criteria.'

    # Try to extract the resolution sentence
    patterns = [
        r'(?:resolv(?:es?|ed?|ing)|settle[sd]?|pays? out)\s+(?:yes|no)?[^\n.]{10,300}',
        r'(?:market|contract)\s+(?:will\s+)?resolv\w+[^\n.]{10,300}',
        r'(?:this\s+)?(?:market|contract)\s+resolv\w+[^\n.]{10,300}',
        r'YES\s+if[^\n.]{5,300}',
        r'resolves\s+YES\s+if[^\n.]{5,300}',
    ]
    for p in patterns:
        m = re.search(p, rules, re.IGNORECASE | re.DOTALL)
        if m:
            text = m.group(0).strip()
            # Truncate at 300 chars
            if len(text) > 300:
                text = text[:300].rsplit(' ', 1)[0] + '…'
            return text

    # Fallback: first 250 chars of rules
    return rules[:250].strip() + ('…' if len(rules) > 250 else '')


def _assess_difficulty(yes_price: float,
                        speaker_tendency: dict,
                        event_context: dict) -> tuple[str, list[str]]:
    """Return (difficulty, factors_list)."""
    factors: list[str] = []
    score = 0  # higher → harder

    # Price-based difficulty
    if yes_price < _EASY_LOW or yes_price > _EASY_HIGH:
        factors.append(f'YES price {yes_price:.0f}¢ — strong directional pricing (easy)')
        score -= 1
    elif _HARD_LOW <= yes_price <= _HARD_HIGH:
        factors.append(f'YES price {yes_price:.0f}¢ — near coin-flip (hard)')
        score += 2
    else:
        factors.append(f'YES price {yes_price:.0f}¢ — moderate directional pricing')
        score += 1

    # Tendency-based difficulty
    tendency = speaker_tendency.get('tendency', 'unknown')
    if tendency == 'evasive':
        factors.append('Speaker shows evasive pattern — harder to predict mentions')
        score += 1
    elif tendency == 'hit_all':
        factors.append('Speaker typically addresses topics broadly — easier to predict')
        score -= 1
    elif tendency == 'unknown':
        factors.append('Speaker tendency unknown — adds uncertainty')
        score += 1

    # Event format difficulty
    fmt = event_context.get('format', '')
    qa  = event_context.get('qa_likelihood', 'medium')
    if fmt == 'speech' or qa == 'low':
        factors.append('Speech / low Q&A format — fewer spontaneous mentions expected')
        score += 1
    elif qa == 'high':
        factors.append('High Q&A likelihood — more opportunity for strike conditions to be hit')
        score -= 1

    if score <= -1:
        return 'easy', factors
    elif score >= 2:
        return 'hard', factors
    else:
        return 'medium', factors


def _build_invalidation(market_data: dict,
                         speaker_tendency: dict,
                         event_context: dict) -> str:
    """Build a plain-English invalidation statement."""
    parts: list[str] = []

    # Event cancellation is always the primary invalidation
    speaker = speaker_tendency.get('speaker_name', 'The speaker')
    fmt = event_context.get('format', 'event')
    date = event_context.get('event_date', '')

    parts.append(
        f'Primary: {speaker} does not appear at the {fmt}'
        + (f' on {date}' if date else '') + '.'
    )

    # Evasive speakers add a "topic not raised" invalidation
    tendency = speaker_tendency.get('tendency', '')
    if tendency == 'evasive':
        parts.append(
            'Secondary: Topic is explicitly stated as off-agenda or speaker '
            'declines to address it early in the session.'
        )

    # For mention markets: topic becoming old news
    rules = market_data.get('rules_primary', market_data.get('rules', ''))
    if 'mention' in rules.lower() or 'mention' in market_data.get('title', '').lower():
        parts.append(
            'Additional: If the topic is already exhausted in pre-event coverage, '
            'speaker may skip it as redundant.'
        )

    return ' '.join(parts)
