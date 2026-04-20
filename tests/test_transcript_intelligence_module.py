from mentions_domain.market_resolution import extract_market_entities
from agents.mentions.services.transcripts.intelligence_heuristic import build_transcript_intelligence_bundle


def test_transcript_intelligence_empty(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence_heuristic.search_transcripts',
        lambda query, limit=5, speaker='': [],
    )
    bundle = build_transcript_intelligence_bundle('Will Trump mention Iran?')
    assert bundle['status'] == 'empty'
    assert 'no-transcript-hits' in bundle['context_risks']


def test_transcript_intelligence_infers_speaker_and_summarizes(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence_heuristic.search_transcripts',
        lambda query, limit=5, speaker='': [
            {'speaker': 'Donald Trump', 'event': 'Interview', 'text': 'Iran came up repeatedly in the conversation.'},
            {'speaker': 'Donald Trump', 'event': 'Interview', 'text': 'He returned to the topic later.'},
        ],
    )
    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence_heuristic.search_transcripts_runtime',
        lambda query='', speaker='', limit=10: [],
    )
    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence_heuristic.search_transcript_tags_runtime',
        lambda speaker='', topic_tags=None, format_tags=None, limit=10: [],
    )
    bundle = build_transcript_intelligence_bundle('Will Trump mention Iran?')
    assert bundle['status'] == 'ok'
    assert bundle['speaker'] == 'Donald Trump'
    assert 'Iran came up repeatedly' in bundle['summary']
    assert bundle['top_speakers'][0] == 'Donald Trump'


def test_market_entity_extraction_keeps_roundtable_tax_tips():
    entities = extract_market_entities('Donald Trump roundtable no tax on tips')
    assert 'roundtable' in entities['event_types']
    assert 'tax' in entities['topics']
    assert 'tips' in entities['topics']


def test_transcript_intelligence_filters_topic_mismatch(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence_heuristic.search_transcript_tags_runtime',
        lambda speaker='', topic_tags=None, format_tags=None, limit=10: [],
    )
    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence_heuristic.search_transcripts_runtime',
        lambda query='', speaker='', limit=10: [],
    )
    monkeypatch.setattr(
        'agents.mentions.services.transcripts.intelligence_heuristic.search_transcripts',
        lambda query, limit=5, speaker='': [
            {'speaker': 'Donald Trump', 'event': 'Interview', 'text': 'Tariffs came up repeatedly in the conversation.'},
        ],
    )
    bundle = build_transcript_intelligence_bundle('Will Trump mention Iran?')
    assert bundle['status'] == 'empty'
    assert 'no-transcript-hits' in bundle['context_risks']
