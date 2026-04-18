from agents.mentions.modules.posterior_update.policy import compute_posterior_update


def test_compute_posterior_update_applies_bounded_move():
    result = compute_posterior_update(
        market_prior={'prior_probability': 0.4, 'market_regime': 'ambiguous_mid_confidence'},
        text_evidence_assessment={
            'text_signal_strength': 'moderate',
            'direction': 'supports_yes',
            'source_reliability': 'medium',
            'contradiction_penalty': 0,
            'fresh_support_score': 2,
        },
        workflow_policy={'decision': 'full_analysis'},
    )
    assert result['suggested_posterior'] is not None
    assert result['suggested_posterior'] > 0.4
    assert result['abstain_flag'] is False


def test_compute_posterior_update_abstains_on_conflicted_weak_evidence():
    result = compute_posterior_update(
        market_prior={'prior_probability': 0.4, 'market_regime': 'thin_noisy_market', 'prior_quality': 'quoted_only'},
        text_evidence_assessment={
            'text_signal_strength': 'weak',
            'direction': 'supports_yes',
            'source_reliability': 'low',
            'contradiction_penalty': 2,
            'fresh_support_score': 0,
        },
        workflow_policy={'decision': 'full_analysis'},
    )
    assert result['abstain_flag'] is True
    assert 'high_contradiction_load' in result['abstain_reasons']
    assert result['suggested_posterior'] == 0.4
