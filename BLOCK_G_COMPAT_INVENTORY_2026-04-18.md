# Block G inventory (Compatibility / legacy shells)

## Purpose
This note records the currently visible compatibility surfaces after Block D and Block B reached checkpoint status.

The goal is to narrow and document these shells, not to let them quietly re-grow into active logic centers.

---

## Main compatibility surface

### `library/`
`library/` is now the largest obvious legacy compatibility surface.

It currently exists as a facade for historical imports and CLI entrypoints, while the canonical active implementation lives under:
- `agents/mentions/*`
- `mentions_core/*`

### Current compatibility areas seen in `library/`
- `library/__main__.py` (legacy CLI shim)
- `library/_core/runtime/*` (runtime compatibility barrel/shims)
- `library/_core/fetch/*` (fetch compatibility barrel/shims)
- `library/_core/analysis/*` (analysis compatibility barrel/placeholders)
- additional package facades under:
  - `library/_core/ingest/`
  - `library/_core/kb/`
  - `library/_core/eval/`
  - `library/_core/session/`
  - `library/_adapters/`

---

## Already clearly marked

The following are already explicitly documented as compatibility-only or legacy:
- `library/README.md`
- `library/__main__.py`
- `library/_core/runtime/__init__.py`
- `library/_core/fetch/__init__.py`
- `library/_core/analysis/__init__.py`
- multiple facade `__init__.py` files under `library/_core/*`
- `agents/mentions/modules/memo_renderer/renderer.py`
- `agents/mentions/modules/output_profiles/profiles.py`
- `agents/mentions/presentation/render_analysis.py`

---

## First safe narrowing step completed

### `library/__init__.py`
The top-level legacy package now explicitly states:
- do not add new runtime logic here
- canonical imports should point to active modules

It also now exports:
- `__all__ = []`

This is a small but useful signal that root-level `library` should not act like a growing public API surface.

---

## Practical reading of risk

### Low-risk compatibility shells
These mostly look like acceptable thin wrappers for now:
- direct one-function shims
- documented package barrels with no independent logic
- compatibility-only CLI entrypoints

### Higher-risk compatibility shells
These deserve closer attention later in Block G:
- barrels that re-export many symbols and can keep old import paths alive indefinitely
- any compatibility file that starts accumulating formatting, routing, or fallback logic
- any shim that silently diverges from canonical active modules

---

## Rule for Block G going forward

When touching a compatibility shell:
1. prefer marking and narrowing over rewriting
2. keep wrappers thin and explicit
3. avoid adding new behavior to legacy surfaces
4. prefer canonical imports from `agents/mentions/*` or `mentions_core/*`
5. document any remaining compatibility shell that must stay alive
