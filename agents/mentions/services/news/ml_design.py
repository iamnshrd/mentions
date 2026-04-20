from __future__ import annotations


NEWS_ML_DESIGN_V0 = {
    'goal': 'Move news_context from heuristic relevance filtering toward ML-backed typed event-context scoring.',
    'evidence_types': [
        'event_core',
        'topic_expansion',
        'ambient_regime',
    ],
    'news_families': {
        'direct_event_coverage': {
            'description': 'Coverage directly about the event itself, venue, speech, or immediate planned remarks.',
            'expected_evidence_type': 'event_core',
        },
        'policy_rollout': {
            'description': 'Coverage framing the event as a policy rollout or issue announcement.',
            'expected_evidence_type': 'event_core',
        },
        'broader_economy_regime': {
            'description': 'Coverage that broadens the event into economy, inflation, jobs, prices, or general macro framing.',
            'expected_evidence_type': 'ambient_regime',
        },
        'opposition_media_reaction': {
            'description': 'Coverage centered on reactions, opponents, criticism, or media framing rather than the event core itself.',
            'expected_evidence_type': 'topic_expansion',
        },
        'geopolitics_ambient': {
            'description': 'Coverage that pulls the event into broader war/geopolitical framing without making that the event core.',
            'expected_evidence_type': 'ambient_regime',
        },
        'local_event_logistics': {
            'description': 'Local reporting on venue, attendance, no-shows, scheduling, logistics, and on-the-ground event setup.',
            'expected_evidence_type': 'event_core',
        },
    },
    'worker_extension': {
        'new_endpoint': '/news-score',
        'input': ['query', 'event_title', 'family', 'articles'],
        'output': ['score', 'family', 'evidence_type'],
    },
    'vps_side_plan': {
        'client': 'Add news_score(...) to the remote worker client.',
        'bundle_shape': ['core_news', 'expansion_news', 'ambient_news'],
        'analysis_usage': [
            'Use typed news evidence to improve event grounding.',
            'Use topic_expansion vs ambient_regime to sharpen market_flattens.',
            'Fuse news-side and transcript-side evidence types in interpretation.',
        ],
    },
}
