# Block G checkpoint (Compatibility / legacy shells)

## Scope
This checkpoint records the current state of **Block G: Compatibility / legacy shells** after a controlled narrowing pass across the main `library/` compatibility perimeter.

---

## Canonical active path

The active implementation path remains under:
- `agents/mentions/*`
- `mentions_core/*`

The `library/` tree now exists primarily as a **legacy compatibility facade**, not as an independent implementation center.

---

## What was done in this cleanup sequence

### 1. Root compatibility package was narrowed
- `library/__init__.py`

It now explicitly states that new runtime logic should not be added there, and exports:
- `__all__ = []`

This reduces the chance of root `library` becoming an accidental public API growth surface.

### 2. Major `library/_core/*` facades were narrowed
The following package facades were cleaned up so they now act as thin re-export surfaces and point directly at canonical modules instead of bouncing through extra local wrappers:

- `library/_core/runtime/__init__.py`
- `library/_core/fetch/__init__.py`
- `library/_core/analysis/__init__.py`
- `library/_core/ingest/__init__.py`
- `library/_core/kb/__init__.py`
- `library/_core/session/__init__.py`
- `library/_core/eval/__init__.py`
- `library/_core/scheduler/__init__.py`

Each now explicitly warns against adding new logic there.

### 3. Wildcard compatibility shims were removed from the touched surfaces
The following legacy shims were narrowed from `import *` to explicit imports + explicit `__all__`:

- `library/_core/fetch/auto.py`
- `library/_core/ingest/auto.py`
- `library/_core/ingest/transcript.py`
- `library/_core/kb/build.py`
- `library/_core/kb/migrate.py`
- `library/_core/kb/query.py`
- `library/_core/session/checkpoint.py`
- `library/_core/session/context.py`
- `library/_core/session/continuity.py`
- `library/_core/session/progress.py`
- `library/_core/session/state.py`
- `library/_core/eval/audit.py`
- `library/_core/scheduler/runner.py`

This materially reduced silent surface sprawl in the compatibility layer.

### 4. Retired placeholder was clarified
- `library/_core/analysis/history.py`

This file is now explicitly documented as a retired compatibility placeholder rather than a potentially live analysis helper.

### 5. Compatibility inventory was documented
- `BLOCK_G_COMPAT_INVENTORY_2026-04-18.md`

This inventory records the visible compatibility surfaces, the risk split between low-risk and higher-risk shells, and the rule that Block G work should narrow/document rather than regrow the legacy perimeter.

---

## Practical effect

### Before
The `library/` tree still looked like a semi-live alternate API layer in several places, with repeated:
- wildcard exports
- local barrel indirection
- unclear public compatibility surface shape

### After
The `library/` tree now reads much more clearly as:
- a compatibility facade
- thin direct re-exports
- explicit compatibility-only perimeter

That does not eliminate `library/`, but it does make it much less likely to drift back into an active implementation center.

---

## Validation
Throughout these changes, targeted import checks continued to pass for:
- `library`
- `library._core.runtime`
- `library._core.fetch`
- `library._core.analysis`
- `library._core.ingest`
- `library._core.kb`
- `library._core.session`
- `library._core.eval`
- `library._core.scheduler`

This gives reasonable confidence that compatibility imports remain intact while the perimeter is being narrowed.

---

## What still remains

### Still allowed to exist
- thin compatibility re-export files
- compatibility-only CLI shims
- explicit retired placeholders where removing the import path outright would be noisier than keeping a harmless shell

### Still worth watching later
- any untouched compatibility subtree outside the currently narrowed surfaces
- any future feature work that starts adding logic back into `library/`
- any external consumers still relying on broad historical import paths

---

## Practical assessment

### Block G status
- **checkpoint-ready**

### Why checkpoint-ready
- the main visible `library/_core/*` facades were narrowed
- wildcard export sprawl was materially reduced
- the compatibility perimeter is now much more explicit
- repeated import validation stayed clean

### What this means
Block G can now be paused at a controlled checkpoint. Future compatibility cleanup can continue later, but the highest-value visible perimeter work has already been done.

---

## Rule from here

If compatibility work resumes later:
1. prefer explicit imports over wildcard exports
2. prefer direct re-exports from canonical modules
3. keep facade files thin and declarative
4. do not add new business/runtime logic into `library/`
5. document retired placeholders instead of letting them silently look live
