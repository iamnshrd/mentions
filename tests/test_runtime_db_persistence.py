from agents.mentions.storage.runtime_db import (
    bootstrap_runtime_db,
    connect_runtime_db,
    link_document,
    replace_transcript_segments,
    upsert_event,
    upsert_news_item,
    upsert_speaker,
    upsert_topic,
    upsert_transcript,
)


def test_runtime_db_entity_and_document_persistence(tmp_path):
    db_path = tmp_path / 'mentions_runtime.db'
    bootstrap_runtime_db(db_path)

    speaker_id = upsert_speaker('Donald Trump', path=db_path)
    topic_id = upsert_topic('Iran', path=db_path)
    event_id = upsert_event('KXTRUMPMENTION-26APR15', title='Trump mention event', path=db_path)
    transcript_id = upsert_transcript(
        source='manual',
        source_ref='transcript-1',
        title='Interview',
        speaker_name='Donald Trump',
        event_key='KXTRUMPMENTION-26APR15',
        event_title='Trump mention event',
        raw_text='Full transcript text',
        path=db_path,
    )
    inserted_segments = replace_transcript_segments(
        transcript_id,
        [
            {'speaker': 'Donald Trump', 'text': 'Iran was mentioned.', 'segment_index': 0},
            {'speaker': 'Donald Trump', 'text': 'Another segment.', 'segment_index': 1},
        ],
        path=db_path,
    )
    news_id = upsert_news_item(
        source='newsapi',
        url='https://example.com/a',
        headline='Trump and Iran',
        body_text='Story body',
        speaker_name='Donald Trump',
        event_key='KXTRUMPMENTION-26APR15',
        path=db_path,
    )
    link_id = link_document('news_items', news_id, speaker_id=speaker_id, topic_id=topic_id, event_id=event_id, link_type='topic-mention', confidence=0.9, path=db_path)

    assert speaker_id > 0
    assert topic_id > 0
    assert event_id > 0
    assert transcript_id > 0
    assert inserted_segments == 2
    assert news_id > 0
    assert link_id > 0

    with connect_runtime_db(db_path) as conn:
        transcript_count = conn.execute('SELECT COUNT(*) AS c FROM transcripts').fetchone()['c']
        segment_count = conn.execute('SELECT COUNT(*) AS c FROM transcript_segments').fetchone()['c']
        news_count = conn.execute('SELECT COUNT(*) AS c FROM news_items').fetchone()['c']
        link_count = conn.execute('SELECT COUNT(*) AS c FROM document_links').fetchone()['c']

    assert transcript_count == 1
    assert segment_count == 2
    assert news_count == 1
    assert link_count == 1
