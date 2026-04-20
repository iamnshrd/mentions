from __future__ import annotations


def empty_transcript_context(query: str, speaker: str = '', status: str = 'skipped', risk: str = 'transcript-not-needed') -> dict:
    return {
        'query': query,
        'speaker': speaker,
        'status': status,
        'chunks': [],
        'summary': '',
        'top_speakers': [],
        'top_events': [],
        'context_risks': [risk] if risk else [],
    }



def empty_news_context(query: str, category: str, risk: str = 'news-fetch-failed') -> dict:
    return {
        'query': query,
        'category': category,
        'status': 'unavailable',
        'freshness': 'missing',
        'sufficiency': 'weak',
        'news': [],
        'summary': '',
        'event_context': {},
        'paths': {'direct': [], 'weak': [], 'late': []},
        'context_risks': [risk] if risk else [],
    }
