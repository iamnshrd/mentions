from pathlib import Path

from agents.mentions.ingest import auto as ingest_auto_module


def test_ingest_auto_dry_run_with_txt(tmp_path, monkeypatch):
    incoming = tmp_path / 'incoming'
    incoming.mkdir(parents=True)
    (incoming / 'powell.txt').write_text('Jerome Powell said the committee will remain data dependent.')

    monkeypatch.setattr(ingest_auto_module, 'INCOMING', incoming)
    monkeypatch.setattr(ingest_auto_module, 'PROCESSING', tmp_path / 'processing')
    monkeypatch.setattr(ingest_auto_module, 'PROCESSED', tmp_path / 'processed')
    monkeypatch.setattr(ingest_auto_module, 'FAILED', tmp_path / 'failed')
    monkeypatch.setattr(ingest_auto_module, 'INGEST_JOBS', tmp_path / 'ingest_jobs.jsonl')

    result = ingest_auto_module.ingest(dry_run=True)
    assert result['processed'][0]['file'] == 'powell.txt'
    assert result['dry_run'] is True


def test_transcript_search_empty_short_query():
    from agents.mentions.interfaces.capabilities.transcripts.api import search_transcripts

    assert search_transcripts('ab') == []
