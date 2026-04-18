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

- `library/` is compatibility-only
- canonical runtime code lives in `mentions_core/` and `agents/mentions/`
- `runtime/synthesize_speaker.py` is now decomposed into:
  - `runtime/synthesize_speaker.py` for synthesis assembly
  - `runtime/speaker_report.py` for report/render shaping
  - `runtime/speaker_paths.py` for topic-path / basket / interpretation logic
- `modules/transcript_semantic_retrieval/` now contains both:
  - main-path ML retrieval files (`client.py`, `strategy.py`, `family_taxonomy.py`, `prototype.py`)
  - research/perimeter tooling (see `modules/transcript_semantic_retrieval/PACKAGE_MAP.md`)

## Notes

- `pytest` is expected through `.[dev]`
- `library/` is compatibility-only
- canonical runtime code lives in `mentions_core/` and `agents/mentions/`
- module bindings live in `agents/mentions/assets/module_bindings.json`
