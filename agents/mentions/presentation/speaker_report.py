from __future__ import annotations

from agents.mentions.presentation.report_common import event_read_sentence, format_read_sentence, ru_conclusion_note, ru_match_reasons
from agents.mentions.presentation.normalizer import normalize_analysis_confidence as ru_confidence, normalize_confidence_scope as ru_confidence_scope
from agents.mentions.presentation.report_sections import baseline_line, basket_explain_lines, direct_topics_line, late_paths_line, should_render_basket_explain, transcript_boundary_line, weak_paths_line
from agents.mentions.presentation.user_output import render_user_output_sections


def render_analysis_report(event_title: str, event_ctx: dict, interpretation_block: dict,
                           evidence_view: dict, news: list[dict], transcript_bundle: dict,
                           confidence: str, strike_list: list[str],
                           strike_baskets: dict | None = None,
                           topic_paths: dict | None = None,
                           market_meta: dict | None = None) -> str:
    interpretation_block = interpretation_block or {}
    evidence_view = evidence_view or {}
    event_ctx = event_ctx or {}
    market_meta = market_meta or {}
    topics = event_ctx.get('likely_topics', [])[:3]
    top_news = _rank_news_for_reasoning(news)[:3]
    lead_transcript = (transcript_bundle.get('top_candidates') or [])[:1]

    event_structure = interpretation_block.get('event_structure') or ''
    topic_centrality = interpretation_block.get('topic_centrality') or ''
    historical_support = interpretation_block.get('historical_support') or ''

    parts = []
    path_mode = interpretation_block.get('path_mode', 'transcript_backed')
    event_prior_mode = interpretation_block.get('event_prior_mode', 'default')
    media_context = interpretation_block.get('media_context') or {}
    user_output = render_user_output_sections(interpretation_block=interpretation_block)
    parts.append(f"**Разбор события:** {event_read_sentence(event_structure, topic_centrality, historical_support)}")
    entity_kind = market_meta.get('entity_kind') or ''
    resolution_source = market_meta.get('resolution_source') or ''
    if entity_kind == 'event' and resolution_source == 'event-ticker':
        parts.append("**Kalshi resolution:** этот URL резолвится как event ticker, поэтому market context собирается через event + вложенные strikes, а не через direct market lookup.")
    if path_mode == 'event_prior_fallback':
        parts.append(f"**Режим path-read:** здесь path-интерпретация в основном опирается на тип события (`{event_prior_mode}`), а не на полноценный transcript-built path.")

    baseline = ' / '.join(topics) if topics else 'контекст ещё тонкий'
    parts.append(baseline_line(topics))

    if top_news:
        news_lines = []
        for item in top_news[:3]:
            headline = _clean_headline(item.get('headline') or item.get('title') or '')
            source = item.get('source') or 'источник'
            if headline:
                news_lines.append(f"- {source}: {headline}")
        if news_lines:
            parts.append("**Свежий контекст:**\n" + '\n'.join(news_lines))

    preferred_analog = None
    for row in (transcript_bundle.get('spillover_hits') or []) + (transcript_bundle.get('generic_regime_hits') or []) + (transcript_bundle.get('core_hits') or []) + lead_transcript:
        family = row.get('family') or ''
        if family in {'tariff_policy_legal', 'trade_industry_manufacturing', 'labor_tax'}:
            preferred_analog = row
            break
    if not preferred_analog and lead_transcript:
        preferred_analog = lead_transcript[0]
    if preferred_analog:
        reasons = ru_match_reasons(preferred_analog.get('match_reasons') or [])
        family = preferred_analog.get('family') or ''
        family_note = f", family `{family}`" if family else ''
        parts.append(f"**Исторический контекст:** лучший полезный аналог{family_note}, {preferred_analog.get('event_title') or 'исторический аналог'} ({reasons}).")

    parts.append(f"**Формат:** {format_read_sentence(event_ctx)}")

    strike_baskets = strike_baskets or {}
    topic_paths = topic_paths or {}
    direct_topics = strike_baskets.get('core', [])[:4] or topics[:2]
    weak_paths = strike_baskets.get('weak', [])[:4]
    late_paths = strike_baskets.get('late', [])[:4] or (topics[2:3] if len(topics) > 2 else [])
    weak_media_case = bool(media_context) and not topics and not direct_topics
    direct_line = direct_topics_line(direct_topics)
    weak_line = weak_paths_line(weak_paths)
    late_line = late_paths_line(late_paths)
    if direct_line:
        parts.append(direct_line)
    if weak_line:
        parts.append(weak_line)
    if late_line:
        parts.append(late_line)

    for line in user_output.get('media_lines', []):
        parts.append(line)

    core_hits = transcript_bundle.get('core_hits') or []
    spillover_hits = transcript_bundle.get('spillover_hits') or []
    generic_regime_hits = transcript_bundle.get('generic_regime_hits') or []
    if core_hits:
        core_families = list({row.get('family') for row in core_hits[:4] if row.get('family')})
        if core_families:
            parts.append(f"**Direct transcript core:** {', '.join(core_families)}.")
    if spillover_hits:
        spill_families = list({row.get('family') for row in spillover_hits[:4] if row.get('family')})
        if spill_families:
            parts.append(f"**Spillover / adjacent paths:** {', '.join(spill_families)}.")
    if generic_regime_hits:
        regime_families = list({row.get('family') for row in generic_regime_hits[:4] if row.get('family')})
        if regime_families:
            parts.append(f"**Regime-embedded context:** {', '.join(regime_families)}.")

    score_rows = strike_baskets.get('score_rows') or []
    if should_render_basket_explain(score_rows=score_rows, weak_media_case=weak_media_case):
        explain_block = basket_explain_lines(score_rows)
        if explain_block:
            parts.append(explain_block)

    leading_paths = topic_paths.get('leading_paths') or []
    dead_end_families = topic_paths.get('dead_end_families') or []
    family_evidence = topic_paths.get('family_evidence') or []
    if family_evidence:
        rendered_families = []
        useful_rows = []
        for row in family_evidence:
            evidence_types = row.get('evidence_types') or {}
            if evidence_types.get('core') or evidence_types.get('spillover'):
                useful_rows.append(row)
        for row in useful_rows[:3]:
            evidence_types = row.get('evidence_types') or {}
            family = row.get('family') or ''
            if evidence_types.get('core'):
                rendered_families.append(f"{family}: есть direct transcript core")
            elif evidence_types.get('spillover'):
                rendered_families.append(f"{family}: есть spillover / adjacent transcript support")
        if rendered_families:
            parts.append("**Transcript family evidence:** " + '; '.join(rendered_families) + '.')

    if leading_paths:
        rendered = []
        for row in leading_paths[:3]:
            to_path = row.get('to') or ''
            if to_path == 'geopolitics' and 'no tax on tips' in baseline.lower():
                continue
            rendered.append(f"{row.get('from')} → {to_path} ({row.get('strength')})")
        if rendered:
            parts.append("**Тематические переходы:** " + '; '.join(rendered) + '.')

    transition_hints = topic_paths.get('transition_hints') or []
    if transition_hints:
        rendered_hints = []
        for row in transition_hints[:3]:
            if row.get('to') == 'geopolitics' and 'no tax on tips' in baseline.lower():
                continue
            source = row.get('source') or 'analog'
            window = row.get('window') or ''
            if window:
                rendered_hints.append(f"{row.get('from')} → {row.get('to')} через {source} ({window})")
            else:
                rendered_hints.append(f"{row.get('from')} → {row.get('to')} через {source}")
        if rendered_hints:
            parts.append("**Где path реально сцеплялся в аналогах:** " + '; '.join(rendered_hints) + '.')

    if dead_end_families:
        parts.append("**Слабые path-зоны:** " + ', '.join(dead_end_families[:3]) + '.')

    boundary_line = transcript_boundary_line(family_evidence=family_evidence, transition_hints=transition_hints)
    if boundary_line:
        parts.append(boundary_line)

    market_gets_right = interpretation_block.get('market_gets_right') or []
    market_flattens = interpretation_block.get('market_flattens') or []
    sharpened_flattens = sharpen_market_flattens(market_flattens, topic_paths=topic_paths, transcript_bundle=transcript_bundle)
    rendered_gets_right = user_output.get('market_gets_right', []) or market_gets_right
    rendered_flattens = user_output.get('market_flattens', []) or sharpened_flattens
    if rendered_gets_right:
        parts.append("**Что реально поддерживает текущий read:**\n" + '\n'.join(f"- {line}" for line in rendered_gets_right[:3]))
    if rendered_flattens:
        parts.append("**Где текущий read нельзя расширять слишком смело:**\n" + '\n'.join(f"- {line}" for line in rendered_flattens[:4]))

    conclusion = ru_conclusion_note(evidence_view.get('conclusion_state', ''))
    confidence_scope = ru_confidence_scope(evidence_view.get('confidence_scope') or 'context-grounding')
    final_line = f"**Главный вывод:** качество контекста {ru_confidence(confidence)}. {conclusion}".strip()
    if confidence_scope:
        final_line = f"{final_line} ({confidence_scope})"
    parts.append(final_line)
    return '\n\n'.join(part for part in parts if part).strip()


