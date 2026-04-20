from __future__ import annotations


def test_build_transcript_trace_keeps_candidate_provenance():
    from agents.mentions.workflows.synthesize_speaker import _build_transcript_trace

    transcript_bundle = {
        'support_shape': 'core-led',
        'top_candidates': [
            {
                'transcript_id': 42,
                'event_title': 'Trump Interview',
                'family': 'war_geopolitics',
                'evidence_type': 'core',
                'quote': 'Iran came up repeatedly.',
                'relevance_score': 0.91,
                'trace': {
                    'transcript_id': 42,
                    'segment_index': 7,
                    'source': 'youtube',
                    'source_ref': 'https://example.com/transcript/42',
                    'event_title': 'Trump Interview',
                    'event_date': '2026-04-01',
                    'start_ts': 12.5,
                    'end_ts': 20.0,
                },
            },
        ],
        'core_hits': [
            {
                'transcript_id': 42,
                'event_title': 'Trump Interview',
                'family': 'war_geopolitics',
                'evidence_type': 'core',
                'quote': 'Iran came up repeatedly.',
                'relevance_score': 0.91,
                'trace': {
                    'transcript_id': 42,
                    'segment_index': 7,
                    'source': 'youtube',
                    'source_ref': 'https://example.com/transcript/42',
                    'event_title': 'Trump Interview',
                    'event_date': '2026-04-01',
                },
            },
        ],
        'spillover_hits': [],
        'generic_regime_hits': [],
        'media_analogs': [],
    }

    trace = _build_transcript_trace(transcript_bundle)
    assert trace['support_shape'] == 'core-led'
    assert trace['lead_candidate']['transcript_id'] == 42
    assert trace['lead_candidate']['trace']['segment_index'] == 7
    assert trace['lead_candidate']['trace']['source_ref'] == 'https://example.com/transcript/42'
    assert trace['core_hits'][0]['family'] == 'war_geopolitics'


def test_evidence_view_exposes_lead_transcript_trace():
    from agents.mentions.workflows.synthesize_speaker import _build_evidence_view

    transcript_bundle = {
        'top_candidates': [
            {
                'event_title': 'Trump Interview',
                'trace': {
                    'transcript_id': 42,
                    'segment_index': 7,
                    'source': 'youtube',
                    'source_ref': 'https://example.com/transcript/42',
                },
            },
        ],
        'support_shape': 'core-led',
    }

    evidence_view = _build_evidence_view([], transcript_bundle, {})
    assert evidence_view['lead_transcript']['event_title'] == 'Trump Interview'
    assert evidence_view['lead_transcript_trace']['transcript_id'] == 42
    assert evidence_view['lead_transcript_trace']['source'] == 'youtube'
