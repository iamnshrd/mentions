"""Speaker-reliability weighting for retrieval scores.

Schema v5 gives every ``speaker_profiles`` row a Beta(α, β) posterior
over "when this speaker shows up in the evidence, does the agent's
decision end up right?". Pre-v0.14.1 retrieval ignored that column:
a well-calibrated speaker and a noisy one ranked identically in
BM25 / RRF / MMR as long as their chunks shared lexical overlap with
the query.

This module closes that loop. After RRF fusion (but before MMR
diversification), each hit's ``score_final`` is multiplied by a
reliability weight derived from its speaker's posterior. Speakers
with fewer than ``min_applications`` outcomes get weight 1.0
(baseline — "no track record, no prejudice"), so new speakers are
not penalised. Speakers with a meaningful track record get pushed
up or down in the range [0.5, 1.5]::

    weight = 0.5 + posterior_p(α, β)

A speaker with 90 % success rate gets a 1.4× boost; a speaker with
10 % gets 0.6×. A perfectly-balanced speaker (50/50) stays at 1.0.

Matching: chunk rows carry a ``speaker`` column (raw string extracted
during transcript ingest); speaker profiles carry a
``canonical_name``. We case-insensitive-match on canonical_name only
for the MVP — alias matching is a later refinement once the speaker
catalogue grows.
"""
from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger('mentions')


# ── Tunables ──────────────────────────────────────────────────────────────

_MIN_APPLICATIONS = 3            # need this many outcomes before we trust it
_WEIGHT_BASE      = 0.5          # p=0 → 0.5, p=1 → 1.5, p=0.5 → 1.0
_WEIGHT_NEUTRAL   = 1.0


def _speaker_weight(alpha: float | None, beta: float | None,
                    n_apps: int, *, min_apps: int = _MIN_APPLICATIONS) -> float:
    """Map (α, β, n) → a score multiplier.

    Returns :data:`_WEIGHT_NEUTRAL` when evidence is too thin. Bounded
    in ``[0.5, 1.5]`` by construction — the multiplier can only nudge,
    never dominate, so a bad speaker still surfaces if their BM25
    overlap with the query is overwhelming.
    """
    if alpha is None or beta is None or n_apps < min_apps:
        return _WEIGHT_NEUTRAL
    total = float(alpha) + float(beta)
    if total <= 0:
        return _WEIGHT_NEUTRAL
    p = float(alpha) / total
    return _WEIGHT_BASE + p


def speaker_weights(conn: sqlite3.Connection,
                    speaker_names: list[str]) -> dict[str, float]:
    """Return ``{name_lower: weight}`` for the given speaker names.

    Unknown / unmatched names are omitted from the returned dict, so
    callers can treat "missing key" as "no adjustment". Duplicates
    and empty strings in *speaker_names* are coalesced.
    """
    names = {(n or '').strip().lower() for n in speaker_names if n}
    names.discard('')
    if not names:
        return {}
    placeholders = ','.join('?' * len(names))
    out: dict[str, float] = {}
    try:
        rows = conn.execute(
            f'''SELECT LOWER(s.canonical_name) AS lname,
                       s.alpha, s.beta,
                       (SELECT COUNT(*) FROM speaker_stance_applications a
                         WHERE a.speaker_profile_id = s.id) AS n
                  FROM speaker_profiles s
                 WHERE LOWER(s.canonical_name) IN ({placeholders})''',
            tuple(names),
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('speaker_weights query failed: %s', exc)
        return {}
    for lname, a, b, n in rows:
        w = _speaker_weight(a, b, n or 0)
        # Only emit when the weight actually differs from neutral —
        # callers treat missing keys as 1.0, and suppressing neutrals
        # keeps the dict small and the diff obvious in traces.
        if w != _WEIGHT_NEUTRAL:
            out[lname] = round(w, 4)
    return out


def apply_weights(hits, weights: dict[str, float]) -> None:
    """In-place: multiply ``hit.score_final`` by the matching weight.

    Also attaches ``hit.score_reliability`` for downstream
    introspection — the multiplier that was applied. Hits whose
    speaker isn't in *weights* are untouched (multiplier 1.0).
    """
    for h in hits:
        # v0.14.6 (T1): prefer canonical name for the lookup when the
        # ingest path resolved one; fall back to the raw surface.
        key = (getattr(h, 'speaker_canonical', '') or h.speaker or '')
        w = weights.get(key.strip().lower(), _WEIGHT_NEUTRAL)
        setattr(h, 'score_reliability', w)
        h.score_final *= w
