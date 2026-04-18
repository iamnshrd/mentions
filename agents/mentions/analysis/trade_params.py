"""Trade parameter computation for speaker event markets.

All logic is rule-based (no LLM). Computes:
  - Win condition (verbatim from market rules)
  - Difficulty level (easy / medium / hard)
  - Speaker tendency contribution
  - Invalidation conditions
  - Scaling-out plan
  - Sizing recommendation

Thresholds are read through the shared Mentions threshold helpers.
"""
from __future__ import annotations

import logging
import re

from agents.mentions.utils import get_threshold

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

# Sizing multipliers by (confidence, difficulty)
_SIZING: dict[tuple[str, str], tuple[float, str]] = {
    ('high',   'easy'):   (1.00, 'Full size — high confidence, clear edge.'),
    ('high',   'medium'): (0.75, '75% size — good confidence, moderate complexity.'),
    ('high',   'hard'):   (0.50, '50% size — high confidence but coin-flip market; limit exposure.'),
    ('medium', 'easy'):   (0.75, '75% size — moderate confidence, favourable setup.'),
    ('medium', 'medium'): (0.50, 'Half size — moderate confidence and complexity.'),
    ('medium', 'hard'):   (0.25, '25% size — borderline edge; small bet only.'),
    ('low',    'easy'):   (0.50, 'Half size — low confidence despite easy setup; caution warranted.'),
    ('low',    'medium'): (0.25, '25% size — weak edge; reduce exposure significantly.'),
    ('low',    'hard'):   (0.00, 'Skip — low confidence + coin-flip = no edge.'),
}


def compute_trade_params(market_data: dict,
                          speaker_tendency: dict,
                          confidence: str = 'medium',
                          event_context: dict | None = None) -> dict:
    """Compute rule-based trade parameters for a speaker event market.

    Parameters
    ----------
    market_data:
        Raw market dict from Kalshi API.
    speaker_tendency:
        Dict from ``speaker_extract.analyse_speaker_tendency()``.
    confidence:
        Overall analysis confidence: 'high' | 'medium' | 'low'.
    event_context:
        Optional dict from ``event_context.analyze_event_context()``.

    Returns
    -------
    dict with all trade parameters.
    """
    _load_thresholds()
    event_context = event_context or {}

    yes_price = _get_yes_price(market_data)
    rules     = market_data.get('rules_primary', market_data.get('rules', ''))
    title     = market_data.get('title', '')
    close     = market_data.get('close_time', market_data.get('expiration_time', ''))

    win_condition = _extract_win_condition(rules, title)
    difficulty, diff_factors = _assess_difficulty(yes_price, speaker_tendency, event_context)
    invalidation  = _build_invalidation(market_data, speaker_tendency, event_context)
    scaling_out   = _SCALING_PLAN.get(difficulty, _SCALING_PLAN['medium'])
    sizing_mult, sizing_note = _SIZING.get(
        (confidence, difficulty),
        (0.25, 'Conservative sizing — confidence/difficulty combination not in standard table.')
    )

    return {
        'win_condition':      win_condition,
        'difficulty':         difficulty,
        'difficulty_factors': diff_factors,
        'invalidation':       invalidation,
        'scaling_out':        scaling_out,
        'sizing_multiplier':  sizing_mult,
        'sizing_note':        sizing_note,
    }


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
                log.debug('Skipping invalid market price value: %r', val)
    return 50.0  # unknown → coin flip


def _extract_win_condition(rules: str, title: str) -> str:
    """Pull the resolution condition from market rules text."""
    if not rules:
        return f'Win condition: {title} resolves YES. See market rules for full criteria.'

    normalized = ' '.join((rules or '').split())

    direct_if = re.search(r'If\s+(.+?),\s*then the market resolves to Yes\.?', normalized, re.IGNORECASE)
    if direct_if:
        clause = direct_if.group(1).strip()
        return f'Win condition: if {clause}, the market resolves Yes.'

    # Try to extract the resolution sentence
    patterns = [
        r'(?:resolv(?:es?|ed?|ing)|settle[sd]?|pays? out)\s+(?:yes|no)?[^\n.]{10,300}',
        r'(?:market|contract)\s+(?:will\s+)?resolv\w+[^\n.]{10,300}',
        r'(?:this\s+)?(?:market|contract)\s+resolv\w+[^\n.]{10,300}',
        r'YES\s+if[^\n.]{5,300}',
        r'resolves\s+YES\s+if[^\n.]{5,300}',
    ]
    for p in patterns:
        m = re.search(p, normalized, re.IGNORECASE | re.DOTALL)
        if m:
            text = m.group(0).strip()
            if len(text) > 300:
                text = text[:300].rsplit(' ', 1)[0] + '…'
            return text

    return normalized[:250].strip() + ('…' if len(normalized) > 250 else '')


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
