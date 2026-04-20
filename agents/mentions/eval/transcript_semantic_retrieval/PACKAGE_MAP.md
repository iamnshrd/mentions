# transcript_semantic_retrieval package map

## Purpose

This package contains the ML-backed transcript-family retrieval layer used by `mentions`.

Important: not every file here is part of the active runtime path.
The package contains both:
- active ML retrieval/runtime pieces
- research and calibration tooling

## 1. Main-path runtime files

These are the files that matter for the active `mentions` transcript ML path:

- `client.py`
  - remote worker HTTP client
  - health checks
  - embedding requests
  - family scoring
  - news scoring

- `family_taxonomy.py`
  - canonical transcript family definitions
  - mode / expression / exclude-term configuration

- `strategy.py`
  - family-oriented retrieval entrypoint used by the active ML path

- `prototype.py`
  - lower-level semantic segment retrieval helper used by strategy-level code

## 2. Supporting package surface

- `__init__.py`
  - package-level exports
  - currently exposes:
    - `retrieve_family_segments`
    - `semantic_segment_search`

## 3. Research / perimeter tooling

These files are not part of the current main runtime path.
They exist for discovery, inspection, evaluation, calibration, and planning:

- `ab_compare.py`
- `cluster_discovery.py`
- `corpus_discovery.py`
- `experimental_path.py`
- `family_inspection.py`
- `family_rollout.py`
- `family_completion_plan.py`
- `candidate_sourcing_plan.py`
- `family_evaluation.py`

## 4. Practical rule

When changing the live `mentions` path, prefer touching:
- `client.py`
- `family_taxonomy.py`
- `strategy.py`
- `prototype.py`
- `transcript_intelligence/ml_builder.py`

Do not assume changes in the research/perimeter files affect production behavior unless they are explicitly wired into the main path.
