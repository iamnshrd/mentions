"""Resolve surface speaker names to canonical profile names.

Panel transcripts yield a soup of surface variants — "Jerome Powell",
"Chair Powell", "J. Powell", "JEROME POWELL", "Powell". The
reliability-weighted retrieval layer (v0.14.1) joins on
``speaker_profiles.canonical_name``; surface drift breaks that join
without any error, just silent misses.

This module provides one entry point, :func:`canonicalize`, that
takes a raw surface name and returns the matching
``speaker_profiles.canonical_name`` or ``None``. The match policy is
intentionally conservative:

1. **Exact case-insensitive hit** on ``canonical_name``.
2. **Exact hit** against any entry in the speaker's ``aliases`` JSON
   array (also case-insensitive, trimmed).
3. **Last-name containment** — if the surface string ends with a
   token that appears as the last whitespace-separated token of a
   single canonical name (unique suffix match), we take that. "Chair
   Powell" → "Jerome Powell" works; "Smith" would only resolve if
   exactly one canonical has "Smith" as its final token.

Anything else returns ``None``. We deliberately do **not** do
fuzzy/Levenshtein matching — the risk of collapsing "Powell" and
"Howell" is worse than leaving a few surface names unresolved.

The resolver caches the profile table in-process so repeated lookups
during a single ingest don't re-hit SQLite per chunk. Cache is keyed
by a simple version tag the caller can bust with
:func:`invalidate_cache` after writing new profiles.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading

log = logging.getLogger('mentions')

_LOCK = threading.Lock()
_CACHE: dict[int, list[tuple[str, list[str]]]] | None = None


def invalidate_cache() -> None:
    """Drop the in-process profile cache.

    Call after inserting/updating/deleting ``speaker_profiles`` rows so
    the next resolve sees the new state.
    """
    global _CACHE
    with _LOCK:
        _CACHE = None


def _load_profiles(conn: sqlite3.Connection) -> list[tuple[str, list[str]]]:
    """Return ``[(canonical_name, aliases), ...]`` from the cache or DB."""
    global _CACHE
    with _LOCK:
        if _CACHE is not None:
            return _CACHE
        rows = conn.execute(
            'SELECT canonical_name, aliases FROM speaker_profiles'
        ).fetchall()
        out: list[tuple[str, list[str]]] = []
        for canonical, aliases_json in rows:
            aliases: list[str] = []
            if aliases_json:
                try:
                    parsed = json.loads(aliases_json)
                    if isinstance(parsed, list):
                        aliases = [str(x).strip() for x in parsed if x]
                except (ValueError, TypeError):
                    log.debug('bad aliases JSON for %s: %r',
                              canonical, aliases_json)
            out.append((canonical, aliases))
        _CACHE = out
        return out


def canonicalize(surface_name: str,
                 conn: sqlite3.Connection | None = None,
                 profiles: list[tuple[str, list[str]]] | None = None,
                 ) -> str | None:
    """Resolve *surface_name* → canonical_name or None.

    Caller can pass either *conn* (we load profiles) or a pre-loaded
    *profiles* list (batched ingest path — avoids one DB hit per chunk).
    """
    if not surface_name or not surface_name.strip():
        return None
    surface = surface_name.strip()
    surface_lc = surface.lower()

    if profiles is None:
        if conn is None:
            return None
        profiles = _load_profiles(conn)
    if not profiles:
        return None

    # 1. Exact canonical match.
    for canonical, _aliases in profiles:
        if canonical.lower() == surface_lc:
            return canonical

    # 2. Alias match.
    for canonical, aliases in profiles:
        for a in aliases:
            if a and a.strip().lower() == surface_lc:
                return canonical

    # 3. Unique-suffix last-name match. Only fire when the surface
    #    token maps to exactly one canonical — prevents collapse.
    last_token = surface.split()[-1].lower() if surface.split() else ''
    if last_token:
        suffix_hits: list[str] = []
        for canonical, _ in profiles:
            parts = canonical.split()
            if parts and parts[-1].lower() == last_token:
                suffix_hits.append(canonical)
        if len(suffix_hits) == 1:
            return suffix_hits[0]

    return None


def canonicalize_batch(names: list[str], conn: sqlite3.Connection
                        ) -> dict[str, str | None]:
    """Resolve many surface names in one profile-table read."""
    profiles = _load_profiles(conn)
    return {n: canonicalize(n, profiles=profiles) for n in names}
