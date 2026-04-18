from __future__ import annotations

import os

from agents.mentions.modules.market_resolution.extraction import extract_market_entities
from agents.mentions.modules.transcript_semantic_retrieval.client import family_score as remote_family_score
from agents.mentions.modules.transcript_semantic_retrieval.family_taxonomy import TRANSCRIPT_FAMILY_TAXONOMY_V0
from agents.mentions.modules.transcript_semantic_retrieval.strategy import retrieve_family_segments
from agents.mentions.runtime.trace import new_run_id, trace_log
from agents.mentions.storage.runtime_query import search_transcripts_runtime
from agents.mentions.utils import fts_query


MAX_TRANSCRIPTS = 3
MAX_FAMILIES = 11
MAX_HITS_PER_FAMILY = 1
PRIORITY_FAMILIES = ('war_geopolitics', 'tariff_policy_legal', 'trade_industry_manufacturing', 'broad_economy_prices', 'energy_industry_manufacturing', 'border_immigration', 'healthcare_drug_pricing', 'sports_education_institutions', 'gop_coalition_internal', 'agriculture_farmers', 'opponents_media_attacks')
MEDIA_FORMAT_HINTS = {
    'fox news sunday': ['fox news sunday'],
    'fox news': ['fox news', 'hannity', 'ingraham', 'watters', 'bret baier', 'fox & friends', 'fox and friends'],
    'meet the press': ['meet the press'],
    'face the nation': ['face the nation'],
    'this week': ['this week'],
    'state of the union': ['state of the union'],
    'interview': ['interview'],
}
WAR_HINTS = ('iran', 'war', 'military', 'missile', 'missiles', 'nato', 'ukraine', 'security')
TARIFF_POLICY_HINTS = ('tariff', 'tariffs', 'trade authority', 'import', 'imports', 'duties', 'supreme court', 'court', 'legal')
TRADE_INDUSTRY_HINTS = ('factory', 'factories', 'manufacturing', 'steel', 'plant', 'plants', 'car industry', 'production')
ROUNDTABLE_HINTS = ('roundtable',)
ANTI_BOAST_TERMS = (
    'right about everything', 'hottest economy', 'history of our country', 'greatest in the history',
    'everyone knows it', 'they all know it', 'congratulations', 'amazing thing', 'very nice',
)
ANTI_GENERIC_ECONOMY_TERMS = (
    'economy', 'economy in the history', 'invested in our country', 'new plants opening', 'bad economy',
)
FAMILY_TITLE_ANCHORS = {
    'healthcare_drug_pricing': ('drug', 'drugs', 'healthcare', 'health care', 'pharma', 'prescription', 'hospital'),
    'sports_education_institutions': ('sports', 'college sports', 'nil', 'ncaa', 'university', 'universities', 'student athlete'),
    'agriculture_farmers': ('farm', 'farmer', 'farmers', 'agriculture', 'agricultural', 'rural'),
}


def _register_transcript_row(transcript_ids: list[int], title_by_id: dict[int, str], row: dict) -> int | None:
    tid = row.get('transcript_id')
    if tid and tid not in transcript_ids:
        transcript_ids.append(tid)
        title_by_id[tid] = row.get('event_title') or row.get('event_key') or ''
    return tid


def _media_analog_row(*, tid: int | None, title: str, speaker: str) -> dict | None:
    if not title:
        return None
    return {
        'transcript_id': tid,
        'event_title': title,
        'speaker': speaker,
        'source': 'media-format-title',
        'format_match': True,
        'topic_match': False,
        'match_reasons': ['same-speaker', 'media-format'],
    }


def _candidate_hit(*, tid: int, title: str, speaker: str, family: str, quote: str, adjusted_score: float, evidence_type: str) -> dict:
    title_lower = (title or '').lower()
    is_roundtable = 'roundtable' in title_lower
    return {
        'transcript_id': tid,
        'event_title': title,
        'speaker': speaker,
        'speaker_match': bool(speaker),
        'format_match': is_roundtable,
        'topic_match': True,
        'topic_matches': [family],
        'format_matches': ['roundtable'] if is_roundtable else [],
        'relevance_score': adjusted_score,
        'match_reasons': ['same-speaker', 'same-topic'],
        'quote': quote,
        'source': f'ml-family:{family}',
        'family': family,
        'evidence_type': evidence_type,
    }


