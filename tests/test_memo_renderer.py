from agents.mentions.modules.memo_renderer import render_memo_output


def test_memo_renderer_deep_contains_sections():
    text = render_memo_output(
        query='Will Trump mention Iran?',
        frame={'route': 'speaker-event'},
        synthesis={
            'market_summary': 'Market: Will Trump mention Iran?',
            'signal_assessment': {'verdict': 'unclear', 'signal_strength': 'unknown'},
            'reasoning_chain': ['Resolution still weak', 'Fresh context incomplete'],
            'transcript_context': 'No speaker context yet',
            'news_context': 'No direct news confirmation',
            'conclusion': 'Partial only.',
            'confidence': 'low',
            'recommended_action': 'Wait for better context',
        },
        mode='deep',
    )
    assert 'Analysis:' in text
    assert 'Reasoning chain:' in text
    assert 'Conclusion:' in text
    assert 'Recommended action:' in text


def test_memo_renderer_quick_is_compact():
    text = render_memo_output(
        query='x',
        frame={},
        synthesis={
            'market_summary': 'Market summary',
            'signal_assessment': {'verdict': 'unclear', 'signal_strength': 'unknown'},
            'conclusion': 'No edge',
            'confidence': 'low',
        },
        mode='quick',
    )
    assert 'Market summary' in text
    assert 'Signal:' in text
    assert 'Confidence:' in text
