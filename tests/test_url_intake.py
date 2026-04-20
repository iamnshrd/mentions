from agents.mentions.services.intake.intake import intake_market_input


def test_url_intake_for_kalshi_market_url():
    result = intake_market_input('https://kalshi.com/markets/kxtrumpmention/what-will-trump-say')
    assert result['input_type'] == 'kalshi_url'
    assert result['is_url'] is True
    assert result['series_slug'] == 'kxtrumpmention'


def test_url_intake_for_three_segment_kalshi_market_url():
    result = intake_market_input('https://kalshi.com/markets/kxmamdanimention/what-will-zohran-mamdani-say/kxmamdanimention-26apr15b')
    assert result['input_type'] == 'kalshi_url'
    assert result['pretty_slug'] == 'what-will-zohran-mamdani-say'
    assert result['ticker'] == 'KXMAMDANIMENTION-26APR15B'
    assert result['has_explicit_url_ticker'] is True


def test_url_intake_for_direct_ticker():
    result = intake_market_input('KXTRUMPMENTION-26APR15-IRAN')
    assert result['ticker'] == 'KXTRUMPMENTION-26APR15-IRAN'
    assert result['is_direct_ticker'] is True
