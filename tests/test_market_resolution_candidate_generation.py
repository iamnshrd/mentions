from agents.mentions.modules.market_resolution import build_search_queries, merge_search_results


def test_build_search_queries_creates_reduced_variants():
    queries = build_search_queries('Will Trump mention Iran in a speech this week?')
    assert 'Will Trump mention Iran in a speech this week?' in queries
    assert 'donald trump iran mention' in [q.lower() for q in queries] or 'trump iran mention' in [q.lower() for q in queries]
    assert any('iran' in q.lower() for q in queries)
    assert any('speech' in q.lower() or 'mention' in q.lower() for q in queries)


def test_merge_search_results_dedupes_by_ticker():
    merged = merge_search_results([
        [{'ticker': 'AAA', 'title': 'one'}, {'ticker': 'BBB', 'title': 'two'}],
        [{'ticker': 'BBB', 'title': 'two-again'}, {'ticker': 'CCC', 'title': 'three'}],
    ])
    assert [row['ticker'] for row in merged] == ['AAA', 'BBB', 'CCC']
