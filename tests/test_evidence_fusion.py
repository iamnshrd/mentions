from agents.mentions.services.analysis.evidence_fusion import fuse_evidence_bundle


def test_fuse_evidence_bundle_builds_primary_and_secondary_sections():
    fused = fuse_evidence_bundle(
        query='Will Trump mention Iran?',
        frame={'route': 'analysis'},
        bundle={
            'market': {'market_data': {'ticker': 'KXTRUMPMENTION-26APR15-IRAN'}},
            'news_context': {'sufficiency': 'sufficient', 'freshness': 'high', 'news': [{'headline': 'Headline'}], 'summary': 'Fresh news'},
            'transcript_intelligence': {
                'chunks': [{'text': 'chunk1'}, {'text': 'chunk2'}],
                'summary': 'Transcript summary',
                'knowledge_bundle': {'pricing_signals': {'main_pricing_signal': 'signal'}},
            },
            'workflow_policy': {'decision': 'full_analysis'},
            'pmt_knowledge': {'pricing_signals': [{'signal_name': 'Overpriced chase'}]},
        },
    )
    assert fused['policy_state'] == 'full_analysis'
    assert len(fused['primary_evidence']) == 2
    assert len(fused['secondary_evidence']) == 3
    assert 'live_market_evidence' in fused['summary']['available_sections']
