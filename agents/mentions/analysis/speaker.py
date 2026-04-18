"""Speaker pattern analysis — extract relevant context from transcript corpus."""
from __future__ import annotations

import logging

log = logging.getLogger('mentions')


def extract_speaker_context(transcript_chunks: list[dict],
                             query: str) -> str:
    """Synthesize a text summary of relevant speaker context from transcript chunks.

    *transcript_chunks* is the list returned by retrieve_transcripts().
    Returns a concise text summary, or empty string if no relevant chunks.
    """
    if not transcript_chunks:
        return ''

    # Group chunks by speaker
    by_speaker: dict[str, list[str]] = {}
    for chunk in transcript_chunks:
        speaker = chunk.get('speaker', 'Unknown')
        text = chunk.get('text', '').strip()
        if text:
            by_speaker.setdefault(speaker, []).append(text)

    if not by_speaker:
        return ''

    parts = []
    for speaker, texts in list(by_speaker.items())[:3]:  # max 3 speakers
        excerpt = _best_excerpt(texts, query)
        if excerpt:
            label = f'{speaker}:' if speaker and speaker != 'Unknown' else 'Transcript:'
            parts.append(f'{label} "{excerpt}"')

    return '\n\n'.join(parts)



def _best_excerpt(texts: list[str], query: str) -> str:
    """Select the most relevant excerpt for *query* from a list of texts."""
    if not texts:
        return ''
    q_words = set(query.lower().split())
    scored = []
    for text in texts:
        t_lower = text.lower()
        score = sum(1 for w in q_words if w in t_lower)
        scored.append((score, text))
    scored.sort(key=lambda x: -x[0])
    best = scored[0][1]
    # Truncate to ~200 chars at sentence boundary
    if len(best) > 200:
        cutoff = best[:200].rfind('. ')
        if cutoff > 100:
            best = best[:cutoff + 1]
        else:
            best = best[:200] + '…'
    return best


