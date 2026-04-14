"""Register and index a single speaker transcript.

Pipeline:
1. Read source file (.txt or .pdf)
2. Chunk text with overlap
3. Insert transcript_documents + transcript_chunks into DB
4. Rebuild FTS index
"""
from __future__ import annotations

import logging
from pathlib import Path

from library.utils import now_iso, get_threshold, slugify

log = logging.getLogger('mentions')


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

    text = _extract_text(p)
    if not text:
        return {'error': 'Could not extract text from file', 'status': 'error'}

    doc_id = _insert_document(p, speaker, event, event_date)
    chunks = _chunk_text(text)
    _insert_chunks(doc_id, chunks, speaker)
    _rebuild_fts()

    log.info('Transcript registered: %s (%d chunks)', p.name, len(chunks))
    return {
        'status': 'indexed',
        'document_id': doc_id,
        'file': str(p),
        'speaker': speaker,
        'event': event,
        'chunks': len(chunks),
    }


def _extract_text(path: Path) -> str:
    """Extract plain text from a .txt or .pdf file."""
    if path.suffix.lower() == '.txt':
        return path.read_text(encoding='utf-8', errors='replace').strip()
    if path.suffix.lower() == '.pdf':
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            subprocess.check_call(['pdftotext', str(path), tmp_path])
            return Path(tmp_path).read_text(encoding='utf-8', errors='replace').strip()
        except Exception as exc:
            log.warning('pdftotext failed for %s: %s', path, exc)
            return ''
        finally:
            import os
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    log.warning('Unsupported transcript format: %s', path.suffix)
    return ''


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    max_chars = get_threshold('transcript_chunk_max_chars', 2000)
    overlap = get_threshold('transcript_chunk_overlap_chars', 200)
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind('. ')
            if last_period > max_chars * 0.5:
                end = start + last_period + 1
                chunk = text[start:end]
        chunks.append(chunk.strip())
        start = end - overlap
    return [c for c in chunks if len(c) >= 50]


def _insert_document(path: Path, speaker: str, event: str,
                     event_date: str) -> int:
    """Insert or return existing transcript_documents row."""
    from library.db import connect
    ts = now_iso()
    with connect() as conn:
        cur = conn.cursor()
        # Check for existing doc with same file
        row = cur.execute(
            'SELECT id FROM transcript_documents WHERE source_file = ?',
            (str(path),),
        ).fetchone()
        if row:
            return row[0]
        cur.execute(
            '''INSERT INTO transcript_documents
               (speaker, event, event_date, source_file, status, added_at)
               VALUES (?, ?, ?, ?, 'indexed', ?)''',
            (speaker, event, event_date, str(path), ts),
        )
        return cur.lastrowid


def _insert_chunks(doc_id: int, chunks: list[str], speaker: str) -> None:
    """Insert transcript_chunks rows for a document."""
    from library.db import connect
    with connect() as conn:
        cur = conn.cursor()
        # Clear existing chunks for this doc
        cur.execute(
            'DELETE FROM transcript_chunks WHERE document_id = ?', (doc_id,)
        )
        for i, chunk in enumerate(chunks):
            cur.execute(
                '''INSERT INTO transcript_chunks
                   (document_id, chunk_index, text, speaker, section)
                   VALUES (?, ?, ?, ?, ?)''',
                (doc_id, i, chunk, speaker, ''),
            )


def _rebuild_fts() -> None:
    """Rebuild the FTS5 index from transcript_chunks."""
    from library.db import connect
    with connect() as conn:
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO transcript_chunks_fts(transcript_chunks_fts) VALUES("rebuild")')
        except Exception as exc:
            log.debug('FTS rebuild note: %s', exc)
