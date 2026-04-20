from __future__ import annotations

from mentions_domain.normalize import ensure_dict, ensure_list, normalize_confidence


def fuse_evidence_bundle(query: str, frame: dict, bundle: dict) -> dict:
    frame = ensure_dict(frame)
    bundle = ensure_dict(bundle)

    market = ensure_dict(bundle.get('market', {}))
    news_context = ensure_dict(bundle.get('news_context', {}))
    transcript_intelligence = ensure_dict(bundle.get('transcript_intelligence', {}))
    workflow_policy = ensure_dict(bundle.get('workflow_policy', {}))
    pmt_knowledge = ensure_dict(bundle.get('pmt_knowledge', {}))
    selected_pmt_evidence = ensure_dict(bundle.get('selected_pmt_evidence', {}))
    text_evidence_assessment = ensure_dict(bundle.get('text_evidence_assessment', {}))
    posterior_update = ensure_dict(bundle.get('posterior_update', {}))
    challenge_block = ensure_dict(bundle.get('challenge_block', {}))
    market_prior = ensure_dict(bundle.get('market_prior', {}))

    live_market_evidence = {
        'kind': 'live_market_evidence',
        'priority': 'primary',
        'confidence': _market_confidence(market),
        'freshness': 'live' if ensure_dict(market.get('market_data', {})) else 'unavailable',
        'items': [market] if market else [],
    }
    news_evidence = {
        'kind': 'news_evidence',
        'priority': 'primary' if news_context.get('sufficiency') == 'sufficient' else 'secondary',
        'confidence': normalize_confidence(news_context.get('freshness', 'low')),
        'freshness': news_context.get('freshness', 'unknown'),
        'items': ensure_list(news_context.get('news', [])),
        'summary': news_context.get('summary', ''),
    }
    transcript_evidence = {
        'kind': 'transcript_evidence',
        'priority': 'secondary',
        'confidence': _transcript_confidence(transcript_intelligence),
        'freshness': 'historical',
        'items': ensure_list(transcript_intelligence.get('chunks', [])),
        'summary': transcript_intelligence.get('summary', ''),
    }
    historical_pmt_evidence = {
        'kind': 'historical_pmt_evidence',
        'priority': 'secondary',
        'confidence': _pmt_confidence(pmt_knowledge),
        'freshness': 'historical',
        'items': _flatten_pmt_items(pmt_knowledge),
    }
    derived_knowledge = {
        'kind': 'derived_knowledge',
        'priority': 'secondary',
        'confidence': _derived_confidence(transcript_intelligence),
        'freshness': 'derived',
        'items': _derived_items(transcript_intelligence),
    }

    conflicts = _detect_conflicts(news_context, transcript_intelligence, workflow_policy, market_prior)
    coverage = _coverage_snapshot(live_market_evidence, news_evidence, transcript_evidence, historical_pmt_evidence, derived_knowledge)
    source_quality_mix = _source_quality_mix(live_market_evidence, news_evidence, transcript_evidence, historical_pmt_evidence)

    fused = {
        'query': query,
        'route': frame.get('route', ''),
        'policy_state': workflow_policy.get('decision', ''),
        'market_prior': market_prior,
        'selected_pmt_evidence': selected_pmt_evidence,
        'text_evidence_assessment': text_evidence_assessment,
        'posterior_update': posterior_update,
        'challenge_block': challenge_block,
        'primary_evidence': [live_market_evidence, news_evidence],
        'secondary_evidence': [transcript_evidence, historical_pmt_evidence, derived_knowledge],
        'conflicts': conflicts,
        'coverage': coverage,
        'source_quality_mix': source_quality_mix,
        'summary': _build_summary(live_market_evidence, news_evidence, transcript_evidence, historical_pmt_evidence, conflicts, coverage),
    }
    return fused


def _market_confidence(market: dict) -> str:
    if ensure_dict(market.get('market_data', {})):
        return 'high'
    return 'low'


