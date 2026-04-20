from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class RetrievalHit:
    chunk_id: int
    document_id: int
    text: str
    speaker: str
    section: str
    event: str
    event_date: str
    token_count: int
    chunk_index: int = 0
    source_file: str = ''
    source_url: str = ''
    char_start: int | None = None
    char_end: int | None = None
    speaker_canonical: str = ''
    rank_bm25: int = 0
    rank_semantic: int = 0
    score_bm25: float = 0.0
    score_semantic: float | None = None
    score_final: float = 0.0
    score_reliability: float = 1.0
    score_recency: float = 1.0
    final_rank: int = 0

    def trace_dict(self) -> dict:
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'chunk_index': self.chunk_index,
            'source_file': self.source_file,
            'source_url': self.source_url,
            'speaker': self.speaker,
            'speaker_canonical': self.speaker_canonical,
            'section': self.section,
            'event': self.event,
            'event_date': self.event_date,
            'char_start': self.char_start,
            'char_end': self.char_end,
        }

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload['trace'] = self.trace_dict()
        return payload
