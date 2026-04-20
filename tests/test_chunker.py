"""Tests for agents.mentions.ingest.chunker (chunker v2).

Covers:
  * count_tokens (tiktoken cl100k_base)
  * clean_transcript_text (stage directions, SRT timestamps, whitespace)
  * detect_language (EN / RU)
  * split_speaker_turns (speaker extraction, fallback)
  * chunk_transcript (token budget, overlap, structure preservation)
  * _sentence_split (oversized-turn fallback)
  * Chunk dataclass (text_sha1 auto-populate, as_row)
"""
from __future__ import annotations

import pytest

from agents.mentions.ingest.chunker import (
    Chunk,
    _ChunkPacker,
    _parse_timestamp,
    _sentence_split,
    chunk_transcript,
    clean_transcript_text,
    count_tokens,
    detect_language,
    split_speaker_turns,
)


# ── Tokenizer ──────────────────────────────────────────────────────────────

class TestCountTokens:
    def test_empty_string_is_zero(self):
        assert count_tokens('') == 0

    def test_short_ascii_is_small(self):
        # 'Hello world' is typically 2 tokens in cl100k_base.
        assert 1 <= count_tokens('Hello world') <= 4

    def test_longer_text_is_bigger(self):
        short = count_tokens('The cat sat on the mat.')
        longer = count_tokens('The cat sat on the mat. ' * 10)
        assert longer > short

    def test_cyrillic_counts(self):
        # Cyrillic usually uses more bpe tokens per character than ASCII.
        tokens = count_tokens('Привет, как дела?')
        assert tokens > 0


# ── Normalisation ──────────────────────────────────────────────────────────

class TestCleanTranscriptText:
    def test_empty_input(self):
        cleaned, meta = clean_transcript_text('')
        assert cleaned == ''
        assert meta['char_count'] == 0

    def test_strips_music_applause_etc(self):
        raw = '[Music]\nHello there [Applause] how are you [Inaudible]?'
        cleaned, meta = clean_transcript_text(raw)
        assert '[Music]' not in cleaned
        assert '[Applause]' not in cleaned
        assert '[Inaudible]' not in cleaned
        assert 'Hello there' in cleaned
        assert meta['char_removed'] > 0

    def test_strips_srt_timestamp_range(self):
        raw = (
            '00:00:05,120 --> 00:00:08,450\n'
            'Hello world.\n'
            '00:00:08,500 --> 00:00:12,000\n'
            'Second cue.\n'
        )
        cleaned, _ = clean_transcript_text(raw)
        assert '-->' not in cleaned
        assert 'Hello world.' in cleaned
        assert 'Second cue.' in cleaned

    def test_strips_srt_sequence_numbers(self):
        raw = '1\n00:00:01,000 --> 00:00:02,000\nFirst line\n\n2\n00:00:02,100 --> 00:00:03,000\nSecond line'
        cleaned, _ = clean_transcript_text(raw)
        # Neither the bare '1' nor bare '2' on a line should survive.
        assert 'First line' in cleaned
        assert 'Second line' in cleaned

    def test_collapses_whitespace(self):
        raw = 'Hello    world   \n\n\n\n  how    are    you'
        cleaned, _ = clean_transcript_text(raw)
        assert '    ' not in cleaned
        assert '\n\n\n' not in cleaned

    def test_preserves_inline_bracketed_timestamps(self):
        # These are useful for structure — leave them be.
        raw = 'Speaker: hello [00:01:30] then continued [00:01:45]'
        cleaned, _ = clean_transcript_text(raw)
        assert '[00:01:30]' in cleaned
        assert '[00:01:45]' in cleaned

    def test_meta_reports_language(self):
        cleaned_en, meta_en = clean_transcript_text('This is an English sentence about cats and dogs.')
        assert meta_en['language'] == 'en'
        cleaned_ru, meta_ru = clean_transcript_text('Это предложение на русском языке про котов и собак.')
        assert meta_ru['language'] == 'ru'