def _score_family_rows(*, family: str, tid: int, title: str, query: str,
                       candidate_rows: list[dict], max_hits_per_family: int,
                       run_id: str) -> list[dict]:
    remote = remote_family_score(
        query=query,
        family=family,
        event_title=title,
        segments=[{'id': idx, 'text': row.get('text', ''), 'meta': row} for idx, row in enumerate(candidate_rows)],
        top_k=max_hits_per_family,
        run_id=run_id,
    )
    remote_rows = remote.get('results', []) if isinstance(remote, dict) else []
    scored_rows = []
    for scored in remote_rows:
        meta = scored.get('meta') or {}
        quote = scored.get('text', '')
        scored_rows.append({
            'score': scored.get('score', 0),
            'text': quote,
            'meta': meta,
            'evidence_type': scored.get('evidence_type') or _classify_evidence_type(family, quote=quote, event_title=title, query=query),
        })
    return scored_rows or [
        {
            'score': row.get('score', 0),
            'text': row.get('text', ''),
            'meta': row,
            'evidence_type': _classify_evidence_type(family, quote=row.get('text', ''), event_title=title, query=query),
        }
        for row in candidate_rows[:MAX_HITS_PER_FAMILY]
    ]


def _accumulate_family_hits(*, family: str, tid: int, title: str, speaker: str,
                            query: str, rows: list[dict], per_family: list[dict],
                            top_candidates: list[dict]) -> None:
    if not rows:
        return
    per_family.append({
        'transcript_id': tid,
        'event_title': title,
        'mode': None,
        'results': rows,
    })
    for hit in rows:
        quote = hit.get('text', '')
        adjusted_score = _adjust_score(
            family,
            base_score=hit.get('score', 0),
            quote=quote,
            event_title=title,
            query=query,
        )
        evidence_type = hit.get('evidence_type') or _classify_evidence_type(family, quote=quote, event_title=title, query=query)
        top_candidates.append(_candidate_hit(
            tid=tid,
            title=title,
            speaker=speaker,
            family=family,
            quote=quote,
            adjusted_score=adjusted_score,
            evidence_type=evidence_type,
        ))


def _extend_transcript_ids(transcript_ids: list[int], title_by_id: dict[int, str], rows: list[dict], cap: int) -> None:
    for row in rows:
        _register_transcript_row(transcript_ids, title_by_id, row)
        if len(transcript_ids) >= cap:
            break


