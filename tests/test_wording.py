from agents.mentions.capabilities.wording.api import check_text


def test_wording_rewrite_event_read():
    result = check_text('Event read', apply_fixes=True, mode='safe')
    assert result['text'] == 'Разбор события'
    assert result['rewrite_count'] >= 1