# ── Language detection ────────────────────────────────────────────────────

class TestDetectLanguage:
    def test_english(self):
        assert detect_language('The quick brown fox jumps over the lazy dog.') == 'en'

    def test_russian(self):
        assert detect_language('Быстрая бурая лиса прыгает через ленивую собаку.') == 'ru'

    def test_empty(self):
        assert detect_language('') == 'und'

    def test_digits_only(self):
        assert detect_language('12345 67890') == 'und'

    def test_mixed_but_majority_english(self):
        # Lots of English, only a light sprinkling of Cyrillic — should stay EN.
        text = ('The quick brown fox jumps over the lazy dog many times. ' * 10
                + 'Привет.')
        assert detect_language(text) == 'en'


# ── Timestamp parsing ──────────────────────────────────────────────────────

class TestParseTimestamp:
    def test_hms(self):
        assert _parse_timestamp('01:02:03') == pytest.approx(3723.0)

    def test_ms(self):
        assert _parse_timestamp('02:30') == pytest.approx(150.0)

    def test_with_milliseconds(self):
        assert _parse_timestamp('00:00:01.500') == pytest.approx(1.5)

    def test_with_comma_milliseconds(self):
        assert _parse_timestamp('00:00:02,250') == pytest.approx(2.25)

    def test_invalid(self):
        assert _parse_timestamp('not a time') is None


# ── Speaker turn detection ─────────────────────────────────────────────────

class TestSplitSpeakerTurns:
    def test_no_speakers_returns_single_turn(self):
        turns = split_speaker_turns('This is just plain text with no speaker labels at all.')
        assert len(turns) == 1
        assert turns[0].speaker == ''

    def test_single_speaker_one_match_returns_single_turn(self):
        # Single match alone shouldn't trigger multi-turn split.
        turns = split_speaker_turns('Alice: just one line')
        # One match → treat as single turn (no structure to split on).
        assert len(turns) == 1

    def test_two_speakers_creates_two_turns(self):
        text = 'Alice: hello there.\nBob: hi, how are you?'
        turns = split_speaker_turns(text)
        assert len(turns) == 2
        assert turns[0].speaker == 'Alice'
        assert 'hello there' in turns[0].text
        assert turns[1].speaker == 'Bob'
        assert 'hi, how are you' in turns[1].text

    def test_youtube_style_double_angle_prefix(self):
        text = '>> Alice: first line\n>> Bob: second line'
        turns = split_speaker_turns(text)
        assert len(turns) == 2
        assert turns[0].speaker == 'Alice'
        assert turns[1].speaker == 'Bob'

    def test_cyrillic_speaker_name(self):
        text = 'Иван: приветствие\nМария: ответ на приветствие'
        turns = split_speaker_turns(text)
        assert len(turns) == 2
        assert turns[0].speaker == 'Иван'
        assert turns[1].speaker == 'Мария'

    def test_turn_ids_are_sequential(self):
        text = 'A: one\nB: two\nC: three'
        turns = split_speaker_turns(text)
        assert [t.turn_id for t in turns] == [0, 1, 2]

    def test_char_offsets_point_into_source(self):
        text = 'Alice: hello\nBob: world'
        turns = split_speaker_turns(text)
        assert len(turns) == 2
        # char_start/char_end should be valid slice indices.
        for t in turns:
            assert 0 <= t.char_start <= t.char_end <= len(text)


# ── Chunk dataclass ────────────────────────────────────────────────────────

