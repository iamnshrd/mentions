# Legacy compatibility layer

`library/` is a compatibility facade only.

## Rule

- New business logic should **not** be added to `library/`.
- Canonical runtime code belongs in:
  - `mentions_core/`
  - `agents/mentions/`

## What may stay here

- import shims
- CLI compatibility wrappers
- thin facades forwarding into canonical modules

## Why

The repo is mid-migration from old `library.*` paths to modular runtime paths.
This directory stays only to avoid breaking older imports and command habits while the migration finishes.
