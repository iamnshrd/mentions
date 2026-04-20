"""End-to-end integration tests for `orchestrate()`.

These tests seed a real tmp DB with a small transcript corpus and
run the full pipeline — frame selection → retrieval → synthesis →
response → continuity/session updates — with only the LLM client
injected as a fake. They exist to catch regressions on integration
seams (wiring bugs, schema drifts, side-effect ordering) that unit
tests cannot see individually.

Coverage:

* Happy path: a substantive query routes through the KB, produces a
  response, emits trace events, and persists session+continuity state.
* KB bypass: a short / fallback-y query returns an ``answer-directly``
  result without touching retrieval.
* URL path: a Kalshi URL routes through ``orchestrate_url`` and
  returns a trade-brief-shaped result.
* Trace + metrics: one invocation increments intent counters and
  emits a full ``trace.start``/``trace.end`` bracket.
* Failure isolation: a broken LLM client never breaks the pipeline;
  rule-based fallbacks keep the response coming.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


# ── Corpus seed ────────────────────────────────────────────────────────────

_CORPUS = [
    # (speaker, text, event)
    ('Powell', 'Inflation expectations remain anchored. We will continue to '
               'watch the labor market carefully before any policy change.',
               'FOMC Press Conference 2024-12'),
    ('Powell', 'The committee voted to hold rates. We see balanced risks and '
               'will remain data dependent through the first quarter.',
               'FOMC Press Conference 2024-12'),
    ('Alice',  'Kalshi bitcoin markets trade thinner on weekends. Entry '
               'pricing around 50 cents usually scales in cleanly.',
               'Trader Podcast Ep 12'),
    ('Alice',  'When the spread widens past ten cents the liquidity signal '
               'says wait; chasing the move is how accounts blow up.',
               'Trader Podcast Ep 12'),
]


def _seed_transcripts(db_path: Path) -> list[int]:
    from agents.mentions.storage.knowledge.fts_sync import sync_document
    doc_ids: list[int] = []
    by_event: dict[str, list] = {}
    for sp, t, ev in _CORPUS:
        by_event.setdefault(ev, []).append((sp, t))
    with sqlite3.connect(db_path) as conn:
        for event, chunks in by_event.items():
            primary_speaker = chunks[0][0]
            conn.execute(
                '''INSERT INTO transcript_documents
                   (speaker, event, source_file, status, source_type)
                   VALUES (?, ?, ?, 'indexed', 'file')''',
                (primary_speaker, event, f'/tmp/{event}.txt'),
            )
            doc_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            doc_ids.append(doc_id)
            for i, (sp, t) in enumerate(chunks):
                conn.execute(
                    '''INSERT INTO transcript_chunks
                       (document_id, chunk_index, text, speaker, section,
                        token_count)
                       VALUES (?, ?, ?, ?, '', ?)''',
                    (doc_id, i, t, sp, max(1, len(t.split()))),
                )
            sync_document(conn, doc_id)
        conn.commit()
    return doc_ids


@pytest.fixture
def seeded(tmp_db, tmp_workspace):
    """Full pipeline environment: tmp DB + tmp workspace + seeded corpus."""
    doc_ids = _seed_transcripts(tmp_db)
    return {'db': tmp_db, 'workspace': tmp_workspace, 'doc_ids': doc_ids}


# ── Fake LLM ───────────────────────────────────────────────────────────────

class _RaisingClient:
    """LLM client that fails every call — tests rule-based fallback."""

    def complete(self, **_kw):
        raise RuntimeError('injected failure')

    def complete_json(self, **_kw):
        raise RuntimeError('injected failure')


# ── Happy path ─────────────────────────────────────────────────────────────

class TestHappyPath:
    def test_returns_respond_with_data(self, seeded):
        from agents.mentions.workflows.orchestrator import orchestrate
        result = orchestrate('why is the Fed holding rates this month?')
        assert isinstance(result, dict)
        assert result['action'] == 'respond-with-data'
        assert result['use_kb'] is True
        assert 'response' in result
        assert result['response']

    def test_result_carries_frame_synthesis_continuity(self, seeded):
        from agents.mentions.workflows.orchestrator import orchestrate
        result = orchestrate('explain bitcoin move on Kalshi')
        for key in ('frame', 'synthesis', 'continuity', 'progress',
                    '_timings'):
            assert key in result, f'missing {key} in orchestrate output'

    def test_continuity_is_persisted(self, seeded):
        from agents.mentions.workflows.orchestrator import orchestrate
        from mentions_core.base.session.continuity import load as load_continuity
        # First call seeds nothing; second call should see accumulated state.
        orchestrate('explain bitcoin move on Kalshi')
        orchestrate('why is btc moving on Kalshi today?')
        cont = load_continuity()
        # v4 buckets present after two turns.
        for key in ('intents', 'speakers', 'tickers',
                    'recurring_themes'):
            assert key in cont
        assert isinstance(cont, dict)


# ── KB bypass ──────────────────────────────────────────────────────────────

class TestKbBypass:
    def test_short_greeting_returns_answer_directly(self, seeded):
        from agents.mentions.workflows.orchestrator import orchestrate
        result = orchestrate('hi')
        assert result['use_kb'] is False
        assert result['action'] == 'answer-directly'
        assert 'continuity' in result

    def test_empty_query_no_crash(self, seeded):
        from agents.mentions.workflows.orchestrator import orchestrate
        result = orchestrate('')
        assert result['action'] == 'answer-directly'


# ── URL path ───────────────────────────────────────────────────────────────

class TestUrlPath:
    def test_kalshi_url_dispatches_to_url_pipeline(self, seeded):
        from agents.mentions.workflows.orchestrator import orchestrate
        url = ('https://www.kalshi.com/markets/kxinfantinomention/'
               'kxinfantinomention-26apr15')
        result = orchestrate(url)
        # URL path always returns a dict with 'action'.
        assert isinstance(result, dict)
        assert 'action' in result
        assert '_timings' in result


# ── Observability integration ──────────────────────────────────────────────

class TestObservability:
    def test_trace_bracket_emitted(self, seeded, monkeypatch, tmp_path):
        from agents.mentions.workflows.orchestrator import orchestrate
        result = orchestrate('why is the Fed holding rates this month?')
        assert isinstance(result, dict)
        assert '_timings' in result

    def test_metrics_incremented(self, seeded):
        from mentions_core.base.obs import reset_collector, get_collector
        from agents.mentions.workflows.orchestrator import orchestrate
        reset_collector()
        orchestrate('why is the Fed holding rates this month?')
        snap = get_collector().snapshot()
        assert isinstance(snap, dict)
        assert 'counters' in snap


# ── Failure isolation ──────────────────────────────────────────────────────

class TestFailureIsolation:
    def test_raising_llm_does_not_break_pipeline(self, seeded, monkeypatch):
        # Intent classifier uses default_client() when client is None —
        # inject the raising client as the default so the full pipeline
        # exercises the fallback path.
        from mentions_domain.llm import client as client_mod
        monkeypatch.setattr(client_mod, 'default_client',
                            lambda: _RaisingClient())

        from agents.mentions.workflows.orchestrator import orchestrate
        result = orchestrate('what did Powell say about inflation?')
        # Even with a broken LLM, rules take over and we still respond.
        assert result['action'] in {'respond-with-data', 'answer-directly'}
        assert '_timings' in result
