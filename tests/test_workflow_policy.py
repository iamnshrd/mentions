from agents.mentions.workflows.policy import evaluate_workflow_policy


def test_workflow_policy_allows_full_when_inputs_are_strong():
    decision = evaluate_workflow_policy(
        query='Will Trump mention Iran?',
        market_data={
            'resolved_market': {'ticker': 'KXTRUMPMENTION-IRAN', 'confidence': 'high', 'score_margin': 8},
            'sourcing': {'filtered_market_count': 1},
            'provider_status': {'market': 'ok'},
        },
        news_context={'status': 'live', 'sufficiency': 'strong'},
        transcript_intelligence={'status': 'ok'},
    )
    assert decision['decision'] == 'full'
    assert decision['output_mode'] == 'full_memo'
    assert decision['allow_trade_recommendation'] is True


def test_workflow_policy_downgrades_when_context_missing():
    decision = evaluate_workflow_policy(
        query='Will Trump mention Iran?',
        market_data={
            'resolved_market': {'ticker': 'KXTRUMPMENTION-IRAN', 'confidence': 'high', 'score_margin': 8},
            'sourcing': {'filtered_market_count': 1},
            'provider_status': {'market': 'ok'},
        },
        news_context={'status': 'unavailable', 'sufficiency': 'weak'},
        transcript_intelligence={'status': 'empty'},
    )
    assert decision['decision'] == 'partial_only'
    assert 'fresh-context-missing' in decision['reasons']
    assert decision['allow_trade_recommendation'] is False


def test_workflow_policy_clarify_when_resolution_weak():
    decision = evaluate_workflow_policy(
        query='Will Trump mention Iran?',
        market_data={
            'resolved_market': {'ticker': '', 'confidence': 'low', 'score_margin': 0},
            'sourcing': {'filtered_market_count': 3},
            'provider_status': {'market': 'unavailable'},
        },
        news_context={'status': 'live', 'sufficiency': 'strong'},
        transcript_intelligence={'status': 'ok'},
    )
    assert decision['decision'] == 'clarify'
    assert decision['output_mode'] == 'clarify'
    assert 'resolution-weak' in decision['reasons']
