from __future__ import annotations

from agents.mentions.runtime.media_detection import analyze_media_appearance


def build_topic_path_map(transcript_bundle: dict | None, event_ctx: dict | None) -> dict:
    transcript_bundle = transcript_bundle or {}
    event_ctx = event_ctx or {}

    likely_topics = [str(topic).strip() for topic in (event_ctx.get('likely_topics') or []) if str(topic).strip()]
    topic_paths = {
        'family_hits': [],
        'leading_paths': [],
        'dead_end_families': [],
        'path_support': 'weak',
        'family_quotes': [],
        'transition_hints': [],
        'family_evidence': [],
        'overextended_families': [],
        'late_branch_families': [],
    }

    rows = []
    seen = set()
    for evidence_type, key in [('core', 'core_hits'), ('spillover', 'spillover_hits'), ('generic_regime', 'generic_regime_hits')]:
        for row in transcript_bundle.get(key, []) or []:
            family = row.get('family') or ''
            quote = row.get('quote') or row.get('text') or ''
            if not family:
                continue
            sig = (family, quote)
            if sig in seen:
                continue
            seen.add(sig)
            rows.append({**row, 'evidence_type': evidence_type})

    family_support = {}
    family_quotes = []
    transition_hints = []
    for row in rows:
        family = row.get('family') or ''
        family_support[family] = family_support.get(family, 0) + (2.0 if row.get('evidence_type') == 'core' else 1.0 if row.get('evidence_type') == 'spillover' else 0.5)
        quote = (row.get('quote') or row.get('text') or '').strip()
        if quote:
            family_quotes.append({'family': family, 'quote': quote[:220], 'evidence_type': row.get('evidence_type', '')})
            lower_quote = quote.lower()
            for from_topic in likely_topics[:2]:
                from_lower = from_topic.lower()
                if from_lower and from_lower in lower_quote:
                    for to_family in ['geopolitical', 'policy_economic', 'event_native', 'weak_noisy']:
                        if to_family in lower_quote and to_family != from_lower:
                            transition_hints.append({
                                'from': from_topic,
                                'to': to_family,
                                'source': family,
                                'window': quote[:140],
                            })

    family_aliases = {
        'war_geopolitics': 'geopolitical',
        'border_immigration': 'geopolitical',
        'tariff_policy_legal': 'policy_economic',
        'trade_industry_manufacturing': 'policy_economic',
        'labor_service_workers': 'policy_economic',
        'broad_economy_prices': 'policy_economic',
        'opponents_media_attacks': 'culture_media',
        'gop_coalition_internal': 'political_opponents',
    }

    leading_paths = []
    family_evidence = []
    overextended_families = []
    late_branch_families = []
    dead_end_families = []
    core_family_names = {row.get('family') for row in (transcript_bundle.get('core_hits') or []) if row.get('family')}
    spill_family_names = {row.get('family') for row in (transcript_bundle.get('spillover_hits') or []) if row.get('family')}
    generic_family_names = {row.get('family') for row in (transcript_bundle.get('generic_regime_hits') or []) if row.get('family')}

    for family, support in sorted(family_support.items(), key=lambda item: item[1], reverse=True):
        bucket = family_aliases.get(family, family)
        topic_paths['family_hits'].append({'family': family, 'bucket': bucket, 'support': support})
        evidence_types = {
            'core': family in core_family_names,
            'spillover': family in spill_family_names,
            'generic_regime': family in generic_family_names,
        }
        family_evidence.append({
            'family': family,
            'bucket': bucket,
            'support': support,
            'evidence_types': evidence_types,
        })
        if support >= 2 and likely_topics:
            leading_paths.append({'from': likely_topics[0], 'to': bucket, 'strength': 'strong' if support >= 3 else 'medium'})
        if evidence_types['generic_regime'] and not evidence_types['core']:
            overextended_families.append(bucket)
        if evidence_types['spillover'] and not evidence_types['core']:
            late_branch_families.append(bucket)
        if support < 1.5:
            dead_end_families.append(bucket)

    topic_paths['leading_paths'] = leading_paths[:5]
    topic_paths['dead_end_families'] = list(dict.fromkeys(dead_end_families))[:5]
    topic_paths['family_quotes'] = family_quotes[:5]
    topic_paths['transition_hints'] = transition_hints[:5]
    topic_paths['family_evidence'] = family_evidence[:6]
    topic_paths['overextended_families'] = list(dict.fromkeys(overextended_families))[:5]
    topic_paths['late_branch_families'] = list(dict.fromkeys(late_branch_families))[:5]

    if any(row['support'] >= 3 for row in topic_paths['family_hits']):
        topic_paths['path_support'] = 'strong'
    elif topic_paths['family_hits']:
        topic_paths['path_support'] = 'partial'

    return topic_paths


