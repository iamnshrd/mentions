from agents.mentions.services.analysis.engine_v2 import build_analysis_v2


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
    assert 'ограниченный сдвиг' in result['thesis']
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
    assert 'нет текстового подтверждения' in result['thesis']
    assert 'нет текстового подтверждения' in result['recommended_action_v2']


def test_build_analysis_v2_surfaces_structured_analysis_card():
    result = build_analysis_v2(
        query='Will Trump mention Iran?',
        frame={'route': 'analysis'},
        bundle={
            'market_prior': {'prior_probability': 0.12},
            'posterior_update': {'suggested_posterior': 0.18},
            'selected_pmt_evidence': {'selected_pricing_signal': {'signal_name': 'Late chase overpriced'}},
            'challenge_block': {
                'disconfirming_indicator': 'Fresh reporting contradicts setup',
                'what_changes_view': 'New transcript evidence',
            },
            'workflow_policy': {'decision': 'full_analysis'},
            'text_evidence_assessment': {'text_signal_strength': 'moderate', 'direction': 'supports_yes'},
            'fused_evidence': {'coverage': {'has_news': True, 'has_transcripts': False, 'has_market': True}, 'conflicts': []},
        },
        legacy_analysis={'conclusion': 'Legacy conclusion'},
    )
    card = result['analysis_card']
    assert card['thesis'] == result['thesis']
    assert card['risk'] == 'Fresh reporting contradicts setup'
    assert card['next_check'] == 'New transcript evidence'
    assert isinstance(card['evidence'], list)
    assert card['evidence']
    assert result['evidence_points'] == card['evidence']


def test_build_analysis_v2_surfaces_uncertainty_and_next_check_for_abstain():
    result = build_analysis_v2(
        query='Will Trump mention Iran?',
        frame={'route': 'analysis'},
        bundle={
            'market_prior': {'prior_probability': 0.12},
            'posterior_update': {
                'suggested_posterior': 0.12,
                'abstain_flag': True,
                'abstain_reasons': ['no_text_support', 'high_contradiction_load'],
            },
            'selected_pmt_evidence': {},
            'challenge_block': {},
            'workflow_policy': {'decision': 'full_analysis'},
            'text_evidence_assessment': {'text_signal_strength': 'weak', 'direction': 'unclear'},
            'fused_evidence': {'coverage': {'has_news': False, 'has_transcripts': False, 'has_market': True}, 'conflicts': ['a', 'b']},
        },
        legacy_analysis={'conclusion': 'Legacy conclusion'},
    )
    assert 'Апдейт остановлен:' in result['uncertainty']
    assert 'Нужен прямой текстовый триггер' in result['next_check']