def build_transcript_intelligence_bundle(query: str, limit: int = 5, speaker: str = '') -> dict:
    run_id = new_run_id()
    debug_mode = os.getenv('MENTIONS_DEBUG_FAST', '').strip().lower() in {'1', 'true', 'yes', 'on'}
    max_transcripts = 1 if debug_mode else MAX_TRANSCRIPTS
    max_families = 3 if debug_mode else MAX_FAMILIES
    max_hits_per_family = 1 if debug_mode else MAX_HITS_PER_FAMILY
    trace_log('transcript.ml_builder.start', run_id=run_id, query=query, speaker=speaker, limit=limit, debug_mode=debug_mode, max_transcripts=max_transcripts, max_families=max_families)
    if not fts_query(query):
        trace_log('transcript.ml_builder.empty_query', run_id=run_id, query=query)
        return _empty_bundle(query, speaker=speaker)

    entities = extract_market_entities(query)
    inferred_speaker = speaker or ((entities.get('speakers') or [''])[0] if (entities.get('speakers') or []) else '')
    transcripts = search_transcripts_runtime(query=inferred_speaker or query, speaker=inferred_speaker, limit=max(limit * 4, 12))

    transcript_ids = []
    title_by_id = {}
    _extend_transcript_ids(transcript_ids, title_by_id, transcripts, max_transcripts)

    title_first_rows = _title_first_transcripts(query=query, speaker=inferred_speaker, limit=max_transcripts * 2)
    _extend_transcript_ids(transcript_ids, title_by_id, title_first_rows, max_transcripts * 2)

    media_analog_rows = _media_format_transcripts(query=query, speaker=inferred_speaker, limit=max_transcripts * 3)
    media_analogs = []
    for row in media_analog_rows:
        tid = _register_transcript_row(transcript_ids, title_by_id, row)
        title = row.get('event_title') or row.get('event_key') or ''
        analog = _media_analog_row(tid=tid, title=title, speaker=inferred_speaker)
        if analog and len(media_analogs) < 5:
            media_analogs.append(analog)
        if len(transcript_ids) >= max_transcripts * 3:
            break

    _extend_transcript_ids(transcript_ids, title_by_id, title_first_rows, max_transcripts * 2)

    debug_families_raw = os.getenv('MENTIONS_DEBUG_FAMILIES', '').strip()
    debug_family_allowlist = [item.strip() for item in debug_families_raw.split(',') if item.strip()]
    candidate_families = _candidate_families(query)
    if debug_family_allowlist:
        candidate_families = [family for family in candidate_families if family in debug_family_allowlist]
    candidate_families = candidate_families[:max_families]
    family_seed_ids = _family_seed_transcript_ids(candidate_families, speaker=inferred_speaker, query=query, limit=max_transcripts)
    for family, seeded_ids in family_seed_ids.items():
        for tid in seeded_ids:
            if tid and tid not in transcript_ids:
                transcript_ids.append(tid)
    trace_log('transcript.ml_builder.selection', run_id=run_id, inferred_speaker=inferred_speaker, transcript_ids=transcript_ids, candidate_families=candidate_families, family_seed_ids=family_seed_ids, debug_family_allowlist=debug_family_allowlist, media_analog_count=len(media_analogs))

    family_results = {}
    top_candidates = []
    filtered_transcript_ids = _prefilter_transcript_ids(candidate_families, transcript_ids, title_by_id, query, family_seed_ids=family_seed_ids)
    for family in candidate_families:
        per_family = []
        for tid in filtered_transcript_ids.get(family, transcript_ids):
            result = retrieve_family_segments(tid, family, limit=max(max_hits_per_family, 3))
            candidate_rows = result.get('selected_results', [])[:3]
            if not candidate_rows:
                continue
            rows = _score_family_rows(
                family=family,
                tid=tid,
                title=title_by_id.get(tid, ''),
                query=query,
                candidate_rows=candidate_rows,
                max_hits_per_family=max_hits_per_family,
                run_id=run_id,
            )
            if rows:
                _accumulate_family_hits(
                    family=family,
                    tid=tid,
                    title=title_by_id.get(tid, ''),
                    speaker=inferred_speaker,
                    query=query,
                    rows=rows,
                    per_family=per_family,
                    top_candidates=top_candidates,
                )
                if per_family:
                    per_family[-1]['mode'] = result.get('mode')
        if per_family:
            family_results[family] = per_family

    top_candidates.sort(key=lambda row: row.get('relevance_score', 0), reverse=True)
    top_candidates = top_candidates[:limit]
    same_speaker_hits = len(top_candidates)
    same_format_hits = sum(1 for row in top_candidates if row.get('format_match'))
    same_topic_hits = sum(1 for row in top_candidates if row.get('topic_match'))
    support_strength = 'high' if len(top_candidates) >= 3 else 'medium' if top_candidates else 'weak'

    trace_log(
        'transcript.ml_builder.finish',
        run_id=run_id,
        status='ok' if top_candidates else 'empty',
        core_hits=len([row for row in top_candidates if row.get('evidence_type') == 'core']),
        spillover_hits=len([row for row in top_candidates if row.get('evidence_type') == 'spillover']),
        generic_regime_hits=len([row for row in top_candidates if row.get('evidence_type') == 'generic_regime']),
        families=list(family_results.keys()),
    )

    core_hits = [row for row in top_candidates if row.get('evidence_type') == 'core'][:5]
    spillover_hits = [row for row in top_candidates if row.get('evidence_type') == 'spillover'][:5]
    generic_regime_hits = [row for row in top_candidates if row.get('evidence_type') == 'generic_regime'][:5]

    return _transcript_intelligence_contract(
        query=query,
        speaker=inferred_speaker,
        status='ok' if top_candidates else 'empty',
        chunks=transcripts[:limit],
        summary='ML-first transcript family retrieval' if top_candidates else 'No ML transcript families found.',
        top_speakers=[inferred_speaker] if inferred_speaker else [],
        top_events=[row.get('event_title', '') for row in top_candidates[:3] if row.get('event_title')],
        context_risks=[] if top_candidates else ['ml-transcript-empty'],
        query_target={'speaker': inferred_speaker, 'event_format': [], 'topic_candidates': list(family_results.keys())[:5]},
        speaker_context={
            'speaker': inferred_speaker,
            'same_speaker_hits': same_speaker_hits,
            'support_strength': support_strength,
            'tendency_summary': 'ML-first transcript family retrieval is active.' if top_candidates else 'No ML transcript family support found.',
        },
        format_analogs=(media_analogs + [row for row in top_candidates if row.get('format_match')])[:5],
        topic_analogs=[row for row in top_candidates if row.get('topic_match')][:3],
        counterevidence=[],
        top_candidates=top_candidates,
        core_hits=core_hits,
        spillover_hits=spillover_hits,
        generic_regime_hits=generic_regime_hits,
        retrieval_summary='ML-first transcript family retrieval found family-matched analogs.' if top_candidates else 'No transcript family analogs found.',
        family_results=family_results,
        media_analogs=media_analogs[:5],
        run_id=run_id,
    )


