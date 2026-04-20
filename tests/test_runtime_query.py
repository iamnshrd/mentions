from agents.mentions.storage.runtime_db import (
    bootstrap_runtime_db,
    connect_runtime_db,
    insert_analysis_report,
    insert_market_snapshot,
    insert_resolution_run,
    upsert_news_item,
    upsert_transcript,
    replace_transcript_segments,
)
from agents.mentions.storage.runtime_query import (
    get_recent_analysis_reports,
    get_recent_market_snapshots,
    get_recent_resolution_runs,
    search_news_runtime,
    search_transcripts_runtime,
)


def test_runtime_query_reads_back_artifacts(tmp_path):
    db_path = tmp_path / 'mentions_runtime.db'
    bootstrap_runtime_db(db_path)

    insert_market_snapshot('KXTEST', {'ticker': 'KXTEST'}, [], {'market': 'ok'}, db_path)
    insert_resolution_run('test query', {'ticker': 'KXTEST', 'confidence': 'high', 'score_margin': 5, 'candidates': []}, {'filtered_market_count': 1}, db_path)
    insert_analysis_report('test query', 'KXTEST', {'decision': 'partial_only', 'output_mode': 'brief'}, {'market': {}}, {'confidence': 'low'}, 'render', {'kind': 'test'}, db_path)

    transcript_id = upsert_transcript('manual', 't1', title='Transcript', speaker_name='Donald Trump', raw_text='Iran mention', path=db_path)
    replace_transcript_segments(transcript_id, [{'speaker': 'Donald Trump', 'text': 'Iran mention', 'segment_index': 0}], path=db_path)
    upsert_news_item('newsapi', 'https://example.com/x', headline='Iran headline', body_text='Iran body', speaker_name='Donald Trump', path=db_path)

    assert get_recent_market_snapshots(path=db_path)[0]['ticker'] == 'KXTEST'
    assert get_recent_resolution_runs(path=db_path)[0]['resolved_ticker'] == 'KXTEST'
    assert get_recent_analysis_reports(path=db_path)[0]['ticker'] == 'KXTEST'
    assert search_transcripts_runtime(query='Iran', path=db_path)[0]['speaker'] == 'Donald Trump'
    assert search_news_runtime(query='Iran', path=db_path)[0]['headline'] == 'Iran headline'


def test_runtime_query_degrades_softly_on_partial_schema(tmp_path):
    db_path = tmp_path / 'broken_runtime.db'
    with connect_runtime_db(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE transcripts (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE transcript_segments (
                id INTEGER PRIMARY KEY,
                transcript_id INTEGER NOT NULL,
                segment_index INTEGER NOT NULL,
                text TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE news_items (
                id INTEGER PRIMARY KEY,
                headline TEXT NOT NULL DEFAULT ''
            );
            """
        )
        conn.commit()

    assert search_transcripts_runtime(query='Iran', path=db_path) == []
    assert search_news_runtime(query='Iran', path=db_path) == []
