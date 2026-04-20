"""Tests for connection-level PRAGMA defaults (v0.14.6 — D7)."""
from __future__ import annotations

import sqlite3

import pytest

from agents.mentions.db import connect


class TestJournalMode:
    def test_wal_enabled(self, tmp_db):
        with connect(db_path=tmp_db, auto_migrate=False) as conn:
            mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
        assert mode.lower() == 'wal'

    def test_wal_persists_across_connections(self, tmp_db):
        # WAL is a persistent DB-level setting; a second open should
        # still report WAL without us re-issuing the pragma.
        with connect(db_path=tmp_db, auto_migrate=False):
            pass
        raw = sqlite3.connect(tmp_db)
        try:
            mode = raw.execute('PRAGMA journal_mode').fetchone()[0]
        finally:
            raw.close()
        assert mode.lower() == 'wal'


class TestSynchronous:
    def test_synchronous_normal(self, tmp_db):
        with connect(db_path=tmp_db, auto_migrate=False) as conn:
            val = conn.execute('PRAGMA synchronous').fetchone()[0]
        # 1 == NORMAL, 2 == FULL
        assert val == 1


class TestForeignKeys:
    def test_fk_still_on(self, tmp_db):
        with connect(db_path=tmp_db, auto_migrate=False) as conn:
            val = conn.execute('PRAGMA foreign_keys').fetchone()[0]
        assert val == 1


class TestSchemaStillMigrates:
    def test_version_matches_latest(self, tmp_db):
        from agents.mentions.storage.knowledge.migrate import LATEST_VERSION
        with connect(db_path=tmp_db) as conn:
            v = conn.execute('PRAGMA user_version').fetchone()[0]
        assert v == LATEST_VERSION
