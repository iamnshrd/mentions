from agents.mentions.storage.runtime_db import bootstrap_runtime_db, insert_transcript_knowledge_artifacts, upsert_transcript
from agents.mentions.storage.runtime_query import get_transcript_knowledge_artifacts, get_transcript_knowledge_bundle


def test_transcript_knowledge_query_reads_back_artifacts(tmp_path):
    db_path = tmp_path / 'mentions_runtime.db'
    bootstrap_runtime_db(db_path)
    transcript_id = upsert_transcript('manual', 'tkq-1', title='Transcript', speaker_name='Donald Trump', raw_text='text', path=db_path)
    insert_transcript_knowledge_artifacts(
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

    pricing = get_transcript_knowledge_artifacts(query='fair value', category='pricing_signals', path=db_path)
    bundle = get_transcript_knowledge_bundle(query='fair value', speaker='Donald Trump', path=db_path)

    assert pricing[0]['category'] == 'pricing_signals'
    assert pricing[0]['speaker'] == 'Donald Trump'
    assert bundle['selected']['pricing_signals'][0]['category'] == 'pricing_signals'