def _transcript_confidence(transcript_intelligence: dict) -> str:
    chunks = ensure_list(transcript_intelligence.get('chunks', []))
    if len(chunks) >= 3:
        return 'medium'
    if chunks:
        return 'low'
    return 'low'


def _pmt_confidence(pmt_knowledge: dict) -> str:
    count = len(_flatten_pmt_items(pmt_knowledge))
    if count >= 4:
        return 'medium'
    if count >= 1:
        return 'low'
    return 'low'


def _derived_confidence(transcript_intelligence: dict) -> str:
    kb = ensure_dict(transcript_intelligence.get('knowledge_bundle', {}))
    return 'medium' if kb else 'low'


def _flatten_pmt_items(pmt_knowledge: dict) -> list[dict]:
    items = []
    for key in ['pricing_signals', 'execution_patterns', 'phase_logic', 'crowd_mistakes', 'decision_cases', 'speaker_profiles']:
        for row in ensure_list(pmt_knowledge.get(key, []))[:2]:
            if isinstance(row, dict):
                enriched = dict(row)
                enriched['_kind'] = key
                items.append(enriched)
    return items[:12]


def _derived_items(transcript_intelligence: dict) -> list[dict]:
    kb = ensure_dict(transcript_intelligence.get('knowledge_bundle', {}))
    items = []
    for key, value in kb.items():
        if value:
            items.append({'kind': key, 'value': value})
    return items[:8]


def _detect_conflicts(news_context: dict, transcript_intelligence: dict, workflow_policy: dict, market_prior: dict) -> list[str]:
    conflicts = []
    if workflow_policy.get('decision') == 'partial_only' and news_context.get('sufficiency') != 'sufficient':
        conflicts.append('news-insufficient-for-full-analysis')
    if workflow_policy.get('decision') == 'clarify':
        conflicts.append('market-linkage-unclear')
    if transcript_intelligence.get('status') in ('empty', 'error'):
        conflicts.append('transcript-support-missing')
    if market_prior.get('prior_quality') in ('fragile', 'quoted_only'):
        conflicts.append(f"prior-quality-{market_prior.get('prior_quality')}")
    return conflicts


def _coverage_snapshot(live_market_evidence: dict, news_evidence: dict, transcript_evidence: dict, historical_pmt_evidence: dict, derived_knowledge: dict) -> dict:
    return {
        'has_live_market': bool(live_market_evidence.get('items')),
        'has_news': bool(news_evidence.get('items')),
        'has_transcripts': bool(transcript_evidence.get('items')),
        'has_historical_pmt': bool(historical_pmt_evidence.get('items')),
        'has_derived_knowledge': bool(derived_knowledge.get('items')),
    }


def _source_quality_mix(live_market_evidence: dict, news_evidence: dict, transcript_evidence: dict, historical_pmt_evidence: dict) -> dict:
    return {
        'market_confidence': live_market_evidence.get('confidence', 'low'),
        'news_confidence': news_evidence.get('confidence', 'low'),
        'transcript_confidence': transcript_evidence.get('confidence', 'low'),
        'historical_confidence': historical_pmt_evidence.get('confidence', 'low'),
    }


def _build_summary(live_market_evidence: dict, news_evidence: dict, transcript_evidence: dict, historical_pmt_evidence: dict, conflicts: list[str], coverage: dict) -> dict:
    return {
        'available_sections': [section.get('kind', '') for section in [live_market_evidence, news_evidence, transcript_evidence, historical_pmt_evidence] if section.get('items')],
        'primary_count': sum(len(section.get('items', [])) for section in [live_market_evidence, news_evidence]),
        'secondary_count': sum(len(section.get('items', [])) for section in [transcript_evidence, historical_pmt_evidence]),
        'conflict_count': len(conflicts),
        'coverage_score': sum(1 for present in coverage.values() if present),
    }
