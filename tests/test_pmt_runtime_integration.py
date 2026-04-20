from agents.mentions.modules.analysis_engine.engine import analyze_evidence_bundle


def test_analysis_engine_appends_pmt_reasoning(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.analysis.market.analyze_market',
        lambda market, frame: 'Market summary',
    )
    monkeypatch.setattr(
        'agents.mentions.analysis.signal.assess_signal',
        lambda market, frame: {'verdict': 'unclear', 'signal_strength': 'unknown'},
    )
    monkeypatch.setattr(
        'agents.mentions.analysis.speaker.extract_speaker_context',
        lambda transcripts, query: 'Speaker context',
    )
    monkeypatch.setattr(
        'agents.mentions.analysis.reasoning.build_reasoning_chain',
        lambda **kwargs: ['Base reasoning'],
    )

    result = analyze_evidence_bundle(
        query='Will Trump mention Iran?',
        frame={},
        bundle={
            'market': {'market_data': {}},
            'news': [],
            'transcripts': [],
            'workflow_policy': {},
            'pmt_knowledge': {
                'pricing_signals': [{'signal_name': 'Overpriced late chase'}],
                'execution_patterns': [{'pattern_name': 'Limit laddering'}],
            },
        },
    )
    assert any('PMT KB:' in step for step in result['reasoning_chain'])