def build_strike_baskets(strike_list: list[str], event_ctx: dict | None, transcript_bundle: dict | None, topic_paths: dict | None = None) -> dict:
    event_ctx = event_ctx or {}
    transcript_bundle = transcript_bundle or {}
    topic_paths = topic_paths or {}
    topics = [str(topic).strip() for topic in (event_ctx.get('likely_topics') or []) if str(topic).strip()]
    media_context = transcript_bundle.get('media_context') or {}
    is_media_case = bool(media_context)

    family_aliases = {
        'war_geopolitics': 'geopolitical',
        'border_immigration': 'geopolitical',
        'tariff_policy_legal': 'policy_economic',
        'trade_industry_manufacturing': 'policy_economic',
        'labor_service_workers': 'policy_economic',
        'broad_economy_prices': 'policy_economic',
        'opponents_media_attacks': 'culture_media',
        'gop_coalition_internal': 'political_opponents',
        'event_native': 'event_native',
    }

    score_rows = []
    for strike in strike_list or []:
        text = (strike or '').strip()
        if not text:
            continue
        lowered = text.lower()
        score = 0.0
        reasons = []
        families = []

        for topic in topics:
            if topic.lower() in lowered:
                score += 3.0
                reasons.append(f'прямое совпадение с темой события `{topic}`')
                families.append('event_native')

        if is_media_case and not topics:
            reasons.append('media-case guardrail: strike label сам по себе не считается event topic без отдельной path/event опоры')

        keyword_family_map = [
            (['iran', 'israel', 'ukraine', 'china', 'war', 'nato'], 'war_geopolitics', 2.5, 'геополитическая ветка'),
            (['tariff', 'trade', 'manufacturing', 'tax', 'tips', 'economy', 'prices'], 'trade_industry_manufacturing', 2.0, 'policy/economy ветка'),
            (['media', 'cnn', 'msnbc', 'fox', 'press'], 'opponents_media_attacks', 1.5, 'media/opponents ветка'),
            (['democrat', 'biden', 'harris', 'republican'], 'gop_coalition_internal', 1.5, 'coalition/politics ветка'),
            (['account', 'bitcoin', 'crypto'], 'weak_noisy', 0.5, 'слабая / branded ветка'),
        ]
        for keywords, family, weight, reason in keyword_family_map:
            if any(keyword in lowered for keyword in keywords):
                score += weight
                reasons.append(reason)
                families.append(family)

        family_hits = {row.get('family'): row for row in (topic_paths.get('family_hits') or []) if row.get('family')}
        for family in list(dict.fromkeys(families)):
            support_row = family_hits.get(family)
            if support_row:
                support = float(support_row.get('support') or 0)
                score += min(2.0, support)
                reasons.append(f'transcript family support: `{family}`')

        if not reasons:
            reasons.append('нет сильной transcript/event опоры')

        if is_media_case and not topics and families == ['event_native']:
            score = min(score, 0.5)

        bucket = 'weak'
        if score >= 4.5:
            bucket = 'core'
        elif score >= 2.0:
            bucket = 'late'

        score_rows.append({
            'strike': text,
            'score': round(score, 2),
            'bucket': bucket,
            'reasons': reasons,
            'families': list(dict.fromkeys(families)),
        })

    score_rows.sort(key=lambda row: row['score'], reverse=True)
    return {
        'core': [row['strike'] for row in score_rows if row['bucket'] == 'core'][:6],
        'late': [row['strike'] for row in score_rows if row['bucket'] == 'late'][:6],
        'weak': [row['strike'] for row in score_rows if row['bucket'] == 'weak'][:6],
        'score_rows': score_rows,
    }


def _event_structure(fmt: str) -> str:
    if fmt in {'panel', 'press_conference', 'interview'}:
        return 'semi-open'
    if fmt in {'speech', 'statement'}:
        return 'scripted'
    return 'mixed'


