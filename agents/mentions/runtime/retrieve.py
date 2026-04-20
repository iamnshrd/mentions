"""Retrieval engine, aligned to current module APIs."""
from __future__ import annotations

import logging

from agents.mentions.module_contracts import ensure_dict, ensure_list
from agents.mentions.runtime.bundle_contracts import build_retrieval_result
from agents.mentions.runtime.trace import new_run_id, trace_log
from agents.mentions.runtime.context_retrieval import (
    retrieve_market_context,
    retrieve_news_context,
    retrieve_transcript_context,
)
from agents.mentions.runtime.ticker_retrieval import (
    retrieve_market_context_by_ticker,
    retrieve_news_context_by_ticker,
    retrieve_transcript_context_by_ticker,
)
from agents.mentions.runtime.persistence_helpers import persist_analysis_stub, persist_ticker_news
from agents.mentions.modules.market_prior import build_market_prior
from agents.mentions.modules.pmt_legacy_kb import query_pmt_knowledge_bundle
from agents.mentions.modules.speaker_event_retrieval import retrieve_relevant_speaker_events
from agents.mentions.modules.pmt_selector import select_pmt_evidence
from agents.mentions.modules.text_evidence_assessor import assess_text_evidence
from agents.mentions.modules.posterior_update import compute_posterior_update
from agents.mentions.modules.challenge_layer import build_challenge_block
from agents.mentions.modules.evidence_fusion import fuse_evidence_bundle
from agents.mentions.modules.workflow_policy import evaluate_workflow_policy
from agents.mentions.utils import timed

log = logging.getLogger('mentions')


def _market_prior_input(market_data: dict, history: list, ticker: str, title: str) -> dict:
    return {
        'ticker': ticker,
        'market': ensure_dict(market_data),
        'history': ensure_list(history),
        'resolved_market': {'ticker': ticker, 'title': title},
        'provider_status': {
            'market': 'ok' if market_data else 'unavailable',
            'history': 'ok' if history else 'unavailable',
        },
    }



def _persist_ticker_side_effects(*, query: str, ticker: str, workflow_policy: dict, market: dict,
                                 news_bundle: dict, transcript_bundle: dict, news: list,
                                 speaker: str, market_data: dict) -> None:
    persist_ticker_news(news, speaker, market_data)
    persist_analysis_stub(
        query=query,
        ticker=market_data.get('ticker', ticker),
        workflow_policy=workflow_policy,
        market=market,
        news_bundle=news_bundle,
        transcript_bundle=transcript_bundle,
    )



def _build_market_payload(*, query: str = '', ticker: str = '', market_data: dict | None = None,
                          history: list | None = None, cached_analysis: list | None = None,
                          entity_kind: str = 'unknown', resolution_source: str = 'unavailable') -> dict:
    market_data = ensure_dict(market_data or {})
    return {
        'query': query,
        'ticker': ticker,
        'market_data': market_data,
        'history': ensure_list(history or []),
        'cached_analysis': ensure_list(cached_analysis or []),
        'event_markets': ensure_list(market_data.get('event_markets', [])),
        'entity_kind': entity_kind,
        'resolution_source': resolution_source,
    }


def _query_context_bundle(*, query: str, market_data: dict, run_id: str) -> tuple[dict, list, dict, list, str]:
    frame = {
        'query': query,
        'category': 'general',
        'needs_transcript': True,
    }
    transcript_bundle = ensure_dict(retrieve_transcript_context(frame))
    transcript_bundle.setdefault('run_id', run_id)
    transcripts = ensure_list(transcript_bundle.get('chunks', []))
    news_bundle = ensure_dict(retrieve_news_context(frame, market_data=market_data))
    news = ensure_list(news_bundle.get('news', []))
    news_status = news_bundle.get('status', 'unavailable')
    return transcript_bundle, transcripts, news_bundle, news, news_status


def _ticker_context_bundle(*, ticker: str, speaker: str, market_data: dict, run_id: str) -> tuple[str, dict, list, dict, list, str]:
    normalized_speaker = speaker or market_data.get('speaker_name', '') or _infer_speaker_from_market(market_data)
    transcript_bundle, transcripts = retrieve_transcript_context_by_ticker(ticker, speaker=normalized_speaker, market_data=market_data)
    transcript_bundle = ensure_dict(transcript_bundle)
    transcript_bundle.setdefault('run_id', run_id)
    transcripts = ensure_list(transcripts)
    news_bundle, news, news_status = retrieve_news_context_by_ticker(ticker, market_data, speaker=normalized_speaker)
    news_bundle = ensure_dict(news_bundle)
    news = ensure_list(news)
    return normalized_speaker, transcript_bundle, transcripts, news_bundle, news, news_status


