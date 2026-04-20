"""Tests for section_tagger (v0.14.7 — T2)."""
from __future__ import annotations

from dataclasses import dataclass

from agents.mentions.ingest.section_tagger import (
    _looks_like_closing, _looks_like_qa, tag_sections,
)


@dataclass
class _C:
    text: str


def _chunks(*texts: str) -> list[_C]:
    return [_C(text=t) for t in texts]


# ── Edge cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty(self):
        assert tag_sections([]) == []

    def test_single_chunk_prepared(self):
        assert tag_sections(_chunks('Good morning, welcome.')) == ['prepared']

    def test_single_chunk_even_with_qa_trigger(self):
        # Single-chunk special case ignores content.
        assert tag_sections(_chunks('Next question please.')) == ['prepared']


# ── Intro default ─────────────────────────────────────────────────────────

class TestIntro:
    def test_first_chunk_is_intro_when_no_qa(self):
        labels = tag_sections(_chunks(
            'Opening remarks.',
            'Economic outlook discussion.',
            'More prepared content.',
        ))
        assert labels[0] == 'intro'
        assert labels[1] == 'prepared'
        assert labels[2] == 'prepared'

    def test_first_chunk_qa_overrides_intro(self):
        # Rare: briefing opens cold with a question.
        labels = tag_sections(_chunks(
            'Q: What about rates?',
            'Follow-up discussion.',
        ))
        assert labels[0] == 'qa'
        assert labels[1] == 'qa'


# ── Q&A latch ─────────────────────────────────────────────────────────────

class TestQALatch:
    def test_qa_latches_forward(self):
        labels = tag_sections(_chunks(
            'Opening.',
            'Prepared remarks body.',
            'Next question from the reporter.',
            'Answer to question.',
            'Another answer.',
        ))
        assert labels == ['intro', 'prepared', 'qa', 'qa', 'qa']

    def test_mr_chairman_triggers_qa(self):
        labels = tag_sections(_chunks(
            'Intro.',
            'Prepared.',
            'Mr. Chairman, could you clarify inflation?',
            'Answer.',
        ))
        assert labels[2] == 'qa'
        assert labels[3] == 'qa'

    def test_reporter_colon_triggers_qa(self):
        labels = tag_sections(_chunks(
            'Intro.',
            'Reporter: what is the outlook?',
        ))
        assert labels[1] == 'qa'

    def test_thanks_for_taking_my_question_triggers(self):
        labels = tag_sections(_chunks(
            'Intro remarks.',
            'Prepared body.',
            'Thanks for taking my question, chair.',
        ))
        assert labels[2] == 'qa'

    def test_q_colon_line_start_triggers(self):
        labels = tag_sections(_chunks(
            'Intro.',
            'Prepared.',
            'Q: How long will rates stay high?',
        ))
        assert labels[2] == 'qa'


# ── Closing ───────────────────────────────────────────────────────────────

class TestClosing:
    def test_closing_phrase_on_last_prepared(self):
        labels = tag_sections(_chunks(
            'Opening.',
            'Body.',
            'Thank you all very much.',
        ))
        assert labels[-1] == 'closing'

    def test_that_concludes_marks_closing(self):
        labels = tag_sections(_chunks(
            'Opening.',
            'Body.',
            'That concludes my prepared remarks.',
        ))
        assert labels[-1] == 'closing'

    def test_qa_tail_not_overwritten_by_closing(self):
        # Last chunk is inside Q&A latch — must stay 'qa' even if it
        # contains a "thank you" phrase.
        labels = tag_sections(_chunks(
            'Opening.',
            'Prepared.',
            'Next question from the back.',
            'Thank you very much, that is all.',
        ))
        assert labels[-1] == 'qa'

    def test_no_closing_phrase_stays_prepared(self):
        labels = tag_sections(_chunks(
            'Opening.',
            'Mid body.',
            'Plain ending without closing phrase.',
        ))
        assert labels[-1] == 'prepared'


# ── Predicate helpers ─────────────────────────────────────────────────────

class TestPredicates:
    def test_looks_like_qa_positive(self):
        assert _looks_like_qa('Next question please.')
        assert _looks_like_qa('Mr. Chairman, can you elaborate?')
        assert _looks_like_qa('Reporter: thank you.')

    def test_looks_like_qa_negative(self):
        assert not _looks_like_qa('Inflation has moderated.')
        assert not _looks_like_qa('')

    def test_looks_like_closing_positive(self):
        assert _looks_like_closing('Thank you all very much.')
        assert _looks_like_closing("I'll stop there.")
        assert _looks_like_closing('That concludes our briefing.')

    def test_looks_like_closing_negative(self):
        assert not _looks_like_closing('Rates remain elevated.')
        assert not _looks_like_closing('')
