from __future__ import annotations


def test_transcript_intelligence_candidates_include_trace(monkeypatch):
    from agents.mentions.services.transcripts.intelligence import (
        build_transcript_intelligence_bundle,
    )

    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence.extract_market_entities',
        lambda query: {'speakers': ['Donald Trump']},
    )
    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence.search_transcripts_runtime',
        lambda query='', speaker='', title_query='', limit=10: [
            {
                'transcript_id': 42,
                'event_title': 'Trump Interview',
                'event_key': 'trump-interview',
                'speaker': 'Donald Trump',
                'source': 'youtube',
                'source_ref': 'https://example.com/transcript/42',
                'event_date': '2026-04-01',
                'segment_index': 7,
                'text': 'Iran came up repeatedly in the interview.',
                'start_ts': 12.5,
                'end_ts': 20.0,
            },
        ],
    )
    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence.retrieve_family_segments',
        lambda transcript_id, family, limit=5: {
            'selected_results': [
                {
                    'score': 0.91,
                    'text': 'Iran came up repeatedly in the interview.',
                    'transcript_id': transcript_id,
                    'segment_index': 7,
                    'source': 'youtube',
                    'source_ref': 'https://example.com/transcript/42',
                    'event_title': 'Trump Interview',
                    'event_date': '2026-04-01',
                    'start_ts': 12.5,
                    'end_ts': 20.0,
                    'metadata': {'speaker_id': 1},
                },
            ],
            'mode': 'semantic_hybrid',
        },
    )
    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence.remote_family_score',
        lambda **kwargs: {},
    )

    bundle = build_transcript_intelligence_bundle('Will Trump mention Iran?')
    assert bundle['status'] == 'ok'
    assert bundle['top_candidates']

    trace = bundle['top_candidates'][0]['trace']
    assert trace['transcript_id'] == 42
    assert trace['segment_index'] == 7
    assert trace['source'] == 'youtube'
    assert trace['source_ref'] == 'https://example.com/transcript/42'
    assert trace['event_title'] == 'Trump Interview'
    assert trace['event_date'] == '2026-04-01'
    assert trace['start_ts'] == 12.5
    assert trace['end_ts'] == 20.0
