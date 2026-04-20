from agents.mentions.interfaces.capabilities.analysis.api import run_query


def test_analysis_query_returns_wording_wrapper():
    result = run_query('fed rate decision market')
    assert result['query'] == 'fed rate decision market'
    assert 'wording' in result
    assert 'response' in result
