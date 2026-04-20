"""Tests for evidence_conflict.py — v0.13.1.

Covers the keyword stance classifier, the bundle-level disagreement
detector, and the synthesize integration that folds the conflict
factor through the same combinator anti_patterns uses.
"""
from __future__ import annotations

import pytest

from mentions_domain.analysis.evidence_conflict import (
    apply_to_p_signal, classify_stance, detect_conflict,
)


# ── Stance classifier ─────────────────────────────────────────────────────

class TestClassifyStance:
    def test_empty_is_neutral(self):
        assert classify_stance('') == 'neutral'
        assert classify_stance('   ') == 'neutral'

    def test_bullish_keywords(self):
        assert classify_stance('Fed turns dovish, rate cut expected') == 'bullish'
        assert classify_stance('Strong rally on robust earnings beat') == 'bullish'

    def test_bearish_keywords(self):
        assert classify_stance('Hawkish Fed hints at more hikes') == 'bearish'
        assert classify_stance('Selloff after downgrade and weak guidance') == 'bearish'

    def test_ties_go_neutral(self):
        # Equal bullish + bearish tokens → neutral.
        assert classify_stance('dovish hawkish') == 'neutral'

    def test_short_tokens_ignored(self):
        # "cut" is length-3 and IS in the lexicon, but "ha" (part of
        # "hawkish") would be filtered. Sanity-check the length filter.
        assert classify_stance('aa bb cc') == 'neutral'


# ── Bundle-level conflict ─────────────────────────────────────────────────

class TestDetectConflict:
    def test_empty_bundle(self):
        out = detect_conflict({})
        assert out['conflicted'] is False
        assert out['factor_p'] is None

    def test_all_bullish_no_conflict(self):
        bundle = {
            'transcripts': [
                {'text': 'Fed turns dovish, cuts on table'},
                {'text': 'Strong rally expected, growth robust'},
            ],
            'news': [{'headline': 'Markets surge on stimulus hopes'}],
        }
        out = detect_conflict(bundle)
        assert out['counts']['bullish'] == 3
        assert out['counts']['bearish'] == 0
        assert out['conflicted'] is False
        assert out['factor_p'] is None

    def test_split_triggers_conflict(self):
        bundle = {
            'transcripts': [
                {'text': 'Hawkish rhetoric, rates stay restrictive'},
                {'text': 'Dovish pivot ahead, cuts priced in'},
            ],
            'news': [{'headline': 'Growth robust, rally continues'}],
        }
        out = detect_conflict(bundle)
        # bull=2 (dovish+rally/robust), bear=1 (hawkish)
        assert out['counts']['bullish'] >= 2
        assert out['counts']['bearish'] >= 1
        assert out['conflicted'] is True
        assert out['factor_p'] is not None
        assert out['factor_p'] < 0.5
        assert out['flag'] and 'conflict' in out['flag'].lower()

    def test_perfect_split_hits_hardest(self):
        bundle = {
            'transcripts': [
                {'text': 'Hawkish hike restrictive tightening'},
                {'text': 'Dovish cut ease accommodative'},
            ],
        }
        out = detect_conflict(bundle)
        assert out['conflicted'] is True
        # Perfect 50/50 → ratio 0.5 → factor_p = 0.50 − 0.40*0.5 = 0.30.
        assert out['factor_p'] == pytest.approx(0.30, abs=0.01)

    def test_below_threshold_not_flagged(self):
        # 1 vs 3 → minority ratio 0.25 < 0.30 threshold
        bundle = {
            'transcripts': [
                {'text': 'dovish'},
                {'text': 'dovish'},
                {'text': 'dovish'},
                {'text': 'hawkish'},
            ],
        }
        out = detect_conflict(bundle)
        assert out['counts']['bullish'] == 3
        assert out['counts']['bearish'] == 1
        assert out['conflicted'] is False

    def test_need_two_polarised_to_flag(self):
        # One polarised + many neutrals → no conflict possible.
        bundle = {
            'transcripts': [{'text': 'dovish'}],
            'news': [{'headline': 'market opens today'}],
        }
        out = detect_conflict(bundle)
        assert out['conflicted'] is False

    def test_reads_snippet_field_too(self):
        bundle = {'transcripts': [{'snippet': 'hawkish hike'}]}
        out = detect_conflict(bundle)
        assert out['counts']['bearish'] == 1


# ── apply_to_p_signal ─────────────────────────────────────────────────────

class TestApplyToPSignal:
    def test_no_conflict_is_identity(self):
        c = {'conflicted': False, 'factor_p': None}
        assert apply_to_p_signal(0.7, c) == 0.7

    def test_none_p_signal(self):
        c = {'conflicted': True, 'factor_p': 0.3}
        assert apply_to_p_signal(None, c) is None

    def test_active_conflict_shrinks_toward_half(self):
        c = {'conflicted': True, 'factor_p': 0.3}
        adjusted = apply_to_p_signal(0.7, c)
        # Combining 0.7 with a 0.3 factor should pull below 0.7.
        assert adjusted is not None
        assert adjusted < 0.7


# ── Synthesize integration ────────────────────────────────────────────────

class TestSynthesizeIntegration:
    def test_canonical_synthesize_returns_structured_analysis(self, tmp_workspace, tmp_db):
        from agents.mentions.workflows.synthesize import synthesize
        bundle = {
            'market': {},
            'transcripts': [
                {'text': 'Hawkish, hike, restrictive'},
                {'text': 'Dovish, cut, accommodative'},
            ],
            'news': [],
            'doc_ids': [],
        }
        out = synthesize('q', {}, bundle)
        assert isinstance(out, dict)
        assert 'conclusion' in out

    def test_canonical_synthesize_handles_neutral_bundle(self, tmp_workspace, tmp_db):
        from agents.mentions.workflows.synthesize import synthesize
        bundle = {
            'market': {},
            'transcripts': [{'text': 'Neutral update, steady as she goes'}],
            'news': [],
            'doc_ids': [],
        }
        out = synthesize('q', {}, bundle)
        assert isinstance(out, dict)
        assert 'conclusion' in out
