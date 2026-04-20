"""Integration tests for select_frame — ensures intent fields surface.

Uses the default NullClient path (so intent comes from rules), which is
enough to verify the wiring.
"""
from __future__ import annotations

from library._core.runtime.frame import select_frame


def test_frame_includes_intent_fields():
    frame = select_frame('why is BTC moving today?')
    assert 'intent' in frame
    assert 'intent_confidence' in frame
    assert 'intent_source' in frame
    assert 'entities' in frame
    assert 'speaker' in frame
    assert frame['intent_source'] in {'llm', 'rules'}
    assert isinstance(frame['intent_confidence'], float)
    assert isinstance(frame['entities'], dict)


def test_frame_speaker_forces_transcript():
    frame = select_frame('what did musk say')
    # Speaker extraction should flip needs_transcript True regardless
    # of base route heuristics.
    assert frame['needs_transcript'] is True
    assert frame['speaker']  # non-empty


def test_frame_preserves_legacy_fields():
    frame = select_frame('BTC price today')
    for key in ('route', 'category', 'mode', 'voice_bias',
                'needs_transcript', 'query'):
        assert key in frame
