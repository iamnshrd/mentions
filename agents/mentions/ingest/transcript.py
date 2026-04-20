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

from agents.mentions.utils import get_threshold, now_iso

log = logging.getLogger('mentions')


# ── Public API ─────────────────────────────────────────────────────────────

def register(source_file: str, speaker: str = '', event: str = '',
             event_date: str = '') -> dict:
    """Register and index a transcript file.

    *source_file* can be a path relative to the Mentions transcript store or absolute.
    Returns a result dict with doc_id and chunk count.
    """
    from agents.mentions.config import TRANSCRIPTS
    p = Path(source_file)
    if not p.is_absolute():
        p = TRANSCRIPTS / source_file
    if not p.exists():
        return {'error': f'File not found: {p}', 'status': 'error'}

    raw_text = _extract_text(p)
    if not raw_text:
        return {'error': 'Could not extract text from file', 'status': 'error'}

    schema_error = _ensure_transcript_schema()
    if schema_error is not None:
        return schema_error

    from agents.mentions.ingest.chunker import (
        chunk_transcript, clean_transcript_text,
    )
    cleaned, meta = clean_transcript_text(raw_text)
    chunks = chunk_transcript(cleaned)

    doc_id, new_doc, content_changed = _upsert_document(
        path=p,
        raw_text=raw_text,
        cleaned_text=cleaned,
        meta=meta,
        speaker=speaker,
        event=event,
        event_date=event_date,
    )
    if new_doc or content_changed or _chunk_count(doc_id) == 0:
        _insert_chunks(doc_id, chunks, default_speaker=speaker)
        _sync_fts(doc_id)
        if new_doc:
            action = 'indexed'
        elif content_changed:
            action = 'reindexed'
        else:
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
        'content_changed': content_changed,
        'trace':        _build_ingest_trace(doc_id),
    }


def rechunk(document_id: int) -> dict:
    """Re-run chunker v2 over a previously indexed document.

    Reads the original source_file, wipes the existing chunks for this doc,
    and re-inserts them with fresh metadata. Useful after chunker upgrades.
    """
    from agents.mentions.db import connect
    with connect() as conn:
        schema_missing = _transcript_schema_missing(conn)
        if schema_missing:
            return _schema_error(schema_missing)
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

    from agents.mentions.ingest.chunker import (
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
        'trace':        _build_ingest_trace(document_id),
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
                     event_date: str) -> tuple[int, bool, bool]:
    """Insert or update the transcript_documents row.

    Returns ``(id, is_new, content_changed)``.
    """
    from agents.mentions.db import connect
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
                return doc_id, False, True
            return doc_id, False, False

        cur.execute(
            '''INSERT INTO transcript_documents
               (speaker, event, event_date, source_file, status, added_at,
                source_type, language, sha256, summary, char_count, token_count)
               VALUES (?, ?, ?, ?, 'indexed', ?, 'file', ?, ?, ?, ?, ?)''',
            (speaker, event, event_date, str(path), ts,
             meta['language'], sha, summary,
             meta['char_count'], token_count),
        )
        return cur.lastrowid, True, False


def _touch_document(document_id: int, cleaned_text: str, meta: dict) -> None:
    """Refresh summary + stats on a document after rechunk."""
    from agents.mentions.db import connect
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
    from agents.mentions.db import connect
    from agents.mentions.services.speakers.canonicalize import (
        _load_profiles, canonicalize,
    )
    from agents.mentions.ingest.section_tagger import tag_sections
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
    from agents.mentions.db import connect
    with connect() as conn:
        row = conn.execute(
            'SELECT COUNT(*) FROM transcript_chunks WHERE document_id = ?',
            (doc_id,),
        ).fetchone()
    return row[0] if row else 0


def _sync_fts(doc_id: int) -> None:
    """Incremental FTS refresh for one document."""
    from agents.mentions.db import connect
    from agents.mentions.storage.knowledge.fts_sync import sync_document
    try:
        with connect() as conn:
            sync_document(conn, doc_id)
    except Exception as exc:
        log.warning('FTS sync failed for doc=%d: %s', doc_id, exc)


def _transcript_schema_missing(conn) -> str | None:
    from agents.mentions.db import assert_transcript_schema

    try:
        assert_transcript_schema(conn)
    except RuntimeError as exc:
        return str(exc)
    return None


def _ensure_transcript_schema() -> dict | None:
    from agents.mentions.db import connect

    with connect() as conn:
        missing = _transcript_schema_missing(conn)
    if missing is None:
        return None
    return _schema_error(missing)


def _schema_error(message: str) -> dict:
    return {
        'status': 'error',
        'error_code': 'schema_invalid',
        'error': message,
    }


def _build_ingest_trace(document_id: int) -> dict:
    from agents.mentions.db import connect

    with connect() as conn:
        doc_row = conn.execute(
            '''SELECT source_file, sha256, language, token_count, char_count
               FROM transcript_documents WHERE id = ?''',
            (document_id,),
        ).fetchone()
        chunk_rows = conn.execute(
            '''SELECT id, chunk_index, speaker, speaker_canonical, section,
                      char_start, char_end, text_sha1
               FROM transcript_chunks
               WHERE document_id = ?
               ORDER BY chunk_index''',
            (document_id,),
        ).fetchall()

    chunk_ids = [int(row[0]) for row in chunk_rows]
    chunk_preview = [
        {
            'chunk_id': int(row[0]),
            'chunk_index': int(row[1]),
            'speaker': row[2] or '',
            'speaker_canonical': row[3],
            'section': row[4] or '',
            'char_start': row[5],
            'char_end': row[6],
            'text_sha1': row[7],
        }
        for row in chunk_rows[:5]
    ]
    return {
        'document_id': document_id,
        'source_file': doc_row[0] if doc_row else '',
        'sha256': doc_row[1] if doc_row else '',
        'language': doc_row[2] if doc_row else '',
        'token_count': doc_row[3] if doc_row else 0,
        'char_count': doc_row[4] if doc_row else 0,
        'chunk_count': len(chunk_ids),
        'chunk_ids': chunk_ids,
        'chunk_preview': chunk_preview,
    }