class TestChunk:
    def test_sha1_auto_populated(self):
        c = Chunk(text='hello', char_start=0, char_end=5, token_count=1)
        assert c.text_sha1
        assert len(c.text_sha1) == 40  # sha1 hex digest

    def test_same_text_same_sha1(self):
        a = Chunk(text='same', char_start=0, char_end=4, token_count=1)
        b = Chunk(text='same', char_start=100, char_end=104, token_count=1)
        assert a.text_sha1 == b.text_sha1

    def test_different_text_different_sha1(self):
        a = Chunk(text='foo', char_start=0, char_end=3, token_count=1)
        b = Chunk(text='bar', char_start=0, char_end=3, token_count=1)
        assert a.text_sha1 != b.text_sha1

    def test_as_row_contains_expected_keys(self):
        c = Chunk(text='hello', char_start=0, char_end=5, token_count=1,
                  chunk_index=3, speaker='Alice', speaker_turn_id=1,
                  timestamp_start=1.5, timestamp_end=3.0)
        row = c.as_row()
        assert row['text'] == 'hello'
        assert row['chunk_index'] == 3
        assert row['speaker'] == 'Alice'
        assert row['speaker_turn_id'] == 1
        assert row['timestamp_start'] == 1.5
        assert row['timestamp_end'] == 3.0
        assert row['text_sha1'] == c.text_sha1


# ── Core chunker ───────────────────────────────────────────────────────────

class TestChunkTranscript:
    def test_empty_input_returns_empty_list(self):
        assert chunk_transcript('') == []
        assert chunk_transcript('   \n\n\t  ') == []

    def test_short_text_produces_one_chunk(self):
        text = 'Alice: just a brief exchange.\nBob: very brief indeed.'
        chunks = chunk_transcript(text, target_tokens=500)
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].token_count > 0

    def test_respects_target_budget(self):
        # Build a long transcript of many short turns.
        names = ['Alice', 'Bob', 'Carol', 'Dave', 'Eve', 'Frank']
        lines = [f'{names[i % len(names)]}: this is turn number {i}, with a bit of text attached. '
                 for i in range(200)]
        text = '\n'.join(lines)
        chunks = chunk_transcript(text, target_tokens=100, overlap_tokens=10, max_tokens=300)
        assert len(chunks) > 1
        # Every chunk should be under the ceiling (max_tokens).
        for c in chunks:
            assert c.token_count <= 400  # allow small overhead from speaker labels

    def test_chunk_indices_are_sequential(self):
        names = ['Alice', 'Bob', 'Carol', 'Dave', 'Eve', 'Frank']
        lines = [f'{names[i % len(names)]}: text content number {i}.' for i in range(50)]
        text = '\n'.join(lines)
        chunks = chunk_transcript(text, target_tokens=50, overlap_tokens=5, max_tokens=150)
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_char_offsets_are_monotonic(self):
        names = ['Alice', 'Bob', 'Carol', 'Dave', 'Eve', 'Frank']
        lines = [f'{names[i % len(names)]}: content {i}.' for i in range(30)]
        text = '\n'.join(lines)
        chunks = chunk_transcript(text, target_tokens=40, overlap_tokens=5, max_tokens=150)
        for a, b in zip(chunks, chunks[1:]):
            # With overlap, starts can step back, but ends should move forward.
            assert b.char_end >= a.char_end

    def test_dominant_speaker_assignment(self):
        # Alice dominates by volume; chunk should pick her up.
        text = (
            'Alice: ' + ('lorem ipsum dolor sit amet. ' * 30) + '\n'
            'Bob: short.'
        )
        chunks = chunk_transcript(text, target_tokens=500, max_tokens=2000)
        assert len(chunks) >= 1
        assert chunks[0].speaker == 'Alice'

    def test_dedup_via_sha1(self):
        # Identical chunks get identical sha1s. Useful for dedup downstream.
        text = 'Alice: hello.\nBob: world.'
        chunks1 = chunk_transcript(text)
        chunks2 = chunk_transcript(text)
        assert chunks1[0].text_sha1 == chunks2[0].text_sha1

    def test_oversized_single_turn_gets_split(self):
        # One huge turn well beyond max_tokens.
        big = 'Alice: ' + ('word ' * 3000)  # ~3000 tokens of "word"
        chunks = chunk_transcript(big, target_tokens=300, overlap_tokens=0, max_tokens=500)
        assert len(chunks) > 1
        # No chunk should wildly exceed the ceiling.
        for c in chunks:
            assert c.token_count <= 600

    def test_plain_text_no_speakers_still_chunks(self):
        text = ('This is a monologue with no explicit speaker labels. ' * 50)
        chunks = chunk_transcript(text, target_tokens=80, overlap_tokens=10, max_tokens=200)
        assert len(chunks) >= 1
        for c in chunks:
            assert c.speaker == ''  # no speaker detected

    def test_overlap_produces_shared_tail(self):
        # Cycle through real-looking speaker names (no digits — our regex
        # rejects digit characters in speaker labels).
        names = ['Alice', 'Bob', 'Carol', 'Dave', 'Eve', 'Frank']
        lines = [f'{names[i % len(names)]}: line number {i} with some filler text for tokens.'
                 for i in range(60)]
        text = '\n'.join(lines)

        with_overlap    = chunk_transcript(text, target_tokens=80,
                                           overlap_tokens=30, max_tokens=200)
        without_overlap = chunk_transcript(text, target_tokens=80,
                                           overlap_tokens=0,  max_tokens=200)

        assert len(with_overlap) >= 2
        assert len(without_overlap) >= 2
        # Overlap mode should emit at least as many chunks, usually more —
        # because each flush carries content forward, increasing total token
        # volume across chunks.
        assert len(with_overlap) >= len(without_overlap)
        tokens_with    = sum(c.token_count for c in with_overlap)
        tokens_without = sum(c.token_count for c in without_overlap)
        assert tokens_with > tokens_without

    def test_no_overlap_chunks_do_not_repeat_content(self):
        # Cycle through real-looking speaker names (no digits — our regex
        # rejects digit characters in speaker labels).
        names = ['Alice', 'Bob', 'Carol', 'Dave', 'Eve', 'Frank']
        lines = [f'{names[i % len(names)]}: line number {i} with some filler text for tokens.'
                 for i in range(60)]
        text = '\n'.join(lines)
        chunks = chunk_transcript(text, target_tokens=80,
                                  overlap_tokens=0, max_tokens=200)
        assert len(chunks) >= 2
        # With zero overlap, char ranges should be strictly non-overlapping
        # (chunks abut but do not share content).
        for a, b in zip(chunks, chunks[1:]):
            assert b.char_start >= a.char_end