def _media_format_transcripts(query: str, speaker: str, limit: int) -> list[dict]:
    lowered = (query or '').lower()
    title_terms: list[str] = []
    for trigger, hints in MEDIA_FORMAT_HINTS.items():
        if trigger in lowered:
            title_terms.extend(hints)
    if not title_terms:
        return []
    title_query = ' '.join(dict.fromkeys(title_terms))
    return search_transcripts_runtime(query=speaker or query, title_query=title_query, speaker=speaker, limit=limit)


def _title_first_transcripts(query: str, speaker: str, limit: int) -> list[dict]:
    lowered = (query or '').lower()
    title_terms: list[str] = []
    for term in TARIFF_POLICY_HINTS + TRADE_INDUSTRY_HINTS + WAR_HINTS + ROUNDTABLE_HINTS:
        if term in lowered and term not in title_terms:
            title_terms.append(term)
    if not title_terms:
        return []
    title_query = ' '.join(title_terms)
    return search_transcripts_runtime(query=speaker or query, title_query=title_query, speaker=speaker, limit=limit)


def _family_seed_transcript_ids(candidate_families: list[str], speaker: str, query: str, limit: int) -> dict[str, list[int]]:
    seeded: dict[str, list[int]] = {}
    for family in candidate_families:
        anchors = FAMILY_TITLE_ANCHORS.get(family, ())
        family_ids: list[int] = []
        for anchor in anchors:
            rows = search_transcripts_runtime(query=speaker or query, speaker=speaker, title_query=anchor, limit=max(limit * 3, 6))
            for row in rows:
                tid = row.get('transcript_id')
                if tid and tid not in family_ids:
                    family_ids.append(tid)
                if len(family_ids) >= limit:
                    break
            if len(family_ids) >= limit:
                break
        if family_ids:
            seeded[family] = family_ids
    return seeded


