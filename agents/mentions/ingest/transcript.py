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

from agents.mentions.utils import now_iso, get_threshold, slugify

log = logging.getLogger('mentions')


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
            except OSError as exc:
                log.debug('Failed to remove temp transcript file %s: %s', tmp_path, exc)
    log.warning('Unsupported transcript format: %s', path.suffix)
    return ''


def _chunk_text(text: str) -> list[str]:
    return [row['text'] for row in _chunk_text_structured(text)]


def _chunk_text_structured(text: str) -> list[dict]:
    """Split text into cleaner structured transcript chunks.

    Returns rows like:
    - text
    - section_title
    - chunk_kind
    - source_boundary
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
            'AUDIENCE QUESTION', 'AUDIENCE QUESTIONS'
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

    def flush_current(source_boundary: str = 'paragraph'):
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


def _insert_document(path: Path, speaker: str, event: str,
                     event_date: str) -> int:
    """Insert or return existing transcript_documents row."""
    from agents.mentions.db import connect
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
    from agents.mentions.db import connect
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
    from agents.mentions.db import connect
    with connect() as conn:
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO transcript_chunks_fts(transcript_chunks_fts) VALUES("rebuild")')
        except Exception as exc:
            log.debug('FTS rebuild note: %s', exc)
