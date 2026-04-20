"""Experimental clustering helper for transcript-family discovery.

Research/perimeter tooling only, not part of the current main runtime path.
"""
from __future__ import annotations

from collections import defaultdict


def discover_clusters(speaker: str = 'Donald Trump', sample_limit: int = 120, k: int = 8) -> dict:
    import numpy as np
    from sklearn.cluster import KMeans

    from agents.mentions.services.transcripts.semantic_retrieval.client import embed_texts
    from agents.mentions.eval.transcript_semantic_retrieval.corpus_discovery import sample_segments

    segments = sample_segments(speaker=speaker, limit=sample_limit)
    texts = [row.get('text', '') for row in segments if (row.get('text') or '').strip()]
    embed = embed_texts(texts)
    if embed.get('status') != 'ok':
        return {'status': 'error', 'error': embed}
    vectors = np.array(embed.get('vectors', []), dtype=float)
    if len(vectors) == 0:
        return {'status': 'empty', 'speaker': speaker}

    k = max(2, min(k, len(vectors)))
    model = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = model.fit_predict(vectors)

    grouped = defaultdict(list)
    for seg, label in zip(segments, labels):
        grouped[int(label)].append({
            'text': seg.get('text', ''),
            'title': seg.get('transcript_title', ''),
            'segment_index': seg.get('segment_index'),
        })

    clusters = []
    for label, rows in grouped.items():
        clusters.append({
            'cluster': label,
            'size': len(rows),
            'examples': rows[:3],
        })
    clusters.sort(key=lambda row: row['size'], reverse=True)
    return {
        'status': 'ok',
        'speaker': speaker,
        'sample_limit': sample_limit,
        'cluster_count': k,
        'clusters': clusters,
    }
