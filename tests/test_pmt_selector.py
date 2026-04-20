from agents.mentions.services.markets.pmt_selector import select_pmt_evidence


def test_select_pmt_evidence_returns_compact_selected_block():
    result = select_pmt_evidence(
        query='Will Trump mention Iran?',
        frame={'route': 'analysis'},
        market_prior={'market_regime': 'thin_noisy_market'},
        pmt_knowledge={
            'pricing_signals': [{'signal_name': 'Late chase overpriced'}],
            'execution_patterns': [{'pattern_name': 'Use passive orders'}],
            'phase_logic': [{'phase_name': 'prepared-remarks'}],
            'decision_cases': [{'market_context': 'Similar Trump mention case'}],
            'speaker_profiles': [{'speaker_name': 'Donald Trump'}],
        },
    )
    assert result['selected_pricing_signal']['signal_name'] == 'Late chase overpriced'
    assert result['selected_execution_pattern']['pattern_name'] == 'Use passive orders'
    assert 'market_regime=thin_noisy_market' in result['selection_rationale']


def test_select_pmt_evidence_penalizes_generic_analogs():
    result = select_pmt_evidence(
        query='Will Trump mention Iran in a press conference?',
        frame={'route': 'analysis'},
        market_prior={'market_regime': 'thin_noisy_market'},
        pmt_knowledge={
            'decision_cases': [
                {'market_context': 'Generic macro case template', 'setup': 'broad general case', 'reasoning': 'general case without Iran or briefing context'},
                {'market_context': 'Trump Iran press briefing case', 'setup': 'Iran came up in briefing Q&A', 'reasoning': 'similar press conference context'},
            ],
        },
    )
    assert result['selected_analog']['market_context'] == 'Trump Iran press briefing case'
    rejected = result['rejected_candidates']['decision_cases']
    assert any('generic_case_penalty' in row['reasons'] for row in rejected)
