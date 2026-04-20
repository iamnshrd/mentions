"""Integration tests for select_frame — ensures intent fields surface.

Uses the default NullClient path (so intent comes from rules), which is
enough to verify the wiring.
"""
from __future__ import annotations

from agents.mentions.workflows.frame_selection import select_frame


def test_frame_includes_intent_fields():
    frame = select_frame('why is BTC moving today?')
    assert 'route' in frame
    assert 'category' in frame
    assert 'mode' in frame
    assert 'voice_bias' in frame
    assert 'needs_transcript' in frame
    assert 'query' in frame


def test_frame_speaker_forces_transcript():
    frame = select_frame('what did musk say')
    # Speaker extraction should flip needs_transcript True regardless
    # of base route heuristics.
    assert frame['needs_transcript'] is True
    assert frame['route'] in {'speaker-history', 'speaker-event', 'context-research', 'macro', 'trend-analysis'}


def test_frame_preserves_legacy_fields():
    frame = select_frame('BTC price today')
    for key in ('route', 'category', 'mode', 'voice_bias',
                'needs_transcript', 'query'):
        assert key in frame
