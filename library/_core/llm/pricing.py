"""Model pricing table + cost computation for LLM calls.

Every rate is in **USD per million tokens** and applied to the four
distinct token categories the Anthropic API surfaces:

* ``input``         — regular (uncached) input tokens.
* ``output``        — generated output tokens.
* ``cache_read``    — input tokens served from the prompt cache.
* ``cache_write``   — input tokens written to the cache on this call
                      (the *creation* cost; reads afterwards are cheap).

Defaults below are approximate, public list prices as of writing. They
are conservative (error on the side of over-reporting cost) and can be
overridden at runtime by mutating :data:`PRICING` — callers who care
about exact numbers should pull fresh rates from the Anthropic pricing
page and patch the table at import time.

Unknown models resolve to a cost of 0.0 so a typo never breaks a live
call — the caller still gets the raw token counts from :class:`LLMResponse`.
"""
from __future__ import annotations


# Rates: USD per 1_000_000 tokens.
PRICING: dict[str, dict[str, float]] = {
    # Claude Haiku 4.5 — the default model for intent + extraction.
    'claude-haiku-4-5': {
        'input':       1.00,
        'output':      5.00,
        'cache_read':  0.10,
        'cache_write': 1.25,
    },
    # Claude Sonnet 4.5 — used for quality-sensitive extraction / analysis.
    'claude-sonnet-4-5': {
        'input':       3.00,
        'output':     15.00,
        'cache_read':  0.30,
        'cache_write': 3.75,
    },
    # Claude Opus 4 — reserved for hardest problems.
    'claude-opus-4': {
        'input':      15.00,
        'output':     75.00,
        'cache_read':  1.50,
        'cache_write':18.75,
    },
}

# Tokens are counted in millions → this is the denominator.
_MILLION = 1_000_000.0


def rates_for(model: str) -> dict[str, float]:
    """Return the per-category rate table for *model*, or zeros if unknown."""
    return PRICING.get(model, {'input': 0.0, 'output': 0.0,
                               'cache_read': 0.0, 'cache_write': 0.0})


def cost_usd(
    *,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_create_tokens: int = 0,
) -> float:
    """Compute USD cost for a single LLM call.

    Unknown models contribute 0.0 — we never raise. Negative token
    counts (which shouldn't happen but the SDK has surfaced bad values
    historically) are clamped to zero.
    """
    rates = rates_for(model)
    in_tok = max(0, int(input_tokens or 0))
    out_tok = max(0, int(output_tokens or 0))
    cr_tok = max(0, int(cache_read_tokens or 0))
    cc_tok = max(0, int(cache_create_tokens or 0))
    total = (
        in_tok  * rates.get('input',       0.0) +
        out_tok * rates.get('output',      0.0) +
        cr_tok  * rates.get('cache_read',  0.0) +
        cc_tok  * rates.get('cache_write', 0.0)
    ) / _MILLION
    return float(total)