def _chunk_text(text: str) -> list[str]:
    """Compatibility helper for manual transcript ingestion."""
    return [row['text'] for row in _chunk_text_structured(text)]


def _chunk_text_structured(text: str) -> list[dict]:
    """Compatibility helper that emits paragraph-window style chunks.

    Manual transcript intake stores richer runtime-segment metadata than the
    canonical DB ingest path needs. Keep this helper local so that path can
    continue to work while the runtime DB remains separate.
    """
    max_chars = int(get_threshold('transcript_chunk_max_chars', 2000))
    overlap = int(get_threshold('transcript_chunk_overlap_chars', 200))
    normalized = '\n'.join(line.rstrip() for line in (text or '').splitlines())
    paragraphs = [p.strip() for p in normalized.split('\n\n') if p.strip()]
    if not paragraphs:
        paragraphs = [normalized.strip()] if normalized.strip() else []

    chunks: list[dict] = []
    current_parts: list[str] = []
    current_section = ''
    current_kind = 'paragraph-window'

    def _detect_heading(line: str) -> str:
        stripped = (line or '').strip()
        if not stripped:
            return ''
        upper = stripped.upper().rstrip(':')
        if stripped.startswith('#'):
            return stripped.lstrip('#').strip()
        explicit = {
            'Q&A', 'Q AND A', 'QUESTIONS AND ANSWERS', 'QUESTION AND ANSWER',
            'PREPARED REMARKS', 'REMARKS', 'INTRODUCTION', 'OPENING REMARKS',
            'AUDIENCE QUESTION', 'AUDIENCE QUESTIONS',
        }
        if upper in explicit:
            return upper
        if stripped.endswith(':') and len(stripped.split()) <= 8:
            label = stripped.rstrip(':').strip()
            if label.isupper() or label.lower() in {'q&a', 'remarks', 'introduction'}:
                return label
        if stripped.upper() == stripped and len(stripped) >= 5:
            return stripped
        return ''

    def flush_current(source_boundary: str = 'paragraph') -> None:
        nonlocal current_parts
        value = ' '.join(part.strip() for part in current_parts if part.strip()).strip()
        if value and len(value) >= 80:
            chunks.append({
                'text': value,
                'section_title': current_section,
                'chunk_kind': current_kind,
                'source_boundary': source_boundary,
            })
        current_parts = []

    for para in paragraphs:
        para = ' '.join(para.split())
        if not para:
            continue

        heading = ''
        content = para
        if ':' in para:
            prefix, suffix = para.split(':', 1)
            detected = _detect_heading(prefix + ':')
            if detected and suffix.strip():
                heading = detected
                content = suffix.strip()
        if not heading:
            heading = _detect_heading(para)
            if heading:
                flush_current('heading')
                current_section = heading
                continue
        if heading:
            flush_current('heading')
            current_section = heading

        units = _split_sentences(content) if len(content) > max_chars else [content]
        for unit in units:
            unit = unit.strip()
            if not unit:
                continue
            candidate = ' '.join(current_parts + [unit]).strip()
            if len(candidate) <= max_chars:
                current_parts.append(unit)
                current_kind = 'sentence-window' if len(units) > 1 else 'paragraph-window'
                continue
            flush_current('sentence' if len(units) > 1 else 'paragraph')
            if len(unit) <= max_chars:
                current_parts = [unit]
                current_kind = 'sentence-window' if len(units) > 1 else 'paragraph-window'
                continue
            start = 0
            while start < len(unit):
                end = min(len(unit), start + max_chars)
                window = unit[start:end]
                if end < len(unit):
                    split = max(window.rfind('. '), window.rfind('; '), window.rfind(', '))
                    if split > max_chars * 0.45:
                        end = start + split + 1
                        window = unit[start:end]
                piece = window.strip()
                if len(piece) >= 80:
                    chunks.append({
                        'text': piece,
                        'section_title': current_section,
                        'chunk_kind': 'hard-window',
                        'source_boundary': 'hard-split',
                    })
                if end >= len(unit):
                    start = len(unit)
                else:
                    start = max(start + 1, end - overlap)
        flush_current('paragraph')

    deduped = []
    seen = set()
    for chunk in chunks:
        key = chunk['text'][:240]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return deduped


def _split_sentences(text: str) -> list[str]:
    text = ' '.join((text or '').split())
    if not text:
        return []
    parts = []
    current = []
    for token in text.split(' '):
        current.append(token)
        if token.endswith(('.', '?', '!')) and len(' '.join(current)) >= 80:
            parts.append(' '.join(current).strip())
            current = []
    if current:
        parts.append(' '.join(current).strip())
    return parts


def _summarize(text: str, max_chars: int = 400) -> str:
    """Cheap non-LLM summary: first N chars of cleaned text, whitespace-joined."""
    if not text:
        return ''
    return ' '.join(text.split())[:max_chars]
