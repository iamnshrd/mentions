from agents.mentions.storage.runtime_db import (
    bootstrap_runtime_db,
    connect_runtime_db,
    get_runtime_health,
)


def test_runtime_db_bootstrap(tmp_path):
    db_path = tmp_path / 'mentions_runtime.db'
    bootstrap_runtime_db(db_path)
    with connect_runtime_db(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {row['name'] for row in rows}
    assert 'transcripts' in table_names
    assert 'news_items' in table_names
    assert 'market_snapshots' in table_names
    assert 'analysis_reports' in table_names
    health = get_runtime_health(db_path)
    assert health['status'] == 'ok'
    assert health['contracts']['transcript_search'] == {}
