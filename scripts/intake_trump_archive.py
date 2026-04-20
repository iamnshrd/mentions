from __future__ import annotations

import json
import re
from pathlib import Path

from agents.mentions.ingest.manual_transcript import ingest_manual_transcript

ARCHIVE_DIR = Path('/root/.openclaw/multi-agent/agents/mentions/repo/tmp_manual_transcripts/trump_archive/Trump')
SPEAKER = 'Donald Trump'


def parse_event_name(path: Path) -> str:
    name = path.stem
    name = re.sub(r'^Trump_', '', name)
    name = name.replace('___', ' ').replace('__', ' ')
    name = name.replace('_', ' ')
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'^President Donald J\.? Trump\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^President Trump\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^Trump\s+', '', name, flags=re.IGNORECASE)
    return name.strip(' -')


def infer_format_tags(event: str) -> list[str]:
    lower = event.lower()
    tags = []
    if 'press conference' in lower:
        tags.append('press-conference')
    elif 'roundtable' in lower:
        tags.append('roundtable')
    elif 'interview' in lower or 'show' in lower:
        tags.append('interview')
    elif 'remarks' in lower:
        tags.append('speech')
    elif 'announcement' in lower:
        tags.append('announcement')
    elif 'meeting' in lower:
        tags.append('meeting')
    return tags


def infer_topic_tags(event: str) -> list[str]:
    lower = event.lower()
    mapping = {
        'iran': 'iran',
        'economy': 'economy',
        'energy': 'energy',
        'trump accounts': 'trump-accounts',
        'oil and gas': 'energy',
        'coal': 'energy',
        'social security': 'social-security',
        'college sports': 'college-sports',
    }
    tags = []
    for needle, tag in mapping.items():
        if needle in lower and tag not in tags:
            tags.append(tag)
    return tags


def main() -> None:
    results = []
    files = sorted(ARCHIVE_DIR.glob('*.txt'))
    for path in files:
        event = parse_event_name(path)
        result = ingest_manual_transcript(
            source_file=str(path),
            speaker=SPEAKER,
            event=event,
            event_date='',
            format_tags=infer_format_tags(event),
            topic_tags=infer_topic_tags(event),
            event_tags=['user-archive'],
            mention_tags=['same-speaker-corpus'],
            quality_tags=['user-supplied-archive'],
            notes='Imported from user-provided Trump transcript archive.',
        )
        results.append({
            'file': path.name,
            'event': event,
            'status': result.get('status'),
            'chunks': result.get('chunks', 0),
            'transcript_id': result.get('transcript_id'),
        })
    print(json.dumps({
        'files': len(files),
        'indexed': sum(1 for r in results if r.get('status') == 'indexed'),
        'results': results,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