def _prefilter_transcript_ids(candidate_families: list[str], transcript_ids: list[int], title_by_id: dict[int, str], query: str, family_seed_ids: dict[str, list[int]] | None = None) -> dict[str, list[int]]:
    lowered_query = (query or '').lower()
    filtered: dict[str, list[int]] = {}
    family_seed_ids = family_seed_ids or {}
    for family in candidate_families:
        family_ids: list[int] = list(family_seed_ids.get(family, []))
        for tid in transcript_ids:
            title = (title_by_id.get(tid, '') or '').lower()
            blob = f"{lowered_query} {title}"
            if family == 'tariff_policy_legal':
                if any(term in blob for term in TARIFF_POLICY_HINTS):
                    family_ids.append(tid)
            elif family == 'trade_industry_manufacturing':
                if any(term in blob for term in TRADE_INDUSTRY_HINTS):
                    family_ids.append(tid)
            elif family == 'war_geopolitics':
                if any(term in blob for term in WAR_HINTS):
                    family_ids.append(tid)
            else:
                family_ids.append(tid)
        unique_ids: list[int] = []
        seen: set[int] = set()
        for tid in family_ids:
            if tid and tid not in seen:
                seen.add(tid)
                unique_ids.append(tid)
        filtered[family] = unique_ids[:MAX_TRANSCRIPTS] or transcript_ids[:MAX_TRANSCRIPTS]
    return filtered


def _candidate_families(query: str) -> list[str]:
    lowered = (query or '').lower()
    selected: list[str] = []
    if any(term in lowered for term in WAR_HINTS):
        selected.append('war_geopolitics')
    if any(term in lowered for term in TARIFF_POLICY_HINTS):
        selected.append('tariff_policy_legal')
    if any(term in lowered for term in TRADE_INDUSTRY_HINTS):
        selected.append('trade_industry_manufacturing')
    if any(term in lowered for term in ('inflation', 'prices', 'economy', 'affordability', 'gas', 'wages')):
        selected.append('broad_economy_prices')
    if any(term in lowered for term in ('oil', 'gas', 'drilling', 'pipeline', 'refinery', 'energy', 'electricity')):
        selected.append('energy_industry_manufacturing')
    if any(term in lowered for term in ('border', 'immigration', 'migrants', 'deportation', 'illegal aliens', 'cartel', 'asylum', 'border patrol', 'illegal immigration')):
        selected.append('border_immigration')
    if any(term in lowered for term in ('drug prices', 'prescription', 'healthcare', 'health care', 'medicaid', 'pharmaceutical', 'drug pricing', 'most favored nation')):
        selected.append('healthcare_drug_pricing')
    if any(term in lowered for term in ('college sports', 'nil', 'student athletes', 'ncaa', 'college football', 'college basketball', 'universities')):
        selected.append('sports_education_institutions')
    if any(term in lowered for term in ('house gop', 'member retreat', 'republican conference', 'gop', 'coalition', 'house republicans')):
        selected.append('gop_coalition_internal')
    if any(term in lowered for term in ('farmers', 'farmer', 'agriculture', 'crops', 'john deere', 'food prices', 'rural producers')):
        selected.append('agriculture_farmers')
    if any(term in lowered for term in ('biden', 'kamala', 'obama', 'democrat', 'fake news', 'newscum', 'witch hunt', 'radical left')):
        selected.append('opponents_media_attacks')
    if not selected:
        selected = [family for family in PRIORITY_FAMILIES if family in TRANSCRIPT_FAMILY_TAXONOMY_V0]
    return selected[:MAX_FAMILIES]


def _adjust_score(family: str, base_score: float, quote: str, event_title: str, query: str) -> float:
    score = float(base_score or 0)
    text = f"{event_title} {quote}".lower()
    query_lower = (query or '').lower()
    if 'roundtable' in query_lower and 'roundtable' in text:
        score += 0.08
    if family == 'war_geopolitics':
        if any(term in text for term in WAR_HINTS):
            score += 0.08
        if any(term in text for term in TARIFF_POLICY_HINTS + TRADE_INDUSTRY_HINTS):
            score -= 0.06
    if family == 'tariff_policy_legal':
        if any(term in text for term in TARIFF_POLICY_HINTS):
            score += 0.08
        if any(term in text for term in WAR_HINTS + TRADE_INDUSTRY_HINTS):
            score -= 0.08
        if any(term in text for term in ANTI_BOAST_TERMS):
            score -= 0.12
        if any(term in text for term in ANTI_GENERIC_ECONOMY_TERMS):
            score -= 0.08
    if family == 'trade_industry_manufacturing':
        if any(term in text for term in TRADE_INDUSTRY_HINTS):
            score += 0.08
        if any(term in text for term in WAR_HINTS):
            score -= 0.08
        if any(term in text for term in ANTI_BOAST_TERMS):
            score -= 0.12
        if any(term in text for term in ANTI_GENERIC_ECONOMY_TERMS):
            score -= 0.08
    return score


