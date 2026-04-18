# Block D checkpoint (Presentation / user output)

## Scope
This checkpoint records the current state of **Block D: Presentation / user output** after the recent cleanup passes.

---

## Canonical active path

The current canonical user-facing output path is now:

1. `agents/mentions/presentation/response_renderer.py`
2. `agents/mentions/presentation/profile_renderers.py`
3. supporting presentation helpers:
   - `agents/mentions/presentation/user_output.py`
   - `agents/mentions/presentation/media_output.py`
   - `agents/mentions/presentation/report_common.py`
   - `agents/mentions/presentation/report_sections.py`
   - `agents/mentions/presentation/wording_adapter.py`

Active runtime entrypoints now point at this path:
- `agents/mentions/runtime/respond.py`
- `agents/mentions/module_registry.py`

---

## What changed

### 1. Old memo renderer was deactivated as an independent prose engine
- `agents/mentions/modules/memo_renderer/renderer.py`
- now acts as a compatibility wrapper over:
  - `agents.mentions.presentation.response_renderer.render_user_response`

### 2. Old output profile surface was deactivated as an independent renderer
- `agents/mentions/modules/output_profiles/profiles.py`
- now acts as a compatibility wrapper over:
  - `agents.mentions.presentation.profile_renderers.build_output_profiles`

### 3. User-facing wording was moved further into presentation layer
Presentation layer now owns more of:
- section wording
- visibility rules
- media humanization
- common report phrasing
- mixed-language cleanup

### 4. Technical leakage was reduced
Examples cleaned from normal user-facing paths:
- raw media/path enums
- multiple English memo labels
- mixed English/Russian fallback headings

---

## Presentation modules by responsibility

### `presentation/response_renderer.py`
Canonical user-facing renderer for full responses.

### `presentation/profile_renderers.py`
Builds rendered output profiles:
- `telegram_brief`
- `trade_memo`
- `investor_note`

### `presentation/user_output.py`
Humanizes interpretation-layer lines and assembles user-facing output sections.

### `presentation/media_output.py`
Media-specific humanization:
- show labels
- path labels
- media report block

### `presentation/report_common.py`
Common report phrasing helpers.

### `presentation/report_sections.py`
Section-level render/visibility helpers.

### `presentation/wording_adapter.py`
Text cleanup and wording normalization.

---

## Compatibility shells still present

These still exist, but should be treated as compatibility-only:

- `agents/mentions/modules/memo_renderer/*`
- `agents/mentions/modules/output_profiles/*`

They should no longer be treated as canonical logic owners.

---

## Remaining risks inside Block D

1. Some wording may still feel mixed or awkward in edge/fallback paths.
2. `speaker_report.py` still contains some report assembly glue that could be moved later.
3. Some user-facing text can still inherit awkward phrasing from upstream analysis/synthesis fields.
4. Rare/less-used compatibility paths may still contain stale phrasing.

---

## Current done status for Block D

### Already achieved
- canonical output path is explicit
- active runtime now points at presentation-based renderer
- major legacy output surfaces are no longer autonomous
- raw technical label leakage was reduced
- multiple smoke checks passed after the cleanup

### Not fully done yet
- complete elimination of all compatibility wrappers
- full migration of remaining section assembly out of runtime report code
- full wording polish across all rare/fallback paths

---

## Practical rule from here

Any new user-facing prose work should default to:
- `presentation/*`

and should **not** add new prose assembly logic back into:
- `runtime/*`
- `modules/memo_renderer/*`
- `modules/output_profiles/*`