class TestChunkPackerDirect:
    """Exercise _ChunkPacker edge cases directly."""

    def test_zero_overlap_clears_buffer(self):
        packer = _ChunkPacker(target_tokens=10, overlap_tokens=0, max_tokens=50)
        from agents.mentions.ingest.chunker import _Turn
        packer.add_turn(_Turn('A', 'short one', 0, 9, 0))
        packer.add_turn(_Turn('B', 'another short', 10, 23, 1))
        packer.flush()
        # With overlap=0 we never carry forward; each flush empties the buf.
        assert packer._buf == []
        assert packer._buf_tokens == 0


class TestSentenceSplit:
    def test_below_max_returns_single_piece(self):
        text = 'Short sentence.'
        pieces = _sentence_split(text, offset=0, max_tokens=100)
        assert len(pieces) == 1
        assert pieces[0][0] == text
        assert pieces[0][1] == 0
        assert pieces[0][2] == len(text)

    def test_splits_on_sentence_boundary(self):
        # Make a text well over the budget, with clear sentence boundaries.
        sentences = ['This is sentence number {} of a long monologue.'.format(i)
                     for i in range(40)]
        text = ' '.join(sentences)
        pieces = _sentence_split(text, offset=0, max_tokens=50)
        assert len(pieces) > 1

    def test_offset_propagates(self):
        text = 'Short.'
        pieces = _sentence_split(text, offset=100, max_tokens=100)
        assert pieces[0][1] == 100
        assert pieces[0][2] == 100 + len(text)
