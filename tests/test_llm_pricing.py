"""Tests for LLM cost computation + CLI breakdown helper."""
from __future__ import annotations

import pytest

from mentions_domain.llm.pricing import PRICING, rates_for, cost_usd


# ── Unit: pricing ──────────────────────────────────────────────────────────

class TestRatesFor:
    def test_known_model(self):
        r = rates_for('claude-haiku-4-5')
        assert r['input']       == 1.00
        assert r['output']      == 5.00
        assert r['cache_read']  == 0.10
        assert r['cache_write'] == 1.25

    def test_unknown_model_zero(self):
        r = rates_for('gpt-99')
        assert r == {'input': 0.0, 'output': 0.0,
                     'cache_read': 0.0, 'cache_write': 0.0}


class TestCostUsd:
    def test_zero_tokens_zero_cost(self):
        assert cost_usd(model='claude-haiku-4-5') == 0.0

    def test_known_model_math(self):
        # 1M input + 1M output on haiku 4.5 → $1.00 + $5.00 = $6.00
        cost = cost_usd(
            model='claude-haiku-4-5',
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert abs(cost - 6.00) < 1e-9

    def test_cache_read_cheaper_than_input(self):
        # 1M cache_read on haiku 4.5 → $0.10
        cost = cost_usd(model='claude-haiku-4-5',
                        cache_read_tokens=1_000_000)
        assert abs(cost - 0.10) < 1e-9

    def test_cache_write_pricier_than_input(self):
        # 1M cache_write on haiku 4.5 → $1.25
        cost = cost_usd(model='claude-haiku-4-5',
                        cache_create_tokens=1_000_000)
        assert abs(cost - 1.25) < 1e-9

    def test_unknown_model_zero(self):
        # No rates → no cost, even with massive token counts.
        cost = cost_usd(model='gpt-99',
                        input_tokens=10_000_000,
                        output_tokens=10_000_000)
        assert cost == 0.0

    def test_negative_tokens_clamped(self):
        cost = cost_usd(model='claude-haiku-4-5',
                        input_tokens=-5,
                        output_tokens=-10)
        assert cost == 0.0

    def test_none_tokens_treated_as_zero(self):
        # Anthropic SDK has been observed returning None for usage fields.
        cost = cost_usd(model='claude-haiku-4-5',
                        input_tokens=None, output_tokens=None)
        assert cost == 0.0

    def test_sonnet_more_expensive_than_haiku(self):
        common = dict(input_tokens=1000, output_tokens=500)
        haiku  = cost_usd(model='claude-haiku-4-5',  **common)
        sonnet = cost_usd(model='claude-sonnet-4-5', **common)
        assert sonnet > haiku


# ── Integration: CLI breakdown helper ──────────────────────────────────────

class TestCostBreakdown:
    def test_breakdown_buckets_by_model(self):
        from mentions_core.cli import _cost_breakdown_from_counters
        rows = [
            {'name': 'llm.input_tokens',  'tags': 'model=claude-haiku-4-5', 'value': 1000},
            {'name': 'llm.output_tokens', 'tags': 'model=claude-haiku-4-5', 'value': 500},
            {'name': 'llm.cost_micro_usd', 'tags': 'model=claude-haiku-4-5', 'value': 3_500_000},  # $3.50
            {'name': 'llm.input_tokens',  'tags': 'model=claude-sonnet-4-5', 'value': 2000},
            {'name': 'llm.cost_micro_usd', 'tags': 'model=claude-sonnet-4-5', 'value': 6_000_000},  # $6.00
        ]
        out = _cost_breakdown_from_counters(rows)
        assert out['by_model']['claude-haiku-4-5']['input']    == 1000
        assert out['by_model']['claude-haiku-4-5']['output']   == 500
        assert out['by_model']['claude-haiku-4-5']['cost_usd'] == 3.50
        assert out['by_model']['claude-sonnet-4-5']['cost_usd'] == 6.00
        assert out['total_cost'] == 9.50

    def test_breakdown_empty_counters(self):
        from mentions_core.cli import _cost_breakdown_from_counters
        out = _cost_breakdown_from_counters([])
        assert out == {'by_model': {}, 'total_cost': 0.0}

    def test_breakdown_ignores_unrelated_counters(self):
        from mentions_core.cli import _cost_breakdown_from_counters
        rows = [
            {'name': 'intent.rules_fallback', 'tags': '', 'value': 5},
            {'name': 'llm.input_tokens', 'tags': 'model=claude-haiku-4-5', 'value': 100},
        ]
        out = _cost_breakdown_from_counters(rows)
        assert 'claude-haiku-4-5' in out['by_model']
        assert len(out['by_model']) == 1
