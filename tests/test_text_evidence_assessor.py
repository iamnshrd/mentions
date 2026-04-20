from agents.mentions.services.analysis.text_evidence_assessor import assess_text_evidence


def test_assess_text_evidence_builds_update_pressure_block():
    result = assess_text_evidence(
        query='Will Trump mention Iran?',
        frame={'route': 'analysis'},
        market_prior={'market_regime': 'thin_noisy_market'},
        news_context={'freshness': 'high', 'news': [{'headline': 'Fresh headline'}], 'context_risks': []},
        transcript_intelligence={'status': 'ok', 'chunks': [{'text': 'chunk1'}, {'text': 'chunk2'}], 'context_risks': []},
        selected_pmt_evidence={'selected_pricing_signal': {'signal_name': 'Late chase overpriced'}},
    )
    assert result['text_signal_strength'] in ('moderate', 'strong')
    assert result['source_reliability'] in ('medium', 'high')
    assert 'market_regime=thin_noisy_market' in result['assessment_rationale']
