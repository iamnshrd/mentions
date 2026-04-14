"""Filesystem-backed StateStore implementation for the Mentions agent.

Layout: ``{workspace}/{user_id}/{key}.json`` (or ``.jsonl`` for append-only
keys).  When *user_id* is ``"default"`` the files live directly in
``{workspace}/`` for backward compatibility with the pre-multi-tenant layout.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from library.utils import now_iso

log = logging.getLogger('mentions')

_JSONL_KEYS = frozenset({'session_checkpoints'})


class FileSystemStore:
    """Persist per-user state as JSON files under *workspace*."""

    def __init__(self, workspace: Path):
        self._ws = workspace
        self._jsonl_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}

    # -- path helpers -------------------------------------------------------

    def _user_dir(self, user_id: str) -> Path:
        if user_id == 'default':
            return self._ws
        return self._ws / user_id

    def _path(self, user_id: str, key: str) -> Path:
        ext = '.jsonl' if key in _JSONL_KEYS else '.json'
        return self._user_dir(user_id) / (key + ext)

    # -- protocol methods ---------------------------------------------------

    def get_json(self, user_id: str, key: str,
                 default: dict | None = None) -> dict:
        p = self._path(user_id, key)
        if not p.exists():
            return default if default is not None else {}
        try:
            result = json.loads(p.read_text(encoding='utf-8'))
            if not isinstance(result, dict):
                log.warning('fs_store: %s is %s, expected dict — using default',
                            p, type(result).__name__)
                return default if default is not None else {}
            return result
        except (json.JSONDecodeError, OSError) as exc:
            log.warning('fs_store: failed to load %s: %s', p, exc)
            return default if default is not None else {}

    def put_json(self, user_id: str, key: str, value: dict) -> None:
        import os, tempfile
        p = self._path(user_id, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
            os.replace(tmp, str(p))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def append_jsonl(self, user_id: str, key: str, event: dict) -> None:
        p = self._user_dir(user_id) / (key + '.jsonl')
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
        self._jsonl_cache.pop((user_id, key), None)

    def read_jsonl(self, user_id: str, key: str) -> list[dict]:
        p = self._user_dir(user_id) / (key + '.jsonl')
        if not p.exists():
            return []
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        cache_key = (user_id, key)
        cached = self._jsonl_cache.get(cache_key)
        if cached and cached[0] == mtime:
            return cached[1]
        rows: list[dict] = []
        for line in p.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
        self._jsonl_cache[cache_key] = (mtime, rows)
        return rows
