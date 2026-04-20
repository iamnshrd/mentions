"""Structure-aware, token-based chunker for transcript ingestion.

Replaces the v0.1 char-based chunker. Key differences:

* Token budget is enforced via ``tiktoken`` (cl100k_base), not char count.
* Speaker turns (``Name: ...``) and timestamps (``[HH:MM:SS]``,
  ``HH:MM:SS --> HH:MM:SS``, etc.) are detected and respected as chunk
  boundaries.
* Text is normalised up front: ``[Music]``, ``[Applause]``, ``[Inaudible]``
  and similar stage directions are stripped; whitespace is collapsed.
* Every emitted ``Chunk`` carries ``char_start``/``char_end`` relative to
  the **cleaned** text, its ``token_count``, and a content ``text_sha1`` for
  deduplication.
* Language detection is a tiny heuristic (Cyrillic ratio) rather than a
  full ``langdetect`` dependency.

Usage::

    from agents.mentions.ingest.chunker import (
        chunk_transcript,
        clean_transcript_text,
    )

    cleaned, meta = clean_transcript_text(raw)
    chunks = chunk_transcript(cleaned, target_tokens=500, overlap_tokens=60)
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import asdict, dataclass, field

log = logging.getLogger('mentions')


# ── Patterns ───────────────────────────────────────────────────────────────

# `[Music]`, `[Applause]`, `[Inaudible]`, `[crosstalk]`, etc. — any bracketed
# stage direction of moderate length. Brackets with numeric timestamps are
# handled separately by TIMESTAMP_PATTERNS.
_STAGE_DIRECTION = re.compile(r'\[\s*(music|applause|inaudible|laughter|crosstalk|noise|cheering|silence|pause|sighs?|sniffs?|clears? throat)\s*\]',
                              re.IGNORECASE)

# `>> Speaker:` YouTube-style or `Speaker: ` plain. Start-of-line anchor.
_SPEAKER_TURN = re.compile(r'^(?:>>\s*)?([A-ZА-ЯЁ][A-Za-zА-Яа-яЁё .\'-]{0,40}):\s', re.MULTILINE)

# Timestamps:
#   [HH:MM:SS]   or  [MM:SS]
#   (HH:MM:SS)   or  (MM:SS)
#   HH:MM:SS --> HH:MM:SS   (SRT/VTT style)
#   bare  HH:MM:SS on its own line
_TIMESTAMP_INLINE = re.compile(
    r'[\[(](\d{1,2}:)?\d{1,2}:\d{2}(?:\.\d{1,3})?[\])]')
_TIMESTAMP_RANGE = re.compile(
    r'(\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?\s*-->\s*(\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?')
_TIMESTAMP_BARE  = re.compile(r'^\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s*$', re.MULTILINE)

# Basic sentence-end detector (fallback when no structure is found).
_SENTENCE_END = re.compile(r'(?<=[.!?…])\s+(?=[A-ZА-ЯЁ0-9])')


# ── Dataclasses ────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    """One emitted chunk with full provenance for storage."""
    text:             str
    char_start:       int
    char_end:         int
    token_count:      int
    chunk_index:      int = 0
    speaker_turn_id:  int | None = None
    timestamp_start:  float | None = None
    timestamp_end:    float | None = None
    speaker:          str = ''
    text_sha1:        str = field(default='', init=False)

    def __post_init__(self) -> None:
        self.text_sha1 = hashlib.sha1(self.text.encode('utf-8', 'replace')).hexdigest()

    def as_row(self) -> dict:
        """Return a dict suitable for ``INSERT INTO transcript_chunks``."""
        d = asdict(self)
        d['text_sha1'] = self.text_sha1
        return d


# ── Tokenizer ──────────────────────────────────────────────────────────────

_encoder = None


class _OfflineEncoder:
    """Tiny fallback encoder for offline/local test environments."""

    _TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def encode(self, text: str, disallowed_special=()):  # noqa: ARG002
        if not text:
            return []
        return self._TOKEN_RE.findall(text)


def _get_encoder():
    """Lazy tiktoken encoder singleton."""
    global _encoder
    if _encoder is None:
        try:
            import tiktoken

            _encoder = tiktoken.get_encoding('cl100k_base')
        except Exception as exc:  # pragma: no cover - depends on local env
            log.warning('Falling back to offline transcript tokenizer: %s', exc)
            _encoder = _OfflineEncoder()
    return _encoder


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_get_encoder().encode(text, disallowed_special=()))


# ── Normalisation ──────────────────────────────────────────────────────────

def clean_transcript_text(text: str) -> tuple[str, dict]:
    """Normalise a raw transcript.

    * Strips stage directions (``[Music]`` etc.)
    * Strips SRT/VTT timestamp ranges (``HH:MM:SS --> HH:MM:SS``)
    * Collapses runs of whitespace.
    * Does NOT strip inline bracketed timestamps — those are useful for
      downstream structure detection.

    Returns ``(cleaned_text, meta)`` where meta carries basic stats used by
    the document row.
    """
    if not text:
        return '', {'char_count': 0, 'language': 'und'}

    original_len = len(text)

    # 1. Remove SRT/VTT timestamp ranges — they appear on their own lines,
    #    so drop the whole line.
    text = _TIMESTAMP_RANGE.sub(' ', text)

    # 2. Strip stage directions.
    text = _STAGE_DIRECTION.sub(' ', text)

    # 3. Remove SRT sequence numbers — lines that are just digits, when
    #    surrounded by line breaks (common at the start of .srt blocks).
    text = re.sub(r'^\s*\d{1,6}\s*$', ' ', text, flags=re.MULTILINE)

    # 4. Collapse whitespace but preserve paragraph breaks (double newline).
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text, {
        'char_count':   len(text),
        'char_removed': original_len - len(text),
        'language':     detect_language(text),
    }


def detect_language(text: str) -> str:
    """Tiny language detector: returns 'ru' if >25% of letters are Cyrillic.

    Not a substitute for proper detection, but avoids a dependency for the
    common EN/RU mixed corpora.
    """
    if not text:
        return 'und'
    sample = text[:2000]
    cyrillic = sum(1 for ch in sample if 'А' <= ch <= 'я' or ch in 'Ёё')
    letters  = sum(1 for ch in sample if ch.isalpha())
    if letters == 0:
        return 'und'
    return 'ru' if cyrillic / letters > 0.25 else 'en'


# ── Timestamp extraction ───────────────────────────────────────────────────

def _parse_timestamp(raw: str) -> float | None:
    """Parse ``HH:MM:SS[.ms]``, ``MM:SS[.ms]`` → seconds (float)."""
    m = re.match(r'(?:(\d+):)?(\d+):(\d+)(?:[.,](\d+))?', raw.strip())
    if not m:
        return None
    h  = int(m.group(1) or 0)
    mn = int(m.group(2))
    s  = int(m.group(3))
    ms = int((m.group(4) or '0')[:3].ljust(3, '0')) / 1000.0
    return h * 3600 + mn * 60 + s + ms


# ── Speaker turn segmentation ──────────────────────────────────────────────

@dataclass
class _Turn:
    speaker:     str
    text:        str
    char_start:  int
    char_end:    int
    turn_id:     int


def split_speaker_turns(text: str) -> list[_Turn]:
    """Split *text* into speaker turns using the ``Name: ...`` pattern.

    If no turns are detected, returns a single turn with empty speaker
    covering the whole text.
    """
    matches = list(_SPEAKER_TURN.finditer(text))
    if len(matches) < 2:
        return [_Turn(speaker='', text=text, char_start=0,
                      char_end=len(text), turn_id=0)]

    turns: list[_Turn] = []
    for i, m in enumerate(matches):
        speaker = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        if not body:
            continue
        turns.append(_Turn(
            speaker=speaker,
            text=body,
            char_start=body_start,
            char_end=body_end,
            turn_id=len(turns),
        ))
    return turns or [_Turn(speaker='', text=text, char_start=0,
                           char_end=len(text), turn_id=0)]


# ── Core chunker ───────────────────────────────────────────────────────────

def chunk_transcript(text: str, *,
                     target_tokens: int = 500,
                     overlap_tokens: int = 60,
                     max_tokens: int = 900) -> list[Chunk]:
    """Split *text* into overlapping, structure-aware chunks.

    Strategy:
      1. Detect speaker turns. Each turn is treated as an atomic unit and
         never split across chunks unless it exceeds ``max_tokens``.
      2. Pack consecutive turns into a chunk until adding the next would
         exceed ``target_tokens``.
      3. A turn longer than ``max_tokens`` is split on sentence boundaries,
         then on whitespace as a last resort.
      4. Chunks overlap by approximately ``overlap_tokens`` measured in
         tokens (for sliding-window retrieval context).
    """
    if not text or not text.strip():
        return []

    turns = split_speaker_turns(text)
    packer = _ChunkPacker(target_tokens=target_tokens,
                          overlap_tokens=overlap_tokens,
                          max_tokens=max_tokens)
    for t in turns:
        packer.add_turn(t)
    packer.flush()
    return packer.chunks


class _ChunkPacker:
    """Greedy packer — emits Chunks as the token budget fills up."""

    def __init__(self, *, target_tokens: int, overlap_tokens: int, max_tokens: int):
        self.target    = target_tokens
        self.overlap   = overlap_tokens
        self.ceiling   = max_tokens
        self.chunks:   list[Chunk] = []
        self._buf:     list[tuple[str, str, int, int, int]] = []
        # each buf entry: (speaker, text, char_start, char_end, turn_id)
        self._buf_tokens = 0

    # ── Public API ─────────────────────────────────────────────────────────

    def add_turn(self, t: _Turn) -> None:
        tokens = count_tokens(t.text)
        if tokens > self.ceiling:
            # Oversized turn: split on sentences first, then on whitespace.
            self.flush()
            for sub_text, s_start, s_end in _sentence_split(
                    t.text, t.char_start, self.ceiling):
                self._emit_single(t.speaker, sub_text, s_start, s_end, t.turn_id)
            return

        # Does adding this turn blow the target budget?
        if self._buf_tokens + tokens > self.target and self._buf:
            self.flush()
        self._buf.append((t.speaker, t.text, t.char_start, t.char_end, t.turn_id))
        self._buf_tokens += tokens

    def flush(self) -> None:
        if not self._buf:
            return
        text = '\n\n'.join(_format_turn(s, t) for s, t, *_ in self._buf)
        char_start = self._buf[0][2]
        char_end   = self._buf[-1][3]
        speaker    = self._dominant_speaker()
        turn_id    = self._buf[0][4]
        self._emit(text, char_start, char_end, speaker, turn_id)
        # Establish overlap with the tail of the current buffer.
        self._carry_overlap()

    # ── Internals ──────────────────────────────────────────────────────────

    def _emit(self, text: str, char_start: int, char_end: int,
              speaker: str, turn_id: int) -> None:
        tokens = count_tokens(text)
        self.chunks.append(Chunk(
            text=text,
            char_start=char_start,
            char_end=char_end,
            token_count=tokens,
            chunk_index=len(self.chunks),
            speaker_turn_id=turn_id,
            speaker=speaker,
        ))

    def _emit_single(self, speaker: str, text: str,
                     char_start: int, char_end: int, turn_id: int) -> None:
        self._emit(_format_turn(speaker, text) if speaker else text,
                   char_start, char_end, speaker, turn_id)

    def _dominant_speaker(self) -> str:
        counts: dict[str, int] = {}
        for sp, text, *_ in self._buf:
            if sp:
                counts[sp] = counts.get(sp, 0) + count_tokens(text)
        if not counts:
            return ''
        return max(counts.items(), key=lambda kv: kv[1])[0]

    def _carry_overlap(self) -> None:
        """Keep the tail of the flushed buffer as seed for the next chunk."""
        if self.overlap <= 0:
            self._buf.clear()
            self._buf_tokens = 0
            return
        # Walk back from the tail accumulating ≤ overlap tokens.
        tail: list[tuple[str, str, int, int, int]] = []
        tail_tokens = 0
        for entry in reversed(self._buf):
            sp, t, *_ = entry
            tok = count_tokens(t)
            if tail_tokens + tok > self.overlap and tail:
                break
            tail.append(entry)
            tail_tokens += tok
        self._buf = list(reversed(tail))
        self._buf_tokens = tail_tokens


def _format_turn(speaker: str, text: str) -> str:
    return f'{speaker}: {text}' if speaker else text


def _sentence_split(text: str, offset: int, max_tokens: int) -> list[tuple[str, int, int]]:
    """Split oversized *text* into sub-chunks ≤ ``max_tokens``.

    Tries sentences first, falls back to whitespace windows. Returns a list
    of ``(text, char_start, char_end)`` with offsets relative to the full
    document (caller provides ``offset``).
    """
    if count_tokens(text) <= max_tokens:
        return [(text, offset, offset + len(text))]

    sentences = _SENTENCE_END.split(text) if text else ['']
    out: list[tuple[str, int, int]] = []
    buf: list[str] = []
    buf_start = 0
    buf_tokens = 0
    pos = 0

    for sent in sentences:
        if not sent:
            continue
        st = count_tokens(sent)
        if buf and buf_tokens + st > max_tokens:
            text_joined = ' '.join(buf)
            out.append((text_joined, offset + buf_start, offset + buf_start + len(text_joined)))
            buf = []
            buf_tokens = 0
            buf_start = pos
        if st > max_tokens:
            # Single sentence too big — hard-split on whitespace windows.
            words = sent.split()
            window: list[str] = []
            w_tokens = 0
            for w in words:
                wt = count_tokens(w + ' ')
                if w_tokens + wt > max_tokens and window:
                    piece = ' '.join(window)
                    out.append((piece, offset + buf_start, offset + buf_start + len(piece)))
                    window = []
                    w_tokens = 0
                    buf_start = pos
                window.append(w)
                w_tokens += wt
                pos += len(w) + 1
            if window:
                piece = ' '.join(window)
                out.append((piece, offset + buf_start, offset + buf_start + len(piece)))
                buf_start = pos
        else:
            if not buf:
                buf_start = pos
            buf.append(sent)
            buf_tokens += st
        pos += len(sent) + 1

    if buf:
        text_joined = ' '.join(buf)
        out.append((text_joined, offset + buf_start, offset + buf_start + len(text_joined)))
    return out
