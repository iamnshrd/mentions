# Development

## Install

Create a local virtualenv and install editable dev dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
```

## Core checks

```bash
python -m mentions_core packs
python -m mentions_core health
python -m mentions_core answer mentions "Will Trump mention Iran in a speech?"
PYTHONPATH=. python3 scripts/smoke_speaker_url.py --fast
```

## Current structural notes

- canonical runtime code lives in `mentions_core/` and `agents/mentions/`
- `workflows/synthesize_speaker.py` is now decomposed across:
  - `agents/mentions/workflows/synthesize_speaker.py`
  - `agents/mentions/presentation/speaker_report.py`
  - `agents/mentions/services/speakers/paths.py`
- semantic transcript retrieval lives under:
  - `agents/mentions/services/transcripts/semantic_retrieval/`
  - `agents/mentions/eval/transcript_semantic_retrieval/`

## Notes

- `pytest` is expected through `.[dev]`
- canonical runtime code lives in `mentions_core/` and `agents/mentions/`
- module bindings live in `agents/mentions/assets/module_bindings.json`