def sharpen_market_flattens(lines: list[str], topic_paths: dict | None = None, transcript_bundle: dict | None = None) -> list[str]:
    lines = [str(line).strip() for line in (lines or []) if str(line).strip()]
    topic_paths = topic_paths or {}
    transcript_bundle = transcript_bundle or {}
    overextended = topic_paths.get('overextended_families', []) or []
    late = topic_paths.get('late_branch_families', []) or []
    dead_ends = topic_paths.get('dead_end_families', []) or []
    weak_families = [row.get('family') for row in (transcript_bundle.get('weak_hits') or []) if row.get('family')]

    out = []
    if any('broad rhetorical regime' in line for line in lines):
        out.append(next(line for line in lines if 'broad rhetorical regime' in line))

    if overextended:
        out.append(f"рынок может слишком рано расширять основной event path в соседние ветки без прямого core-перехода: {', '.join(overextended[:3])}")
    elif any('слишком рано расширять event read' in line for line in lines):
        out.append(next(line for line in lines if 'слишком рано расширять event read' in line))

    if late:
        out.append(f"часть текущих трактовок больше похожа на позднее Q&A / side-branch расширение, чем на естественный основной path: {', '.join(late[:3])}")
    elif any('late/Q&A expansion' in line for line in lines):
        out.append(next(line for line in lines if 'late/Q&A expansion' in line))

    if dead_ends:
        out.append(f"некоторые боковые корзины сейчас выглядят скорее как dead ends, а не как естественное продолжение события: {', '.join(dead_ends[:3])}")
    elif weak_families:
        out.append(f"часть корзин пока выглядит forced и держится слабее, чем основной event path: {', '.join(weak_families[:3])}")

    seen = set()
    deduped = []
    for line in out:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped


def _clean_headline(text: str) -> str:
    text = ' '.join((text or '').split()).strip()
    text = text.removesuffix(' - PBS').removesuffix(' - The Nevada Independent').removesuffix(' - KSNV')
    return text


def _rank_news_for_reasoning(news: list[dict]) -> list[dict]:
    priority = {
        'reuters': 100,
        'associated press': 95,
        'ap': 95,
        'politico': 92,
        'the hill': 90,
        'guardian': 89,
        'bbc': 88,
        'npr': 87,
        'pbs': 86,
        'c-span': 85,
        'the nevada independent': 84,
        'ksnv': 80,
    }
    def score(item: dict) -> tuple[int, str]:
        source = (item.get('source') or '').lower()
        for key, value in priority.items():
            if key in source:
                return (value, source)
        return (50, source)
    return sorted(news or [], key=score, reverse=True)


def summarize_news(news: list[dict]) -> str:
    if not news:
        return ''
    headlines = [n.get('headline', n.get('title', '')) for n in news[:3] if n.get('headline') or n.get('title')]
    return '; '.join(h for h in headlines if h)