def _current_grounding(evidence_view: dict) -> str:
    news_contract = evidence_view.get('news_contract') or {}
    transcript_contract = evidence_view.get('transcript_contract') or {}
    coverage_state = (news_contract.get('coverage_state') or '').lower()
    support_shape = (transcript_contract.get('support_shape') or '').lower()
    top_news_count = evidence_view.get('top_news_count', 0)

    if coverage_state == 'event-led' and support_shape == 'core-led':
        return 'strong'
    if coverage_state in {'ambient-only', 'empty'} and support_shape in {'generic-only', 'empty'}:
        return 'weak'
    if coverage_state == 'topic-led' or support_shape == 'spillover-led':
        return 'partial'
    if top_news_count >= 2:
        return 'strong'
    if top_news_count == 1:
        return 'partial'
    return 'weak'


def _topic_centrality(likely_topics: list[str]) -> str:
    direct_topic_terms = {'no tax on tips', 'tax day', 'roundtable'}
    if likely_topics and any(topic.lower() in direct_topic_terms for topic in likely_topics):
        return 'core-topic'
    if likely_topics:
        return 'adjacent-topic'
    return 'weak-topic'


def _event_support_profile(event_ctx: dict, transcript_bundle: dict, evidence_view: dict) -> dict:
    likely_topics = [str(topic).strip() for topic in (event_ctx.get('likely_topics') or []) if str(topic).strip()]
    fmt = (event_ctx.get('format') or '').lower()
    qa = (event_ctx.get('qa_likelihood') or '').lower()
    media_context = analyze_media_appearance(event_ctx)

    event_structure = _event_structure(fmt)
    current_grounding = _current_grounding(evidence_view)
    topic_centrality = _topic_centrality(likely_topics)

    core_hits = transcript_bundle.get('core_hits') or []
    spillover_hits = transcript_bundle.get('spillover_hits') or []
    generic_regime_hits = transcript_bundle.get('generic_regime_hits') or []
    weak_hits = transcript_bundle.get('weak_hits') or []

    if core_hits:
        historical_support = 'strong'
    elif spillover_hits:
        historical_support = 'partial'
    elif generic_regime_hits:
        historical_support = 'weak-regime'
    else:
        historical_support = 'weak'

    path_mode = 'transcript_backed'
    event_prior_mode = 'default'
    if not (core_hits or spillover_hits or generic_regime_hits):
        path_mode = 'event_prior_fallback'
        title = ((event_ctx.get('event_title') or event_ctx.get('title') or '')).lower()
        if 'briefing' in title or fmt == 'press_conference':
            event_prior_mode = 'press_briefing'
        elif 'fox news sunday' in title:
            event_prior_mode = 'sunday_show_interview'
        elif 'interview' in title or fmt == 'interview':
            event_prior_mode = 'interview'
        elif 'dinner' in title:
            event_prior_mode = 'dinner_media_room'
        elif 'turning point' in title or 'conference' in title:
            event_prior_mode = 'conference_coalition'
        elif fmt == 'speech':
            event_prior_mode = 'scripted_speech'

    if media_context:
        path_mode = 'media_appearance_framework'
        event_prior_mode = media_context.get('media_event_type', event_prior_mode)

    return {
        'likely_topics': likely_topics,
        'fmt': fmt,
        'qa': qa,
        'media_context': media_context,
        'event_structure': event_structure,
        'current_grounding': current_grounding,
        'topic_centrality': topic_centrality,
        'core_hits': core_hits,
        'spillover_hits': spillover_hits,
        'generic_regime_hits': generic_regime_hits,
        'weak_hits': weak_hits,
        'historical_support': historical_support,
        'path_mode': path_mode,
        'event_prior_mode': event_prior_mode,
    }


