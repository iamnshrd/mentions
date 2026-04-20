from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from agents.mentions.trace import trace_log


DEFAULT_WORKER_URL = os.getenv('MENTIONS_SEMANTIC_WORKER_URL', 'http://100.74.98.63:8765').rstrip('/')


def worker_health(worker_url: str | None = None, timeout: float = 5.0) -> dict:
    base = (worker_url or DEFAULT_WORKER_URL).rstrip('/')
    req = urllib.request.Request(f'{base}/health', method='GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        return {'status': 'error', 'error': str(exc), 'url': base}


def embed_texts(texts: list[str], worker_url: str | None = None, timeout: float = 60.0) -> dict:
    base = (worker_url or DEFAULT_WORKER_URL).rstrip('/')
    payload = {'texts': texts}
    req = urllib.request.Request(
        f'{base}/embed',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        return {'status': 'error', 'error': f'http {exc.code}', 'url': base}
    except Exception as exc:
        return {'status': 'error', 'error': str(exc), 'url': base}


def semantic_search(query: str, family: str, segments: list[dict], top_k: int = 5,
                    worker_url: str | None = None, timeout: float = 20.0) -> dict:
    base = (worker_url or DEFAULT_WORKER_URL).rstrip('/')
    payload = {
        'family': family,
        'query': query,
        'segments': [
            {
                'id': seg.get('id') or seg.get('segment_index') or idx,
                'text': seg.get('text', ''),
                'meta': seg.get('meta', seg.get('metadata', {})) or {},
            }
            for idx, seg in enumerate(segments)
            if (seg.get('text') or '').strip()
        ],
        'top_k': top_k,
    }
    req = urllib.request.Request(
        f'{base}/semantic-search',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        return {'status': 'error', 'error': f'http {exc.code}', 'url': base}
    except Exception as exc:
        return {'status': 'error', 'error': str(exc), 'url': base}


def family_score(query: str, family: str, segments: list[dict], event_title: str = '', top_k: int = 5,
                 worker_url: str | None = None, timeout: float = 20.0, run_id: str = '') -> dict:
    base = (worker_url or DEFAULT_WORKER_URL).rstrip('/')
    payload = {
        'family': family,
        'query': query,
        'event_title': event_title,
        'segments': [
            {
                'id': seg.get('id') or seg.get('segment_index') or idx,
                'text': seg.get('text', ''),
                'meta': seg.get('meta', seg.get('metadata', {})) or {},
            }
            for idx, seg in enumerate(segments)
            if (seg.get('text') or '').strip()
        ],
        'top_k': top_k,
    }
    req = urllib.request.Request(
        f'{base}/family-score',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    trace_log('worker.family_score.request', run_id=run_id, family=family, event_title=event_title, segment_count=len(payload['segments']), top_k=top_k)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            trace_log('worker.family_score.response', run_id=run_id, family=family, result_count=len(data.get('results', [])) if isinstance(data, dict) else 0)
            return data
    except urllib.error.HTTPError as exc:
        trace_log('worker.family_score.error', run_id=run_id, family=family, error=f'http {exc.code}')
        return {'status': 'error', 'error': f'http {exc.code}', 'url': base}
    except Exception as exc:
        trace_log('worker.family_score.error', run_id=run_id, family=family, error=str(exc))
        return {'status': 'error', 'error': str(exc), 'url': base}


def news_score(query: str, family: str, articles: list[dict], event_title: str = '', top_k: int = 5,
               worker_url: str | None = None, timeout: float = 20.0, run_id: str = '') -> dict:
    base = (worker_url or DEFAULT_WORKER_URL).rstrip('/')
    payload = {
        'family': family,
        'query': query,
        'event_title': event_title,
        'articles': [
            {
                'id': article.get('id') or idx,
                'headline': article.get('headline') or article.get('title') or '',
                'text': article.get('text') or article.get('summary') or article.get('snippet') or '',
                'source': article.get('source') or '',
                'meta': article,
            }
            for idx, article in enumerate(articles)
            if (article.get('headline') or article.get('title') or '').strip()
        ],
        'top_k': top_k,
    }
    req = urllib.request.Request(
        f'{base}/news-score',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    trace_log('worker.news_score.request', run_id=run_id, family=family, event_title=event_title, article_count=len(payload['articles']), top_k=top_k)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            trace_log('worker.news_score.response', run_id=run_id, family=family, result_count=len(data.get('results', [])) if isinstance(data, dict) else 0)
            return data
    except urllib.error.HTTPError as exc:
        trace_log('worker.news_score.error', run_id=run_id, family=family, error=f'http {exc.code}')
        return {'status': 'error', 'error': f'http {exc.code}', 'url': base}
    except Exception as exc:
        trace_log('worker.news_score.error', run_id=run_id, family=family, error=str(exc))
        return {'status': 'error', 'error': str(exc), 'url': base}
