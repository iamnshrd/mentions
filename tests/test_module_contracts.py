from agents.mentions.module_contracts import ensure_dict, ensure_list, normalize_confidence, normalize_status


def test_normalize_status_and_confidence():
    assert normalize_status('OK') == 'ok'
    assert normalize_status('weird') == 'unavailable'
    assert normalize_confidence('HIGH') == 'high'
    assert normalize_confidence('strange') == 'low'


def test_ensure_dict_and_list():
    assert ensure_dict({'x': 1}) == {'x': 1}
    assert ensure_dict(None) == {}
    assert ensure_list([1, 2]) == [1, 2]
    assert ensure_list(None) == []
