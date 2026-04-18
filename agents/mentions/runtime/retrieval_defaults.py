from __future__ import annotations


def empty_transcript_bundle(query: str, speaker: str = '', status: str = 'skipped', risk: str = 'transcript-not-needed') -> dict:
    return {
        'query': query,
        'speaker': speaker,
        'status': status,
        'risk': risk,
        'chunks': [],
        'context': '',
        'tendency': '',
        'top_candidates': [],
        'query_target': query,
        'speaker_context': {
            'speaker': speaker,
            'same_speaker_hits': 0,
            'support_strength': 'none',
            'tendency_summary': 'No transcript evidence available.',
        },
        'format_analogs': [],
        'topic_analogs': [],
        'counterevidence': [],
        'retrieval_summary': 'No transcript retrieval attempted.',
    }



def empty_news_bundle(query: str, category: str = 'general') -> dict:
    return {
        'query': query,
        'category': category,
        'status': 'unavailable',
        'news': [],
        'top_headlines': [],
        'provider_status': 'unavailable',
        'typed_news': {},
        'core_news': [],
        'expansion_news': [],
        'ambient_news': [],
    }
