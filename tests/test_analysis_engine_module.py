from agents.mentions.modules.analysis_engine.engine import analyze_evidence_bundle


def test_analysis_engine_respects_policy_constraints(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.analysis.market.analyze_market',
        lambda market, frame: 'Market summary',
    )
    monkeypatch.setattr(
        'agents.mentions.analysis.signal.assess_signal',
        lambda market, frame: {'verdict': 'signal', 'signal_strength': 'strong'},
    )
    monkeypatch.setattr(
        'agents.mentions.analysis.speaker.extract_speaker_context',
        lambda transcripts, query: 'Speaker context',
    )
    monkeypatch.setattr(
        'agents.mentions.analysis.reasoning.build_reasoning_chain',
        lambda **kwargs: ['Reason 1', 'Reason 2'],
    )

    result = analyze_evidence_bundle(
        query='Will Trump mention Iran?',
        frame={'route': 'speaker-event'},
        bundle={
            'market': {'market_data': {'ticker': 'KXTRUMPMENTION-IRAN'}},
            'news': [],
            'transcripts': [],
            'workflow_policy': {
                'decision': 'partial_only',
                'reasons': ['fresh-context-missing'],
                'allow_trade_recommendation': False,
            },
        },
    )
    assert result['confidence'] == 'low' or result['confidence'] == 'medium'
    assert 'Policy constraints:' in result['conclusion']
    assert result['recommended_action'] == 'Monitor — policy does not allow trade recommendation yet'
