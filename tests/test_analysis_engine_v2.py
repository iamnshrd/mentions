from agents.mentions.modules.analysis_engine.v2 import build_analysis_v2


def test_build_analysis_v2_uses_prior_and_posterior():
    result = build_analysis_v2(
        query='Will Trump mention Iran?',
        frame={'route': 'analysis'},
        bundle={
            'market_prior': {'prior_probability': 0.12},
            'posterior_update': {'suggested_posterior': 0.18},
            'selected_pmt_evidence': {'selected_pricing_signal': {'signal_name': 'Late chase overpriced'}},
            'challenge_block': {'disconfirming_indicator': 'Fresh reporting contradicts setup', 'what_changes_view': 'New transcript evidence'},
            'workflow_policy': {'decision': 'full_analysis'},
            'text_evidence_assessment': {'text_signal_strength': 'moderate', 'direction': 'supports_yes'},
        },
        legacy_analysis={'conclusion': 'Legacy conclusion'},
    )
    assert 'bounded move' in result['thesis']
    assert '0.120' in result['fair_value_view']
    assert result['key_risk'] == 'Fresh reporting contradicts setup'


def test_build_analysis_v2_surfaces_abstain_reasons():
    result = build_analysis_v2(
        query='Will Trump mention Iran?',
        frame={'route': 'analysis'},
        bundle={
            'market_prior': {'prior_probability': 0.12},
            'posterior_update': {'suggested_posterior': 0.12, 'abstain_flag': True, 'abstain_reasons': ['no_text_support', 'high_contradiction_load']},
            'selected_pmt_evidence': {},
            'challenge_block': {},
            'workflow_policy': {'decision': 'full_analysis'},
            'text_evidence_assessment': {'text_signal_strength': 'weak', 'direction': 'unclear'},
        },
        legacy_analysis={'conclusion': 'Legacy conclusion'},
    )
    assert 'no_text_support' in result['thesis']
    assert 'no_text_support' in result['recommended_action_v2']