def build_interpretation_block(event_ctx: dict | None, transcript_bundle: dict | None, evidence_view: dict | None) -> dict:
    event_ctx = event_ctx or {}
    transcript_bundle = transcript_bundle or {}
    evidence_view = evidence_view or {}

    profile = _event_support_profile(event_ctx, transcript_bundle, evidence_view)
    likely_topics = profile['likely_topics']
    fmt = profile['fmt']
    qa = profile['qa']
    media_context = profile['media_context']
    event_structure = profile['event_structure']
    current_grounding = profile['current_grounding']
    topic_centrality = profile['topic_centrality']
    core_hits = profile['core_hits']
    spillover_hits = profile['spillover_hits']
    generic_regime_hits = profile['generic_regime_hits']
    weak_hits = profile['weak_hits']
    historical_support = profile['historical_support']
    path_mode = profile['path_mode']
    event_prior_mode = profile['event_prior_mode']

    support_signals = []
    caution_signals = []
    weak_grounding = current_grounding == 'weak'

    if topic_centrality == 'core-topic':
        support_signals.append('topic-core')
    elif topic_centrality == 'adjacent-topic':
        if weak_grounding:
            support_signals.append('topic-adjacent-weak')
        else:
            support_signals.append('topic-adjacent')
    if media_context.get('gets_right') and not weak_grounding:
        support_signals.append('media-format-fit')
    show_style = media_context.get('show_style') or ''
    show_family = media_context.get('show_family') or ''
    if show_style and show_family and not weak_grounding:
        support_signals.append('show-format-bounded')
    realistic_paths = media_context.get('realistic_paths') or []
    if realistic_paths and not weak_grounding:
        support_signals.append('realistic-media-paths')

    if historical_support == 'strong' and not weak_grounding:
        support_signals.append('historical-strong')
    elif historical_support == 'partial':
        if weak_grounding:
            support_signals.append('historical-partial-weak')
        else:
            support_signals.append('historical-partial')

    if topic_centrality != 'core-topic':
        caution_signals.append('topic-not-exclusive')
    if media_context:
        caution_signals.append('media-topical-vs-conversational')
        if media_context.get('show_family'):
            caution_signals.append('show-format-constrained')
        blocked_paths = media_context.get('blocked_paths') or []
        weak_paths = media_context.get('weak_paths') or []
        if blocked_paths:
            caution_signals.append('blocked-media-paths')
        elif weak_paths:
            caution_signals.append('weak-media-paths')
    if event_structure == 'semi-open' and qa == 'high':
        support_signals.append('semi-open-qa-expansion')
    elif event_structure == 'scripted':
        caution_signals.append('scripted-limits')

    if historical_support == 'weak-regime':
        caution_signals.append('historical-regime-only')
    elif historical_support == 'weak':
        caution_signals.append('historical-thin')

    topic_paths = transcript_bundle.get('topic_paths') or {}
    overextended_families = topic_paths.get('overextended_families') or []
    late_branch_families = topic_paths.get('late_branch_families') or []
    dead_end_families = topic_paths.get('dead_end_families') or []

    if overextended_families:
        filtered_overextended = [fam for fam in overextended_families if fam not in {'culture_media', 'political_opponents'} or 'conference' not in (fmt or '')]
        if filtered_overextended:
            caution_signals.append('overextended-paths')
    elif spillover_hits and not core_hits:
        caution_signals.append('spillover-without-core')
    if generic_regime_hits and not core_hits:
        caution_signals.append('generic-regime-without-core')
    if dead_end_families:
        caution_signals.append('dead-end-families')
    if late_branch_families:
        filtered_late = [fam for fam in late_branch_families if fam not in {'culture_media', 'political_opponents'} or event_prior_mode not in {'conference_coalition'}]
        if filtered_late:
            caution_signals.append('late-branch-expansion')
    if weak_hits:
        weak_families = []
        for row in weak_hits:
            family = row.get('family')
            if family and family not in weak_families:
                weak_families.append(family)
        if weak_families:
            late_preview = filtered_late[:3] if late_branch_families else []
            if late_preview:
                caution_signals.append('late-preview-expansion')
            caution_signals.append('weak-family-baskets')

    interpretive_state = 'structured-not-grounded'
    if evidence_view.get('conclusion_note'):
        interpretive_state = 'evidence-note'
    if weak_grounding and not evidence_view.get('conclusion_note'):
        interpretive_state = 'weak-grounding'

    return {
        'event_structure': event_structure,
        'topic_centrality': topic_centrality,
        'historical_support': 'strong' if historical_support == 'strong' else 'partial' if historical_support == 'partial' else 'weak',
        'current_grounding': current_grounding,
        'interpretive_state': interpretive_state,
        'support_signals': support_signals,
        'caution_signals': caution_signals,
        'path_mode': path_mode,
        'event_prior_mode': event_prior_mode,
        'media_context': media_context,
    }
