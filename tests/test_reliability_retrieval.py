"""Tests for reliability-weighted retrieval (v0.14.1).

The Beta(α, β) posterior on speaker_profiles should nudge retrieval
rankings: high-posterior speakers' chunks bubble up, low-posterior
ones sink. Untested speakers keep a neutral weight of 1.0.
"""
from __future__ import annotations

import sqlite3

import pytest

from mentions_domain.retrieval import RetrievalHit
from mentions_domain.retrieval.reliability import speaker_weight
from agents.mentions.services.retrieval.reliability import (
    apply_weights, speaker_weights,
)


# ── Pure helpers ──────────────────────────────────────────────────────────

class TestSpeakerWeight:
    def test_uniform_prior_no_history_is_neutral(self):
        assert speaker_weight(1.0, 1.0, n_apps=0) == 1.0
        assert speaker_weight(1.0, 1.0, n_apps=2) == 1.0

    def test_missing_values_neutral(self):
        assert speaker_weight(None, None, n_apps=10) == 1.0

    def test_good_speaker_boosted(self):
        # 9 wins, 0 losses → α=10, β=1, p=10/11 ≈ 0.91, weight ≈ 1.41
        w = speaker_weight(10.0, 1.0, n_apps=9)
        assert 1.35 < w <= 1.5

    def test_bad_speaker_penalised(self):
        # 0 wins, 9 losses → α=1, β=10, p≈0.09, weight ≈ 0.59
        w = speaker_weight(1.0, 10.0, n_apps=9)
        assert 0.5 <= w < 0.65

    def test_bounded_in_half_to_onehalf(self):
        # Extreme α with huge β still yields p ∈ [0,1] → weight ∈ [0.5, 1.5]
        for a, b in [(1.0, 1000.0), (1000.0, 1.0), (500.0, 500.0)]:
            w = speaker_weight(a, b, n_apps=10)
            assert 0.5 <= w <= 1.5

    def test_respects_min_applications(self):
        # 2 wins, 0 losses but n=2 < default min=3 → neutral
        assert speaker_weight(3.0, 1.0, n_apps=2) == 1.0


# ── DB-backed query ───────────────────────────────────────────────────────

