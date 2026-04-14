"""Automated transcript ingestion from incoming/ staging directory.

Pipeline: incoming/ → processing/ → processed/ | failed/
Each file gets a job record in ingest_jobs.jsonl.
Mirrors Jordan's library/_core/ingest/auto.py for transcripts.
"""
from __future__ import annotations

import json
import logging
import shutil

from library.config import INCOMING, ROOT
from library.utils import slugify, save_json, now_iso
from library._core.ingest.transcript import register as register_transcript

log = logging.getLogger('mentions')

PROCESSING = INCOMING.parent / 'processing'
PROCESSED = INCOMING.parent / 'processed'
FAILED = INCOMING.parent / 'failed'
INGEST_JOBS = INCOMING.parent / 'ingest_jobs.jsonl'

SUPPORTED_SUFFIXES = {'.txt', '.pdf'}


def _ensure_dirs():
    for d in (INCOMING, PROCESSING, PROCESSED, FAILED):
        d.mkdir(parents=True, exist_ok=True)


def _append_job(entry: dict):
    with open(INGEST_JOBS, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def _load_processed_set() -> set[str]:
    names: set[str] = set()
    if not INGEST_JOBS.exists():
        return names
    for line in INGEST_JOBS.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get('status') == 'processed':
            names.add(rec.get('file', ''))
    return names


def ingest(dry_run: bool = False) -> dict:
    """Process all transcripts (.txt, .pdf) in incoming/.

    With *dry_run=True* files are scanned but not moved or processed.
    """
    _ensure_dirs()
    already_done = _load_processed_set()
    processed, skipped, errors = [], [], []

    for path in sorted(INCOMING.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            skipped.append({'file': path.name, 'reason': 'unsupported_suffix'})
            continue
        if path.name in already_done:
            skipped.append({'file': path.name, 'reason': 'already_ingested'})
            continue

        if dry_run:
            processed.append({'file': path.name, 'dry_run': True})
            continue

        staging_path = PROCESSING / path.name
        try:
            shutil.move(str(path), str(staging_path))
        except OSError as exc:
            errors.append({'file': path.name, 'error': f'move_to_processing: {exc}'})
            _append_job({'file': path.name, 'status': 'error',
                         'error': str(exc), 'timestamp': now_iso()})
            continue

        target_name = slugify(staging_path.stem) + staging_path.suffix.lower()
        from library.config import TRANSCRIPTS
        TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
        target = TRANSCRIPTS / target_name

        if target.exists():
            import hashlib as _hl
            h = _hl.md5(staging_path.read_bytes()).hexdigest()[:8]
            alt = TRANSCRIPTS / f'{slugify(staging_path.stem)}_{h}{staging_path.suffix.lower()}'
            if alt.exists():
                skipped.append({'file': path.name, 'reason': 'already_exists'})
                shutil.move(str(staging_path), str(PROCESSED / path.name))
                _append_job({'file': path.name, 'status': 'skipped_duplicate',
                             'timestamp': now_iso()})
                continue
            target = alt

        try:
            shutil.move(str(staging_path), str(target))
            result = register_transcript(str(target))

            shutil.copy2(str(target), str(PROCESSED / path.name))
            _append_job({
                'file': path.name,
                'status': 'processed',
                'target': str(target.relative_to(ROOT)),
                'chunks': result.get('chunks', 0),
                'timestamp': now_iso(),
            })
            processed.append({
                'file': path.name,
                'target': str(target.relative_to(ROOT)),
                'chunks': result.get('chunks', 0),
            })

        except Exception as exc:
            log.exception('Ingest failed for %s', path.name)
            fail_dest = FAILED / path.name
            for src in (target, staging_path):
                if src.exists():
                    try:
                        shutil.move(str(src), str(fail_dest))
                    except OSError:
                        pass
                    break
            errors.append({'file': path.name, 'error': str(exc)})
            _append_job({'file': path.name, 'status': 'error',
                         'error': str(exc), 'timestamp': now_iso()})

    return {
        'processed': processed,
        'skipped': skipped,
        'errors': errors,
        'dry_run': dry_run,
    }
