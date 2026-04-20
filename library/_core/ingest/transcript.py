"""Register and index a single speaker transcript (v2 pipeline).

Pipeline:
1. Read source file (.txt or .pdf)
2. Normalise text (strip stage directions, SRT metadata, collapse whitespace)
3. Chunk via structure-aware token-based chunker
4. Insert transcript_documents + transcript_chunks into DB with full v2
   metadata (sha256, language, summary, token_count, char offsets, text_sha1,
   speaker_turn_id)
5. Incremental FTS sync for this document only

All new columns introduced in schema v2 are populated here; older callers
that only read v1 columns continue to work.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from library.utils import now_iso

log = logging.getLogger('mentions')


# ── Public API ─────────────────────────────────────────────────────────────

def register(source_file: str, speaker: str = '', event: str = '',
             event_date: str = '') -> dict:
    """Register and index a transcript file.

    *source_file* can be a path relative to library/transcripts/ or absolute.
    Returns a result dict with doc_id and chunk count.
    """
    from library.config import TRANSCRIPTS
    p = Path(source_file)
    if not p.is_absolute():
        p = TRANSCRIPTS / source_file
    if not p.exists():
        return {'error': f'File not found: {p}', 'status': 'error'}

    raw_text = _extract_text(p)
    if not raw_text:
        return {'error': 'Could not extract text from file', 'status': 'error'}

    from library._core.ingest.chunker import (
        chunk_transcript, clean_transcript_text,
    )
    cleaned, meta = clean_transcript_text(raw_text)
    chunks = chunk_transcript(cleaned)

    doc_id, new_doc = _upsert_document(
        path=p,
        raw_text=raw_text,
        cleaned_text=cleaned,
        meta=meta,
        speaker=speaker,
        event=event,
        event_date=event_date,
    )
    if new_doc or _chunk_count(doc_id) == 0:
        _insert_chunks(doc_id, chunks, default_speaker=speaker)
        _sync_fts(doc_id)
        action = 'indexed'
    else:
        log.info('Document %s already indexed (%d chunks); skipping',
                 p.name, _chunk_count(doc_id))
        action = 'already_indexed'

    log.info('Transcript %s: %s (chunks=%d tokens_total=%d lang=%s)',
             p.name, action, len(chunks),
             sum(c.token_count for c in chunks), meta['language'])

    return {
        'status':       action,
        'document_id':  doc_id,
        'file':         str(p),
        'speaker':      speaker,
        'event':        event,
        'chunks':       len(chunks),
        'tokens':       sum(c.token_count for c in chunks),
        'language':     meta['language'],
        'chars_removed': meta.get('char_removed', 0),
    }


def rechunk(document_id: int) -> dict:
    """Re-run chunker v2 over a previously indexed document.

    Reads the original source_file, wipes the existing chunks for this doc,
    and re-inserts them with fresh metadata. Useful after chunker upgrades.
    """
    from library.db import connect
    with connect() as conn:
        row = conn.execute(
            '''SELECT id, source_file, speaker FROM transcript_documents
               WHERE id = ?''',
            (document_id,),
        ).fetchone()
    if not row:
        return {'status': 'error', 'error': f'document_id {document_id} not found'}

    source_file = row[1]
    p = Path(source_file)
    if not p.exists():
        return {'status': 'error', 'error': f'Source file missing: {source_file}'}

    raw_text = _extract_text(p)
    if not raw_text:
        return {'status': 'error', 'error': 'Could not re-extract text'}

    from library._core.ingest.chunker import (
        chunk_transcript, clean_transcript_text,
    )
    cleaned, meta = clean_transcript_text(raw_text)
    chunks = chunk_transcript(cleaned)

    _replace_chunks(document_id, chunks, default_speaker=row[2] or '')
    _touch_document(document_id, cleaned, meta)
    _sync_fts(document_id)

    return {
        'status':       'rechunked',
        'document_id':  document_id,
        'chunks':       len(chunks),
        'tokens':       sum(c.token_count for c in chunks),
        'language':     meta['language'],
    }


# ── Text extraction ────────────────────────────────────────────────────────

def _extract_text(path: Path) -> str:
    """Extract plain text from a .txt or .pdf file."""
    suffix = path.suffix.lower()
    if suffix == '.txt':
        return path.read_text(encoding='utf-8', errors='replace').strip()
    if suffix == '.pdf':
        return _extract_pdf_text(path)
    if suffix in {'.srt', '.vtt'}:
        return path.read_text(encoding='utf-8', errors='replace').strip()
    log.warning('Unsupported transcript format: %s', path.suffix)
    return ''


def _extract_pdf_text(path: Path) -> str:
    """Extract text from PDF via pypdf (preferred) or pdftotext subprocess."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = [page.extract_text() or '' for page in reader.pages]
        text = '\n\n'.join(p.strip() for p in pages if p.strip())
        if text:
            return text
        log.warning('pypdf returned empty text for %s; trying pdftotext', path)
    except Exception as exc:
        log.debug('pypdf failed for %s (%s); trying pdftotext', path, exc)

    # Fallback to pdftotext if available
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
        tmp_path = tmp.name
    try:
        subprocess.check_call(
            ['pdftotext', str(path), tmp_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return Path(tmp_path).read_text(encoding='utf-8', errors='replace').strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        log.warning('pdftotext fallback also failed for %s: %s', path, exc)
        return ''
    finally:
        import os
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── DB writes ──────────────────────────────────────────────────────────────

def _upsert_document(*, path: Path, raw_text: str, cleaned_text: str,
                     meta: dict, speaker: str, event: str,
                     event_date: str) -> tuple[int, bool]:
    """Insert or update the transcript_documents row. Returns (id, is_new)."""
    from library.db import connect
    ts = now_iso()
    sha = hashlib.sha256(raw_text.encode('utf-8', 'replace')).hexdigest()
    summary = _summarize(cleaned_text)
    token_count = meta.get('char_count', 0) // 4  # rough heuristic, precise count is per-chunk sum

    with connect() as conn:
        cur = conn.cursor()
        row = cur.execute(
            'SELECT id, sha256 FROM transcript_documents WHERE source_file = ?',
            (str(path),),
        ).fetchone()
        if row:
            doc_id, existing_sha = row
            if existing_sha != sha:
                # Source changed on disk — refresh metadata.
                cur.execute(
                    '''UPDATE transcript_documents
                       SET sha256 = ?, language = ?, summary = ?,
                           char_count = ?, token_count = ?, added_at = ?
                       WHERE id = ?''',
                    (sha, meta['language'], summary,
                     meta['char_count'], token_count, ts, doc_id),
                )
                log.info('Document sha changed; metadata refreshed for id=%d', doc_id)
            return doc_id, False

        cur.execute(
            '''INSERT INTO transcript_documents
               (speaker, event, event_date, source_file, status, added_at,
                source_type, language, sha256, summary, char_count, token_count)
               VALUES (?, ?, ?, ?, 'indexed', ?, 'file', ?, ?, ?, ?, ?)''',
            (speaker, event, event_date, str(path), ts,
             meta['language'], sha, summary,
             meta['char_count'], token_count),
        )
        return cur.lastrowid, True


def _touch_document(document_id: int, cleaned_text: str, meta: dict) -> None:
    """Refresh summary + stats on a document after rechunk."""
    from library.db import connect
    with connect() as conn:
        conn.execute(
            '''UPDATE transcript_documents
               SET summary = ?, language = ?, char_count = ?
               WHERE id = ?''',
            (_summarize(cleaned_text), meta['language'],
             meta['char_count'], document_id),
        )


def _insert_chunks(doc_id: int, chunks: list, default_speaker: str) -> None:
    """Insert a fresh batch of chunks for a document (caller ensures empty).

    v0.14.6 — T1: for each chunk, attempt to resolve the detected
    surface speaker to a canonical ``speaker_profiles.canonical_name``
    and store it in the new ``speaker_canonical`` column. NULL when
    no profile matches — callers fall back to the raw ``speaker``.
    """
    from library.db import connect
    from library._core.analysis.speaker_canonicalize import (
        _load_profiles, canonicalize,
    )
    from library._core.ingest.section_tagger import tag_sections
    # v0.14.7 — T2: rule-based section labels (intro / prepared / qa /
    # closing) so downstream analysis can slice "Q&A answers only".
    section_labels = tag_sections(chunks)
    with connect() as conn:
        cur = conn.cursor()
        # Clear existing chunks for this doc — we treat each register()
        # call as authoritative for the source file's content.
        cur.execute('DELETE FROM transcript_chunks WHERE document_id = ?', (doc_id,))
        profiles = _load_profiles(conn)
        for c, section in zip(chunks, section_labels):
            surface = c.speaker or default_speaker
            canonical = canonicalize(surface, profiles=profiles) if surface else None
            cur.execute(
                '''INSERT INTO transcript_chunks
                   (document_id, chunk_index, text, speaker, speaker_canonical,
                    section, char_start, char_end, token_count, timestamp_start,
                    timestamp_end, speaker_turn_id, text_sha1)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (doc_id, c.chunk_index, c.text,
                 surface, canonical, section,
                 c.char_start, c.char_end, c.token_count,
                 c.timestamp_start, c.timestamp_end,
                 c.speaker_turn_id, c.text_sha1),
            )


def _replace_chunks(doc_id: int, chunks: list, default_speaker: str) -> None:
    """Alias for clarity when used in rechunk path."""
    _insert_chunks(doc_id, chunks, default_speaker)


def _chunk_count(doc_id: int) -> int:
    from library.db import connect
    with connect() as conn:
        row = conn.execute(
            'SELECT COUNT(*) FROM transcript_chunks WHERE document_id = ?',
            (doc_id,),
        ).fetchone()
    return row[0] if row else 0


def _sync_fts(doc_id: int) -> None:
    """Incremental FTS refresh for one document."""
    from library.db import connect
    from library._core.kb.fts_sync import sync_document
    try:
        with connect() as conn:
            sync_document(conn, doc_id)
    except Exception as exc:
        log.warning('FTS sync failed for doc=%d: %s', doc_id, exc)


def _summarize(text: str, max_chars: int = 400) -> str:
    """Cheap non-LLM summary: first N chars of cleaned text, whitespace-joined."""
    if not text:
        return ''
    return ' '.join(text.split())[:max_chars]