def _insert_speaker(conn, name, alpha=1.0, beta=1.0):
    conn.execute(
        'INSERT INTO speaker_profiles (canonical_name, alpha, beta) '
        'VALUES (?, ?, ?)',
        (name, alpha, beta),
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def _insert_applications(conn, speaker_id, wins, losses):
    for _ in range(wins):
        conn.execute(
            'INSERT INTO speaker_stance_applications '
            '(speaker_profile_id, outcome) VALUES (?, 1)',
            (speaker_id,),
        )
    for _ in range(losses):
        conn.execute(
            'INSERT INTO speaker_stance_applications '
            '(speaker_profile_id, outcome) VALUES (?, 0)',
            (speaker_id,),
        )


class TestSpeakerWeightsQuery:
    def test_returns_empty_for_unknown(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            assert speaker_weights(conn, ['Nobody Knows Me']) == {}

    def test_returns_empty_for_no_input(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            assert speaker_weights(conn, []) == {}
            assert speaker_weights(conn, ['', None, '  ']) == {}

    def test_neutral_speakers_omitted(self, tmp_db):
        """Speakers with no history (weight=1.0) shouldn't clutter the dict."""
        with sqlite3.connect(tmp_db) as conn:
            _insert_speaker(conn, 'Jerome Powell')
            conn.commit()
            w = speaker_weights(conn, ['Jerome Powell'])
        assert w == {}

    def test_boosts_good_speaker(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            sid = _insert_speaker(conn, 'Good Speaker', alpha=10.0, beta=1.0)
            _insert_applications(conn, sid, wins=9, losses=0)
            conn.commit()
            w = speaker_weights(conn, ['Good Speaker'])
        assert w.get('good speaker', 1.0) > 1.3

    def test_penalises_bad_speaker(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            sid = _insert_speaker(conn, 'Bad Speaker', alpha=1.0, beta=10.0)
            _insert_applications(conn, sid, wins=0, losses=9)
            conn.commit()
            w = speaker_weights(conn, ['Bad Speaker'])
        assert w.get('bad speaker', 1.0) < 0.7

    def test_case_insensitive_match(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            sid = _insert_speaker(conn, 'Jane Doe', alpha=8.0, beta=1.0)
            _insert_applications(conn, sid, wins=7, losses=0)
            conn.commit()
            w = speaker_weights(conn, ['JANE DOE', 'jane doe', 'Jane Doe'])
        # All three should collapse to the same key.
        assert len(w) == 1
        assert 'jane doe' in w


# ── apply_weights ─────────────────────────────────────────────────────────

class TestApplyWeights:
    def _hit(self, cid=1, speaker='', score_final=1.0):
        return RetrievalHit(
            chunk_id=cid, document_id=1, text='x', speaker=speaker,
            section='', event='', event_date='',
            token_count=10, score_final=score_final,
        )

    def test_unknown_speaker_unchanged(self):
        h = self._hit(speaker='Someone Else', score_final=2.0)
        apply_weights([h], {'jerome powell': 1.4})
        assert h.score_final == 2.0
        assert h.score_reliability == 1.0

    def test_known_speaker_multiplied(self):
        h = self._hit(speaker='Jerome Powell', score_final=2.0)
        apply_weights([h], {'jerome powell': 1.4})
        assert h.score_final == pytest.approx(2.8, abs=1e-9)
        assert h.score_reliability == 1.4

    def test_case_insensitive(self):
        h = self._hit(speaker='  JEROME Powell  ', score_final=1.0)
        apply_weights([h], {'jerome powell': 0.6})
        assert h.score_final == pytest.approx(0.6, abs=1e-9)

    def test_empty_speaker_neutral(self):
        h = self._hit(speaker='', score_final=1.0)
        apply_weights([h], {'jerome powell': 1.4})
        assert h.score_final == 1.0
        assert h.score_reliability == 1.0


# ── End-to-end: two speakers with tied BM25 ───────────────────────────────

class TestPipelineIntegration:
    def test_reliable_speaker_outranks_unreliable_when_otherwise_tied(
        self, tmp_db,
    ):
        """If BM25 ties two chunks, the reliable speaker's wins."""
        # Set up: two speakers, two transcript docs, one chunk each, same text.
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            good = _insert_speaker(conn, 'Good Speaker',
                                   alpha=10.0, beta=1.0)
            bad  = _insert_speaker(conn, 'Bad Speaker',
                                   alpha=1.0, beta=10.0)
            _insert_applications(conn, good, wins=9, losses=0)
            _insert_applications(conn, bad,  wins=0, losses=9)

            # Minimal transcript_documents + chunks rows.
            for i, (name, text) in enumerate([
                ('Good Speaker', 'inflation expectations rising fast'),
                ('Bad Speaker',  'inflation expectations rising fast'),
            ], start=1):
                conn.execute(
                    "INSERT INTO transcript_documents "
                    "(id, event, event_date, source_url) "
                    "VALUES (?, 'FOMC', '2024-01-01', 'x')",
                    (i,),
                )
                conn.execute(
                    '''INSERT INTO transcript_chunks
                       (id, document_id, speaker, section, text, token_count)
                       VALUES (?, ?, ?, 'prep', ?, 20)''',
                    (i, i, name, text),
                )
                conn.execute(
                    'INSERT INTO transcript_chunks_fts (rowid, text, speaker) '
                    'VALUES (?, ?, ?)',
                    (i, text, name),
                )
            conn.commit()

        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        hits = hybrid_retrieve('inflation expectations', limit=5)
        assert len(hits) == 2
        # Good speaker's chunk should come first.
        assert hits[0].speaker == 'Good Speaker'
        assert hits[0].score_reliability > 1.0
        assert hits[1].speaker == 'Bad Speaker'
        assert hits[1].score_reliability < 1.0

    def test_disable_flag_preserves_neutral_scoring(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            good = _insert_speaker(conn, 'Good Speaker',
                                   alpha=10.0, beta=1.0)
            _insert_applications(conn, good, wins=9, losses=0)
            conn.execute(
                "INSERT INTO transcript_documents (id, event, event_date, "
                "source_url) VALUES (1, 'FOMC', '2024-01-01', 'x')",
            )
            conn.execute(
                '''INSERT INTO transcript_chunks
                   (id, document_id, speaker, section, text, token_count)
                   VALUES (1, 1, 'Good Speaker', 'prep',
                           'inflation expectations', 20)''',
            )
            conn.execute(
                'INSERT INTO transcript_chunks_fts (rowid, text, speaker) '
                'VALUES (1, ?, ?)',
                ('inflation expectations', 'Good Speaker'),
            )
            conn.commit()

        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        hits = hybrid_retrieve('inflation expectations', limit=5,
                               reliability_weight=False)
        assert hits
        assert hits[0].score_reliability == 1.0