def _classify_evidence_type(family: str, quote: str, event_title: str, query: str) -> str:
    text = f"{event_title} {quote}".lower()
    has_boast = any(term in text for term in ANTI_BOAST_TERMS)
    has_generic_economy = any(term in text for term in ANTI_GENERIC_ECONOMY_TERMS)
    if family == 'war_geopolitics':
        if has_boast and not any(term in text for term in WAR_HINTS):
            return 'generic_regime'
        return 'core' if any(term in text for term in WAR_HINTS) else 'spillover'
    if family == 'tariff_policy_legal':
        if has_boast or has_generic_economy:
            return 'generic_regime'
        if any(term in text for term in TARIFF_POLICY_HINTS):
            return 'core'
        return 'spillover'
    if family == 'trade_industry_manufacturing':
        if has_boast or has_generic_economy:
            return 'generic_regime'
        if any(term in text for term in TRADE_INDUSTRY_HINTS):
            return 'core'
        return 'spillover'
    return 'spillover'


def _transcript_intelligence_contract(*, query: str, speaker: str, status: str,
                                      chunks: list[dict], summary: str,
                                      top_speakers: list[str], top_events: list[str],
                                      context_risks: list[str], query_target: dict,
                                      speaker_context: dict, format_analogs: list[dict],
                                      topic_analogs: list[dict], counterevidence: list[dict],
                                      top_candidates: list[dict], core_hits: list[dict],
                                      spillover_hits: list[dict], generic_regime_hits: list[dict],
                                      retrieval_summary: str, family_results: dict,
                                      media_analogs: list[dict], run_id: str) -> dict:
    return {
        'query': query,
        'speaker': speaker,
        'status': status,
        'chunks': chunks,
        'summary': summary,
        'top_speakers': top_speakers,
        'top_events': top_events,
        'context_risks': context_risks,
        'query_target': query_target,
        'speaker_context': speaker_context,
        'format_analogs': format_analogs,
        'topic_analogs': topic_analogs,
        'counterevidence': counterevidence,
        'top_candidates': top_candidates,
        'core_hits': core_hits,
        'spillover_hits': spillover_hits,
        'generic_regime_hits': generic_regime_hits,
        'retrieval_summary': retrieval_summary,
        'family_results': family_results,
        'media_analogs': media_analogs,
        'run_id': run_id,
        'has_core_support': bool(core_hits),
        'has_spillover_support': bool(spillover_hits),
        'has_generic_regime': bool(generic_regime_hits),
        'support_shape': 'core-led' if core_hits else 'spillover-led' if spillover_hits else 'generic-only' if generic_regime_hits else 'empty',
    }


def _empty_bundle(query: str, speaker: str = '') -> dict:
    return _transcript_intelligence_contract(
        query=query,
        speaker=speaker,
        status='empty',
        chunks=[],
        summary='',
        top_speakers=[],
        top_events=[],
        context_risks=['ml-transcript-empty'],
        query_target={'speaker': speaker, 'event_format': [], 'topic_candidates': []},
        speaker_context={'speaker': speaker, 'same_speaker_hits': 0, 'support_strength': 'weak', 'tendency_summary': 'No ML transcript family support found.'},
        format_analogs=[],
        topic_analogs=[],
        counterevidence=[],
        top_candidates=[],
        core_hits=[],
        spillover_hits=[],
        generic_regime_hits=[],
        retrieval_summary='No transcript family analogs found.',
        family_results={},
        media_analogs=[],
        run_id='',
    )
