"""Model pricing table + cost computation for LLM calls."""
from __future__ import annotations

PRICING: dict[str, dict[str, float]] = {
    'claude-haiku-4-5': {
        'input': 1.00,
        'output': 5.00,
        'cache_read': 0.10,
        'cache_write': 1.25,
    },
    'claude-sonnet-4-5': {
        'input': 3.00,
        'output': 15.00,
        'cache_read': 0.30,
        'cache_write': 3.75,
    },
    'claude-opus-4': {
        'input': 15.00,
        'output': 75.00,
        'cache_read': 1.50,
        'cache_write': 18.75,
    },
}

_MILLION = 1_000_000.0


def rates_for(model: str) -> dict[str, float]:
    return PRICING.get(model, {'input': 0.0, 'output': 0.0, 'cache_read': 0.0, 'cache_write': 0.0})


def cost_usd(
    *,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_create_tokens: int = 0,
) -> float:
    rates = rates_for(model)
    in_tok = max(0, int(input_tokens or 0))
    out_tok = max(0, int(output_tokens or 0))
    cr_tok = max(0, int(cache_read_tokens or 0))
    cc_tok = max(0, int(cache_create_tokens or 0))
    total = (
        in_tok * rates.get('input', 0.0)
        + out_tok * rates.get('output', 0.0)
        + cr_tok * rates.get('cache_read', 0.0)
        + cc_tok * rates.get('cache_write', 0.0)
    ) / _MILLION
    return float(total)
