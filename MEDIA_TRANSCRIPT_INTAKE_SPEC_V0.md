# Media transcript intake spec V0

## Purpose

This spec defines what transcript data should be ingested to support the `media_appearance_framework` in `mentions`.

The goal is not generic transcript accumulation.
The goal is to build a usable historical corpus for media-appearance mention markets such as:
- Fox News hits
- Sunday shows
- host-driven interviews
- cable news appearances
- panel / moderated TV segments

---

## 1. Product goal

The media framework needs transcript support for questions like:
- does this speaker tend to reach the target topic in this kind of media format?
- does the mention usually require a direct host prompt?
- does the speaker self-bridge into the topic in short TV appearances?
- is the show format narrow/topic-bounded or permissive?

This means the corpus should be optimized for:
- **format relevance**
- **show relevance**
- **host-control relevance**
- **path-to-topic relevance**

not just generic same-speaker coverage.

---

## 2. Priority transcript classes

### Priority 1: same speaker, same show / same outlet family
Examples:
- same speaker on Fox News Sunday
- same speaker on Hannity
- same speaker on Bret Baier / Special Report
- same speaker on Meet the Press / Face the Nation / This Week / State of the Union

### Priority 2: same speaker, same media format
Examples:
- same speaker in short cable-news hit
- same speaker in host-driven TV interview
- same speaker in moderated Sunday-show interview

### Priority 3: same speaker, similar format family
Examples:
- if exact show is unavailable, use analogous interview/show format
- prioritize TV/interview/panel analogs over speeches/rallies

### Low priority / do not rely on by default
- rallies
- campaign speeches
- prepared remarks
- press releases
- unrelated long speeches

These can still exist in corpus, but they are weak analogs for media-appearance markets.

---

## 3. Required metadata

For each ingested transcript, capture as much of the following as possible.

### Required
- `speaker`
- `title`
- `event_title`
- `source_url` or `source_ref`
- `date` (exact if possible)
- full transcript text

### Strongly recommended
- `outlet`
  - e.g. Fox News, NBC, CBS, ABC, CNN
- `show_name`
  - e.g. Fox News Sunday, Hannity, Meet the Press
- `host_name`
- `format_type`
  - one of:
    - `cable_news_short_hit`
    - `sunday_show_interview`
    - `host_driven_interview`
    - `panel_segment`
    - `townhall_media_format`
    - `remote_hit`
    - `special_media_appearance`
- `segment_shape`
  - e.g. `topic_bounded`, `host_driven`, `looser_host_mix`
- `panel_mode`
  - `low`, `medium`, `high`
- `host_control`
  - `low`, `medium`, `high`

### Nice to have
- `guest_list`
- `is_live`
- `is_clip` vs `full_segment`
- `transcript_source_quality`
- `notes`

---

## 4. File naming guidance

User-supplied transcript files can be lightweight and practical.

Preferred filename shape:

```text
<speaker> - <outlet> - <show> - <date> - <short title>.txt
```

Examples:
- `Rick Scott - Fox News - Fox News Sunday - 2026-04-19 - interview.txt`
- `Donald Trump - Fox News - Hannity - 2026-02-11 - border interview.txt`
- `JD Vance - CBS - Face the Nation - 2026-03-03 - sunday show.txt`

If metadata is incomplete, acceptable fallback shape:

```text
<speaker> - <show or outlet> - <topic>.txt
```

Examples:
- `Rick Scott - Fox News Sunday - tariffs.txt`
- `Donald Trump - Hannity - Iran.txt`

Do not block intake on perfect naming. Ingestion can backfill later.

---

## 5. Ingest tagging requirements

When these transcripts are ingested, the runtime DB should preserve tags that make media retrieval possible.

### Needed tags / structured fields
- speaker tag
- outlet tag
- show tag
- host tag
- media format tag
- show family tag
- format control tag
  - e.g. `host_control:high`
- panel/solo tag
- interview type tag

### Example tag set
```json
{
  "speaker": "Rick Scott",
  "outlet": "Fox News",
  "show": "Fox News Sunday",
  "host": "Shannon Bream",
  "format_type": "sunday_show_interview",
  "show_family": "fox_news_sunday",
  "host_control": "high",
  "segment_shape": "topic_bounded",
  "panel_mode": "low"
}
```

---

## 6. Retrieval goals for this corpus

The corpus should enable future retrieval layers to answer:

### A. Same-show analogs
- did the speaker discuss similar topics on this exact show?

### B. Same-format analogs
- if exact show data is absent, what happens in comparable media formats?

### C. Path-to-topic analogs
- was the topic raised by host prompt?
- did speaker bridge into it?
- did it arise only in a reactive exchange?
- did it only appear in broader/longer interviews?

This is more important than merely finding the same noun in transcript text.

---

## 7. Anti-noise guidance

Do not treat these as strong media analogs by default:
- speech transcripts
- rally transcripts
- conference speeches
- campaign remarks
- generic press briefings

These can be fallback context, but they should not dominate media-appearance historical reads.

The media framework should prefer:
- format-correct but topic-adjacent analogs

over:
- topic-matching but format-wrong analogs

---

## 8. Recommended initial acquisition list

For V0 usefulness, prioritize collecting transcripts for:

### Fox / cable news
- Fox News Sunday
- Hannity
- The Ingraham Angle
- Jesse Watters Primetime
- Special Report with Bret Baier
- Fox & Friends

### Sunday shows
- Meet the Press
- Face the Nation
- This Week
- State of the Union

### Speakers
Prioritize speakers who actually appear in mention markets.

Examples:
- Trump
- White House / administration figures
- senators / governors who appear in political mention markets
- future recurring media-appearance speakers

---

## 9. V0 practical rule

A smaller but correctly tagged media transcript corpus is better than a larger, mixed, weakly-labeled dump.

For this framework:
- **quality of format metadata > raw transcript count**

---

## 10. Immediate next usage

This spec should guide:
1. manual transcript intake for media/show transcripts
2. future intake scripts for media transcript batches
3. media-format historical analog retrieval improvements
4. show-aware retrieval and path-to-topic evaluation