def _policy_context(*, query: str, market_data: dict, history: list, market: dict,
                    transcript_bundle: dict, news_bundle: dict, cached_analysis: list | None = None,
                    ticker: str = '') -> tuple[dict, dict]:
    title = market_data.get('title', '') or ensure_dict(market_data.get('resolved_market', {})).get('title', '') or query or ticker
    market_prior = build_market_prior(_market_prior_input(market_data, history, market_data.get('ticker', ticker), title))
    try:
        workflow_policy = evaluate_workflow_policy(
            query=query,
            market_data=market_data,
            news_context=news_bundle,
            transcript_intelligence=transcript_bundle,
        )
    except Exception as exc:
        log.debug('Workflow policy evaluation failed: %s', exc)
        workflow_policy = {}
    return market_prior, workflow_policy


def _precompose_context(*, query: str, market: dict, transcripts: list, transcript_bundle: dict,
                        news: list, news_bundle: dict, news_status: str, market_prior: dict,
                        workflow_policy: dict) -> dict:
    return {
        'query': query,
        'market': market,
        'market_prior': market_prior,
        'transcripts': ensure_list(transcripts),
        'transcript_bundle': ensure_dict(transcript_bundle),
        'news': ensure_list(news),
        'news_bundle': ensure_dict(news_bundle),
        'news_status': news_status,
        'workflow_policy': ensure_dict(workflow_policy),
    }


def _trace_context_counts(*, run_id: str, stage: str, query: str = '', ticker: str = '',
                          normalized_speaker: str = '', transcript_bundle: dict | None = None,
                          news: list | None = None, news_status: str = '') -> None:
    transcript_bundle = ensure_dict(transcript_bundle or {})
    news = ensure_list(news or [])
    trace_log(
        stage,
        run_id=run_id,
        query=query,
        ticker=ticker,
        normalized_speaker=normalized_speaker,
        transcript_candidates=len(transcript_bundle.get('top_candidates', [])),
        news_count=len(news),
        news_status=news_status,
    )


def compose_retrieval_bundle(*, query: str, market: dict, market_prior: dict, transcripts: list, transcript_bundle: dict, news: list, news_bundle: dict, news_status: str, workflow_policy: dict) -> dict:
    frame = {'query': query, 'route': workflow_policy.get('decision', '')}
    pmt_knowledge = query_pmt_knowledge_bundle(
        event_title=query,
        speaker=transcript_bundle.get('speaker', ''),
        fmt=(market.get('market_data', {}) or {}).get('event_type', ''),
        freeform=query,
        top=3,
    )
    speaker_event_context = retrieve_relevant_speaker_events(query, transcript_bundle, market)
    selected_pmt_evidence = select_pmt_evidence(query, frame, market_prior, pmt_knowledge)
    text_evidence_assessment = assess_text_evidence(query, frame, market_prior, news_bundle, transcript_bundle, selected_pmt_evidence)
    posterior_update = compute_posterior_update(market_prior, text_evidence_assessment, workflow_policy)
    challenge_block = build_challenge_block(market_prior, text_evidence_assessment, posterior_update, workflow_policy, news_bundle, transcript_bundle)

    fusion_input = {
        'market': market,
        'market_prior': market_prior,
        'news_context': news_bundle,
        'transcript_intelligence': transcript_bundle,
        'workflow_policy': workflow_policy,
        'pmt_knowledge': pmt_knowledge,
        'selected_pmt_evidence': selected_pmt_evidence,
        'text_evidence_assessment': text_evidence_assessment,
        'posterior_update': posterior_update,
        'challenge_block': challenge_block,
    }
    fused_evidence = fuse_evidence_bundle(query, frame, fusion_input)
    sources_used = []
    if market.get('market_data'):
        sources_used.append('market')
    if news:
        sources_used.append('news')
    if transcripts:
        sources_used.append('transcripts')
    if pmt_knowledge:
        sources_used.append('pmt')
    has_data = bool(market.get('market_data') or news or transcripts)
    result = build_retrieval_result(
        market=market,
        market_prior=market_prior,
        transcripts=transcripts,
        transcript_intelligence=transcript_bundle,
        news=news,
        news_status=news_status,
        news_context=news_bundle,
        workflow_policy=workflow_policy,
        pmt_knowledge=pmt_knowledge,
        selected_pmt_evidence=selected_pmt_evidence,
        text_evidence_assessment=text_evidence_assessment,
        posterior_update=posterior_update,
        challenge_block=challenge_block,
        fused_evidence=fused_evidence,
        has_data=has_data,
        sources_used=sources_used,
    )
    result['speaker_event_context'] = speaker_event_context
    return result


