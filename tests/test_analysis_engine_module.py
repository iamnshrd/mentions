from agents.mentions.services.analysis.engine import analyze_evidence_bundle


def test_analysis_engine_respects_policy_constraints(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.analysis.market.analyze_market',
        lambda market, frame: 'Market summary',
    )
    monkeypatch.setattr(
        'agents.mentions.services.analysis.signal.assess_signal',
        lambda market, frame: {'verdict': 'signal', 'signal_strength': 'strong'},
    )
    monkeypatch.setattr(
        'agents.mentions.services.analysis.speaker.extract_speaker_context',
        lambda transcripts, query: 'Speaker context',
    )
    monkeypatch.setattr(
        'agents.mentions.services.analysis.reasoning.build_reasoning_chain',
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
    assert 'Ограничения policy:' in result['conclusion']
    assert result['recommended_action'] == 'Пока наблюдать, policy ещё не разрешает trade recommendation'


def test_analysis_engine_surfaces_evidence_debug():
    result = analyze_evidence_bundle(
        query='Will Trump mention Iran?',
        frame={'route': 'speaker-event'},
        bundle={
            'market': {'market_data': {'ticker': 'KXTRUMPMENTION-IRAN'}, 'history': [{'price': 0.42}]},
            'news': [{'headline': 'Iran headline', 'url': 'https://example.com', 'source': 'Example'}],
            'transcripts': [{
                'chunk_id': 11,
                'document_id': 7,
                'chunk_index': 2,
                'speaker': 'Donald Trump',
                'event': 'Interview',
                'source_file': '/tmp/trump.txt',
            }],
            'workflow_policy': {'decision': 'full_analysis'},
            'runtime_health': {'transcripts': {'contract': 'transcript_search', 'status': 'ok'}},
            'sources_used': ['market', 'news', 'transcripts'],
            'transcript_intelligence': {
                'context_risks': ['runtime-db-transcript-fallback'],
                'lead_candidate': {
                    'trace': {'transcript_id': 'tx-1', 'segment_index': 0, 'source_ref': 'yt:abc'},
                },
            },
            'news_context': {
                'status': 'ok',
                'freshness': 'stored',
                'sufficiency': 'partial',
                'context_risks': ['runtime-db-news-fallback'],
            },
        },
    )
    debug = result['evidence_debug']
    assert debug['source_summary']['has_market_data'] is True
    assert debug['source_summary']['news_count'] == 1
    assert debug['runtime_health']['transcripts']['contract'] == 'transcript_search'
    assert debug['context_risks']['news'] == ['runtime-db-news-fallback']
    assert debug['context_risks']['transcripts'] == ['runtime-db-transcript-fallback']
    assert debug['transcript_trace']['lead_candidate']['transcript_id'] == 'tx-1'
    assert debug['transcript_trace']['retrieval_hits'][0]['chunk_id'] == 11
    assert debug['news_trace']['items'][0]['headline'] == 'Iran headline'
