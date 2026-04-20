from agents.mentions.services.speakers.event_retrieval import retrieve_relevant_speaker_events


def test_speaker_event_retrieval_prefers_tagged_topic_and_format_matches(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.speakers.event_retrieval.search_transcript_tags_runtime',
        lambda speaker='', topic_tags=None, format_tags=None, limit=10: [
            {
                'event_title': 'Press Briefing A',
                'topic_tags': ['iran'],
                'topic_family_tags': [],
                'format_tags': ['press-conference', 'q-and-a'],
                'tagging_confidence': 0.9,
            }
        ],
    )
    monkeypatch.setattr(
        'agents.mentions.services.speakers.event_retrieval.search_transcripts_runtime',
        lambda query='', speaker='', limit=10: [
            {
                'event_title': 'Press Briefing A',
                'text': 'Iran came up in the press briefing and several questions followed.',
                'speaker': 'Donald Trump',
            }
        ],
    )

    result = retrieve_relevant_speaker_events(
        'Will Trump mention Iran in a press conference?',
        {'speaker': 'Donald Trump'},
        {},
    )
    assert result['status'] == 'ok'
    assert result['events'][0]['event_title'] == 'Press Briefing A'
    assert result['events'][0]['format_matches']
    assert result['events'][0]['relevance_score'] > 3


def test_speaker_event_retrieval_rejects_format_mismatch(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.speakers.event_retrieval.search_transcript_tags_runtime',
        lambda speaker='', topic_tags=None, format_tags=None, limit=10: [],
    )
    monkeypatch.setattr(
        'agents.mentions.services.speakers.event_retrieval.search_transcripts_runtime',
        lambda query='', speaker='', limit=10: [
            {
                'event_title': 'TV Interview',
                'text': 'Iran came up in the interview.',
                'speaker': 'Donald Trump',
            }
        ],
    )

    result = retrieve_relevant_speaker_events(
        'Will Trump mention Iran in a press conference?',
        {'speaker': 'Donald Trump'},
        {},
    )
    assert result['status'] == 'empty'
    assert any(item['reason'] == 'format-mismatch' for item in result['rejection_reasons'])
