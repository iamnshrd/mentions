"""Speaker-reliability weighting for retrieval scores."""
from __future__ import annotations

import logging
import sqlite3

from mentions_domain.retrieval.reliability import (
    apply_weights,
    speaker_weight as _speaker_weight,
)

log = logging.getLogger('mentions')


def speaker_weights(conn: sqlite3.Connection,
                    speaker_names: list[str]) -> dict[str, float]:
    """Return ``{name_lower: weight}`` for the given speaker names."""
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
        if w != 1.0:
            out[lname] = round(w, 4)
    return out

