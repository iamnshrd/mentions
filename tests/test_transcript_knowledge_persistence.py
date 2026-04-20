from agents.mentions.storage.runtime_db import (
    bootstrap_runtime_db,
    connect_runtime_db,
    insert_transcript_knowledge_artifacts,
    upsert_transcript,
)


def test_transcript_knowledge_artifacts_persist(tmp_path):
    db_path = tmp_path / 'mentions_runtime.db'
    bootstrap_runtime_db(db_path)
    transcript_id = upsert_transcript(
        source='manual',
        source_ref='tk-1',
        title='Transcript',
        speaker_name='Donald Trump',
        raw_text='text',
        path=db_path,
    )
    inserted = insert_transcript_knowledge_artifacts(
        transcript_id,
        {
            'candidates': {
                'pricing_signals': [
                    {'speaker': 'Donald Trump', 'score': 3, 'hits': ['fair value'], 'text': 'fair value text'}
                ],
                'execution_patterns': [
                    {'speaker': 'Donald Trump', 'score': 2, 'hits': ['limit order'], 'text': 'limit order text'}
                ],
            }
        },
        speaker_name='Donald Trump',
        event_key='KXTRUMPMENTION-26APR15',
        path=db_path,
    )
    assert inserted == 2
    with connect_runtime_db(db_path) as conn:
        count = conn.execute('SELECT COUNT(*) AS c FROM transcript_knowledge_artifacts').fetchone()['c']
    assert count == 2
