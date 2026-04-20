#!/usr/bin/env python3
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

WORKDIR = Path('/root/.openclaw/workspace')
TRANSCRIPTS_DIR = WORKDIR / 'transcripts'
DB_PATH = WORKDIR / 'pmt_trader_knowledge.db'
CHANNEL = 'PredictionMarketTrader'
CHANNEL_URL = 'https://www.youtube.com/@PredictionMarketTrader/streams'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def parse_filename(path: Path):
    stem = path.stem
    if '__' in stem:
        video_id, title = stem.split('__', 1)
    else:
        video_id, title = stem, stem
    return video_id, title


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_text(text: str, target_chars=1800, overlap_chars=250):
    text = text.strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n+', text) if p.strip()]
    chunks = []
    current = ''
    start_char = 0
    for para in paragraphs:
        candidate = para if not current else current + '\n\n' + para
        if len(candidate) <= target_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            tail = current[-overlap_chars:] if overlap_chars > 0 else ''
            current = (tail + '\n\n' + para).strip() if tail else para
        else:
            # hard split oversized paragraph
            s = para
            while len(s) > target_chars:
                chunks.append(s[:target_chars].strip())
                s = s[target_chars - overlap_chars:].strip() if overlap_chars < target_chars else s[target_chars:].strip()
            current = s
    if current:
        chunks.append(current)

    results = []
    search_from = 0
    for idx, chunk in enumerate(chunks):
        pos = text.find(chunk[:120].strip(), search_from)
        if pos == -1:
            pos = search_from
        end = min(len(text), pos + len(chunk))
        results.append({
            'chunk_index': idx,
            'text': chunk,
            'char_start': pos,
            'char_end': end,
            'token_estimate': estimate_tokens(chunk),
        })
        search_from = max(pos, end - overlap_chars)
    return results


def init_db(conn):
    conn.executescript('''
    PRAGMA journal_mode=WAL;
    PRAGMA foreign_keys=ON;

    CREATE TABLE IF NOT EXISTS videos (
      video_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      source_channel TEXT,
      source_url TEXT NOT NULL,
      channel_url TEXT,
      local_txt_path TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'ok',
      text_length INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS transcripts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      video_id TEXT NOT NULL UNIQUE,
      clean_text TEXT NOT NULL,
      language TEXT NOT NULL DEFAULT 'en',
      source_type TEXT NOT NULL DEFAULT 'youtube_auto',
      ingested_at TEXT NOT NULL,
      FOREIGN KEY(video_id) REFERENCES videos(video_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS transcript_chunks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      video_id TEXT NOT NULL,
      transcript_id INTEGER NOT NULL,
      chunk_index INTEGER NOT NULL,
      text TEXT NOT NULL,
      char_start INTEGER NOT NULL,
      char_end INTEGER NOT NULL,
      token_estimate INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(video_id, chunk_index),
      FOREIGN KEY(video_id) REFERENCES videos(video_id) ON DELETE CASCADE,
      FOREIGN KEY(transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS transcript_chunks_fts USING fts5(
      video_id,
      title,
      text,
      content=''
    );

    CREATE INDEX IF NOT EXISTS idx_videos_title ON videos(title);
    CREATE INDEX IF NOT EXISTS idx_transcript_chunks_video_id ON transcript_chunks(video_id);
    CREATE INDEX IF NOT EXISTS idx_transcript_chunks_transcript_id ON transcript_chunks(transcript_id);
    ''')
    conn.commit()


def upsert_video_and_transcript(conn, path: Path):
    video_id, title = parse_filename(path)
    text = path.read_text(encoding='utf-8', errors='ignore').strip()
    now = utc_now()
    source_url = f'https://www.youtube.com/watch?v={video_id}'
    conn.execute('''
      INSERT INTO videos (video_id, title, source_channel, source_url, channel_url, local_txt_path, status, text_length, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, 'ok', ?, ?, ?)
      ON CONFLICT(video_id) DO UPDATE SET
        title=excluded.title,
        source_channel=excluded.source_channel,
        source_url=excluded.source_url,
        channel_url=excluded.channel_url,
        local_txt_path=excluded.local_txt_path,
        status='ok',
        text_length=excluded.text_length,
        updated_at=excluded.updated_at
    ''', (video_id, title, CHANNEL, source_url, CHANNEL_URL, str(path), len(text), now, now))

    conn.execute('''
      INSERT INTO transcripts (video_id, clean_text, language, source_type, ingested_at)
      VALUES (?, ?, 'en', 'youtube_auto', ?)
      ON CONFLICT(video_id) DO UPDATE SET
        clean_text=excluded.clean_text,
        language=excluded.language,
        source_type=excluded.source_type,
        ingested_at=excluded.ingested_at
    ''', (video_id, text, now))

    transcript_id = conn.execute('SELECT id FROM transcripts WHERE video_id=?', (video_id,)).fetchone()[0]

    conn.execute('DELETE FROM transcript_chunks WHERE video_id=?', (video_id,))
    conn.execute('DELETE FROM transcript_chunks_fts WHERE video_id=?', (video_id,))

    chunks = chunk_text(text)
    for chunk in chunks:
        cur = conn.execute('''
          INSERT INTO transcript_chunks (video_id, transcript_id, chunk_index, text, char_start, char_end, token_estimate, created_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (video_id, transcript_id, chunk['chunk_index'], chunk['text'], chunk['char_start'], chunk['char_end'], chunk['token_estimate'], now))
        chunk_id = cur.lastrowid
        conn.execute('''
          INSERT INTO transcript_chunks_fts (rowid, video_id, title, text)
          VALUES (?, ?, ?, ?)
        ''', (chunk_id, video_id, title, chunk['text']))
    return video_id, title, len(text), len(chunks)


def main():
    txt_files = sorted(TRANSCRIPTS_DIR.glob('*.txt'))
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    imported = []
    for path in txt_files:
        imported.append(upsert_video_and_transcript(conn, path))
    conn.commit()
    total_videos = conn.execute('SELECT COUNT(*) FROM videos').fetchone()[0]
    total_transcripts = conn.execute('SELECT COUNT(*) FROM transcripts').fetchone()[0]
    total_chunks = conn.execute('SELECT COUNT(*) FROM transcript_chunks').fetchone()[0]
    print(f'DB: {DB_PATH}')
    print(f'Imported files: {len(imported)}')
    print(f'Videos: {total_videos}')
    print(f'Transcripts: {total_transcripts}')
    print(f'Chunks: {total_chunks}')
    print('Sample imported:')
    for row in imported[:10]:
        print(f'- {row[0]} :: {row[1]} :: chars={row[2]} :: chunks={row[3]}')

if __name__ == '__main__':
    main()
