"""Section tagging for transcript chunks (v0.14.7 — T2).

The v1 schema carried a ``transcript_chunks.section`` TEXT column but
no writer ever populated it — every row was the empty string. That
was a wasted slot: the *section* a quote came from is a strong,
cheap signal orthogonal to content. Prepared remarks are
pre-scripted and rehearsed; Q&A is reactive, unpredictable, and
historically where policy surprises happen. A heuristic that works
on prepared-remarks Fed language may systematically fail on Q&A
answers — or vice versa.

This module labels each chunk with one of:

* ``intro``   — first prepared segment of the transcript
* ``prepared`` — mid-document prepared remarks (default for any
                 non-Q&A, non-intro, non-closing chunk)
* ``qa``      — a question from a reporter / committee member, or
                 any speaker turn that follows one until the next
                 sectional marker
* ``closing`` — the final prepared segment

Detection is rule-based (no LLM): look for Q&A trigger patterns
("question from", "next question", "Q:", "reporter:", etc.) in the
chunk text, and bucket by chunk position for intro/closing.

The tagger is a pure function over the chunker's ``Chunk`` list —
no DB access, no side effects. Called by ``_insert_chunks`` just
before the SQL INSERT so the ``section`` column is populated
cleanly from ingest onward. Re-running the tagger after a rechunk
is idempotent.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger('mentions')

# ── Q&A triggers ──────────────────────────────────────────────────────────

# Patterns that strongly indicate the start of (or continuation within)
# a Q&A section. Matched case-insensitively against the chunk text.
_QA_PATTERNS: list[re.Pattern] = [
    re.compile(r'\bquestion(?:s)?\s+from\b', re.I),
    re.compile(r'\bnext\s+question\b',       re.I),
    re.compile(r'\bi[\'’]?ll\s+take\s+(?:the\s+)?next\s+question\b', re.I),
    re.compile(r'\b(?:first|next|final)\s+question\b', re.I),
    re.compile(r'\b(?:reporter|journalist)[:,]',       re.I),
    # Line-start Q: / A: transcript marker
    re.compile(r'(?:^|\n)\s*Q[:\.]\s',                  re.I),
    re.compile(r'\bthanks?\s+(?:for|to)\s+taking\s+(?:my|your)\s+question\b',
               re.I),
    re.compile(r'\bwould\s+you\s+comment\s+on\b',        re.I),
    re.compile(r'\bcan\s+you\s+(?:comment|respond|elaborate)\b', re.I),
    re.compile(r'\bmr\.\s+chairman\b',                   re.I),
    re.compile(r'\bchair\s+\w+,\s+(?:you|do|can|could|how|what)\b', re.I),
]


def _looks_like_qa(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in _QA_PATTERNS)


# ── Closing triggers ──────────────────────────────────────────────────────

_CLOSING_PATTERNS: list[re.Pattern] = [
    re.compile(r'\bthank\s+you\s+(?:all\s+)?(?:very\s+much)?\b', re.I),
    re.compile(r'\bi[\'’]?ll\s+stop\s+there\b',                  re.I),
    re.compile(r'\bthat\s+concludes\b',                           re.I),
    re.compile(r'\bthis\s+concludes\b',                           re.I),
]


def _looks_like_closing(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in _CLOSING_PATTERNS)


# ── Public API ────────────────────────────────────────────────────────────

def tag_sections(chunks: list) -> list[str]:
    """Return a list of section labels, one per chunk.

    Passes once forward through *chunks*. Chunk position drives
    intro/closing defaults; Q&A pattern matches *latch* — once we see
    a Q&A trigger, every subsequent chunk is ``qa`` until the end of
    the transcript. That mirrors real press-conference structure:
    Q&A doesn't return to prepared remarks mid-session.

    Fallback for single-chunk or empty transcripts: the lone chunk
    (if any) is labelled ``prepared``.
    """
    n = len(chunks)
    if n == 0:
        return []
    if n == 1:
        return ['prepared']

    labels: list[str] = ['prepared'] * n
    in_qa = False
    qa_started_at: int | None = None

    # First pass — detect where Q&A starts (if anywhere).
    for i, c in enumerate(chunks):
        text = getattr(c, 'text', '') or ''
        if _looks_like_qa(text):
            in_qa = True
            qa_started_at = i
            break

    if in_qa and qa_started_at is not None:
        # Every chunk from qa_started_at onward is QA (latch).
        for i in range(qa_started_at, n):
            labels[i] = 'qa'

    # Intro: first chunk of any transcript with ≥ 2 chunks, unless it
    # already latched into Q&A (rare — press briefings that open
    # cold with a question).
    if labels[0] != 'qa':
        labels[0] = 'intro'

    # Closing: last chunk, *only* if it still looks prepared (i.e. not
    # part of a Q&A tail) AND carries a closing phrase. Press
    # conferences typically end on a Q&A tail, in which case we leave
    # the last chunk as ``qa``.
    last = n - 1
    if labels[last] == 'prepared':
        text = getattr(chunks[last], 'text', '') or ''
        if _looks_like_closing(text):
            labels[last] = 'closing'

    return labels
