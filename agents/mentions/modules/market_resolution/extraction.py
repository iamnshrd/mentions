from __future__ import annotations

KNOWN_SPEAKERS = {
    'trump': 'Donald Trump',
    'donald trump': 'Donald Trump',
    'powell': 'Jerome Powell',
    'jerome powell': 'Jerome Powell',
    'biden': 'Joe Biden',
    'lagarde': 'Christine Lagarde',
    'musk': 'Elon Musk',
    'zelensky': 'Volodymyr Zelensky',
    'putin': 'Vladimir Putin',
    'press secretary': 'White House Press Secretary',
    'white house press secretary': 'White House Press Secretary',
    'press sec': 'White House Press Secretary',
}

KNOWN_TOPICS = [
    'iran', 'fed', 'rates', 'inflation', 'bitcoin', 'crypto', 'tariffs',
    'ukraine', 'china', 'oil', 'recession', 'war', 'tax', 'tips',
]

KNOWN_EVENT_TYPES = [
    'mention', 'speech', 'press conference', 'presser', 'interview',
    'statement', 'briefing', 'testimony', 'roundtable', 'meeting', 'announcement',
]


def extract_market_entities(query: str) -> dict:
    q = (query or '').lower()
    speakers = [canonical for key, canonical in KNOWN_SPEAKERS.items() if key in q]
    topics = [topic for topic in KNOWN_TOPICS if topic in q]
    event_types = [etype for etype in KNOWN_EVENT_TYPES if etype in q]

    deduped_speakers = []
    seen = set()
    for speaker in speakers:
        if speaker in seen:
            continue
        seen.add(speaker)
        deduped_speakers.append(speaker)

    if 'no tax on tips' in q:
        for topic in ['tax', 'tips']:
            if topic not in topics:
                topics.append(topic)

    return {
        'speakers': deduped_speakers,
        'topics': topics,
        'event_types': event_types,
        'is_mention_style': 'mention' in q or 'will say' in q or 'will address' in q,
    }