@timed('retrieve_market_data')
def retrieve_market_data(query: str, limit: int = 5, speaker: str = '') -> dict:
    run_id = new_run_id()
    trace_log('retrieve.market_data.start', run_id=run_id, query=query, limit=limit, speaker=speaker)

    market_context = retrieve_market_context(query)
    market_data = ensure_dict(market_context.get('market_data', {}))
    history = ensure_list(market_context.get('history', []))

    transcript_bundle, transcripts, news_bundle, news, news_status = _query_context_bundle(
        query=query,
        market_data=market_data,
        run_id=run_id,
    )

    _trace_context_counts(
        run_id=run_id,
        stage='retrieve.market_data.context',
        query=query,
        transcript_bundle=transcript_bundle,
        news=news,
        news_status=news_status,
    )

    title = market_data.get('title', '') or ensure_dict(market_context.get('resolved_market', {})).get('title', '') or query
    market = _build_market_payload(
        query=query,
        market_data=market_data,
        history=history,
        cached_analysis=market_context.get('cached_analysis', []),
    )
    market_prior, workflow_policy = _policy_context(
        query=query,
        market_data=market_data,
        history=history,
        market=market,
        transcript_bundle=transcript_bundle,
        news_bundle=news_bundle,
        cached_analysis=market_context.get('cached_analysis', []),
    )

    precompose = _precompose_context(
        query=query,
        market=market,
        transcripts=transcripts,
        transcript_bundle=transcript_bundle,
        news=news,
        news_bundle=news_bundle,
        news_status=news_status,
        market_prior=market_prior,
        workflow_policy=workflow_policy,
    )
    result = compose_retrieval_bundle(**precompose)
    trace_log('retrieve.market_data.finish', run_id=run_id, query=query, market_title=title, has_data=result.get('has_data', False), sources_used=result.get('sources_used', []))
    return result


@timed('retrieve_by_ticker')
def retrieve_by_ticker(ticker: str, speaker: str = '', ticker_kind: str = 'unknown') -> dict:
    run_id = new_run_id()
    ticker = ticker.upper()
    trace_log('retrieve.by_ticker.start', run_id=run_id, ticker=ticker, speaker=speaker, ticker_kind=ticker_kind)

    market_context = retrieve_market_context_by_ticker(ticker, ticker_kind=ticker_kind)
    market_data = ensure_dict(market_context.get('market_data', {}))
    history = ensure_list(market_context.get('history', []))
    entity_kind = market_context.get('entity_kind', 'unknown')
    resolution_source = market_context.get('resolution_source', 'unavailable')
    normalized_speaker, transcript_bundle, transcripts, news_bundle, news, news_status = _ticker_context_bundle(
        ticker=ticker,
        speaker=speaker,
        market_data=market_data,
        run_id=run_id,
    )

    _trace_context_counts(
        run_id=run_id,
        stage='retrieve.by_ticker.context',
        ticker=ticker,
        normalized_speaker=normalized_speaker,
        transcript_bundle=transcript_bundle,
        news=news,
        news_status=news_status,
    )

    family_query = market_data.get('event_title', '') or market_data.get('title', '') or ticker
    title = market_data.get('title', '') or family_query
    market = _build_market_payload(
        query=family_query,
        ticker=ticker,
        market_data=market_data,
        history=history,
        cached_analysis=[],
        entity_kind=entity_kind,
        resolution_source=resolution_source,
    )
    market_prior, workflow_policy = _policy_context(
        query=family_query,
        market_data=market_data,
        history=history,
        market=market,
        transcript_bundle=transcript_bundle,
        news_bundle=news_bundle,
        ticker=ticker,
    )

    _persist_ticker_side_effects(
        query=family_query,
        ticker=ticker,
        workflow_policy=workflow_policy,
        market=market,
        news_bundle=news_bundle,
        transcript_bundle=transcript_bundle,
        news=news,
        speaker=normalized_speaker,
        market_data=market_data,
    )

    precompose = _precompose_context(
        query=family_query,
        market=market,
        transcripts=transcripts,
        transcript_bundle=transcript_bundle,
        news=news,
        news_bundle=news_bundle,
        news_status=news_status,
        market_prior=market_prior,
        workflow_policy=workflow_policy,
    )
    result = compose_retrieval_bundle(**precompose)
    trace_log('retrieve.by_ticker.finish', run_id=run_id, ticker=ticker, entity_kind=entity_kind, resolution_source=resolution_source, market_title=title, has_data=result.get('has_data', False), sources_used=result.get('sources_used', []))
    return result


def retrieve_bundle_for_frame(query: str, frame: dict) -> dict:
    frame = ensure_dict(frame)
    speaker = frame.get('speaker', '') or frame.get('speaker_name', '') or ''
    limit = int(frame.get('limit', 5) or 5)
    return retrieve_market_data(query=query, limit=limit, speaker=speaker)


def build_retrieval_bundle(query: str, frame: dict) -> dict:
    return retrieve_bundle_for_frame(query, frame)


def _infer_speaker_from_market(market_data: dict | None) -> str:
    market_data = ensure_dict(market_data or {})
    title = str(market_data.get('title', '') or market_data.get('event_title', ''))
    if not title:
        return ''
    lowered = title.lower()
    if 'trump' in lowered:
        return 'Donald Trump'
    if 'vance' in lowered:
        return 'JD Vance'
    if 'biden' in lowered:
        return 'Joe Biden'
    if 'harris' in lowered:
        return 'Kamala Harris'
    return ''
