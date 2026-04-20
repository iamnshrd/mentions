from __future__ import annotations

from mentions_domain.normalize import ensure_dict, ensure_list


def build_debug_view(synthesis: dict) -> dict:
    synthesis = ensure_dict(synthesis)
    evidence_debug = ensure_dict(synthesis.get('evidence_debug', {}))
    source_summary = ensure_dict(evidence_debug.get('source_summary', {}))
    runtime_health = ensure_dict(evidence_debug.get('runtime_health', {}))
    context_risks = ensure_dict(evidence_debug.get('context_risks', {}))
    transcript_trace = ensure_dict(evidence_debug.get('transcript_trace', {}))
    news_trace = ensure_dict(evidence_debug.get('news_trace', {}))

    return {
        'summary': {
            'sources_used': ensure_list(source_summary.get('sources_used', [])),
            'news_count': int(source_summary.get('news_count', 0) or 0),
            'transcript_count': int(source_summary.get('transcript_count', 0) or 0),
            'has_market_data': bool(source_summary.get('has_market_data', False)),
            'has_history': bool(source_summary.get('has_history', False)),
        },
        'runtime_health': runtime_health,
        'context_risks': {
            'news': ensure_list(context_risks.get('news', [])),
            'transcripts': ensure_list(context_risks.get('transcripts', [])),
        },
        'top_evidence': {
            'lead_transcript': ensure_dict(transcript_trace.get('lead_candidate', {})),
            'transcript_candidates': ensure_list(transcript_trace.get('top_candidates', []))[:3],
            'retrieval_hits': ensure_list(transcript_trace.get('retrieval_hits', []))[:3],
            'news_items': ensure_list(news_trace.get('items', []))[:3],
        },
        'status': {
            'news': {
                'status': news_trace.get('status', ''),
                'freshness': news_trace.get('freshness', ''),
                'sufficiency': news_trace.get('sufficiency', ''),
            },
        },
    }


def render_debug_view_text(synthesis: dict) -> str:
    debug_view = build_debug_view(synthesis)
    summary = ensure_dict(debug_view.get('summary', {}))
    runtime_health = ensure_dict(debug_view.get('runtime_health', {}))
    context_risks = ensure_dict(debug_view.get('context_risks', {}))
    top_evidence = ensure_dict(debug_view.get('top_evidence', {}))
    status = ensure_dict(debug_view.get('status', {}))
    lines = ['Debug View', '─' * 48]
    lines.append(
        'Sources: '
        + ', '.join(summary.get('sources_used', []) or ['none'])
    )
    lines.append(
        f"Counts: news={summary.get('news_count', 0)} | transcripts={summary.get('transcript_count', 0)}"
    )
    if runtime_health:
        for name, payload in runtime_health.items():
            payload = ensure_dict(payload)
            lines.append(
                f"Runtime health [{name}]: {payload.get('status', 'unknown')} ({payload.get('contract', '')})"
            )
    news_risks = ensure_list(context_risks.get('news', []))
    transcript_risks = ensure_list(context_risks.get('transcripts', []))
    if news_risks:
        lines.append('News risks: ' + ', '.join(news_risks))
    if transcript_risks:
        lines.append('Transcript risks: ' + ', '.join(transcript_risks))
    lead_transcript = ensure_dict(top_evidence.get('lead_transcript', {}))
    if lead_transcript:
        lines.append(
            'Lead transcript: '
            + ', '.join(
                str(part)
                for part in [
                    lead_transcript.get('transcript_id', ''),
                    lead_transcript.get('segment_index', ''),
                    lead_transcript.get('source_ref', '') or lead_transcript.get('source_file', ''),
                ]
                if part not in ('', None)
            )
        )
    news_items = ensure_list(top_evidence.get('news_items', []))
    if news_items:
        headline = ensure_dict(news_items[0]).get('headline', '')
        if headline:
            lines.append(f'Lead news: {headline}')
    news_status = ensure_dict(status.get('news', {}))
    if news_status:
        lines.append(
            'News status: '
            + ' | '.join(
                part for part in [
                    news_status.get('status', ''),
                    news_status.get('freshness', ''),
                    news_status.get('sufficiency', ''),
                ] if part
            )
        )
    return '\n'.join(line for line in lines if line)
