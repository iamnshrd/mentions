from __future__ import annotations

import logging

log = logging.getLogger('mentions')


def persist_ticker_news(news: list, speaker: str, market_data: dict) -> None:
    try:
        from agents.mentions.storage.runtime_db import upsert_news_item
        for item in news[:5]:
            if not isinstance(item, dict):
                continue
            url = item.get('url', '')
            if not url:
                continue
            upsert_news_item(
                source=item.get('source', 'newsapi'),
                url=url,
                headline=item.get('headline', ''),
                published_at=item.get('published_at', ''),
                body_text=item.get('summary', '') or item.get('body', '') or '',
                speaker_name=speaker,
                event_key=(market_data or {}).get('event_ticker', ''),
            )
    except Exception as exc:
        log.debug('Runtime DB news persistence failed: %s', exc)


def persist_analysis_stub(query: str, ticker: str, workflow_policy: dict, market: dict, news_bundle: dict, transcript_bundle: dict) -> None:
    try:
        from agents.mentions.storage.runtime_db import insert_analysis_report
        insert_analysis_report(
            query=query,
            ticker=ticker,
            workflow_policy=workflow_policy,
            evidence={
                'market': market,
                'news_context': news_bundle,
                'transcript_intelligence': transcript_bundle,
            },
            analysis={},
            rendered_text='',
            metadata={'runtime_phase': 'retrieve_by_ticker' if query == ticker else 'retrieve'},
        )
    except Exception as exc:
        log.debug('Runtime DB analysis persistence failed: %s', exc)
