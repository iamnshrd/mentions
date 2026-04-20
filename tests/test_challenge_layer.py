from agents.mentions.services.analysis.challenge import build_challenge_block


def test_build_challenge_block_exposes_governance_fields():
    block = build_challenge_block(
        market_prior={'market_regime': 'thin_noisy_market'},
        text_evidence_assessment={'source_reliability': 'low', 'text_signal_strength': 'weak'},
        posterior_update={'suggested_posterior': 0.08},
        workflow_policy={'decision': 'partial_only'},
        news_context={'news': []},
        transcript_intelligence={'chunks': []},
    )
    assert block['alternative_hypotheses']
    assert isinstance(block['key_assumption'], str)
    assert isinstance(block['disconfirming_indicator'], str)
    assert 'fresh event-specific news evidence' in block['missing_evidence']
