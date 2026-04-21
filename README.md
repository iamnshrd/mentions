# Mentions Runtime

`Mentions` в этом репо живёт как локальный runtime (`mentions_core`), доменный слой (`mentions_domain`) и прикладной пакет [`agents/mentions`](/Users/nshrd/Documents/Mentions/mentions/agents/mentions).

## Structure

- `mentions_core/` - локальный runtime-layer: CLI, pack registry, state/session, scheduler, logging
- `mentions_domain/` - канонический domain-layer: общие контракты, нормализация и переиспользуемая доменная логика
- `agents/mentions/` - pack с capability-слоями `transcripts`, `wording`, `news_context`, `analysis`
- `docs/` - активная документация, спецификации и GitHub Pages UI

## Install

```bash
python -m pip install -e '.[dev]'
pytest
```

После editable install доступен локальный runtime:

```bash
python -m mentions_core packs
mentionsctl packs
```

## Local runtime CLI

```bash
python -m mentions_core answer mentions "<query>"
python -m mentions_core run mentions "<query>"
python -m mentions_core prompt mentions "<query>" --system-only
python -m mentions_core capability mentions transcripts ingest auto
python -m mentions_core capability mentions analysis url "<kalshi-url>"
python -m mentions_core capability mentions news_context build "<query>" --require-live
python -m mentions_core schedule mentions run --dry-run
```

Для локальных conversational turns удобнее всего:

```bash
mentionsctl answer mentions "<query>"
```

## Mentions capabilities

1. `transcripts`
   - transcript ingest
   - chunking
   - FTS search
   - KB rebuild
2. `wording`
   - wording validation
   - rewrite rules
   - canonical market phrasing
3. `news_context`
   - live news fetch via NewsAPI
   - cache fallback for analysis
   - event context
   - direct / weak / late path mapping
4. `analysis`
   - query analysis
   - Kalshi URL analysis
   - LLM prompt bundle
   - autonomous scheduled scan

## Runtime data

- base session/state: `workspace/`
- Mentions pack data: `workspace/mentions/`
- generated dashboard output: `dashboard/mentions/`

## Web workspace payload

GitHub Pages UI lives in `docs/` and can consume a real runtime snapshot instead
of demo data.

Generate a workspace payload for the site:

```bash
python -m mentions_core workspace "What will Bernie Sanders say at the More Perfect University Kick Off Call?" \
  --output docs/ui/workspace-data.json
```

Equivalent helper:

```bash
python scripts/export_workspace_payload.py "What will Bernie Sanders say at the More Perfect University Kick Off Call?" \
  --output docs/ui/workspace-data.json
```

After committing and pushing `docs/ui/workspace-data.json`, the Pages site will
load that runtime snapshot automatically.

## Compatibility

- локальный runtime CLI: `python -m mentions_core ...` или `mentionsctl ...`

Path migration details are documented in `docs/specs/MIGRATION.md`.
Architecture ownership and migration sequencing are documented in `docs/specs/ARCHITECTURE_MIGRATION_MAP.md`.

## Runtime infrastructure

- module bindings: `agents/mentions/assets/module_bindings.json`
- runtime health: `python -m mentions_core health`
- canonical module wiring: `agents/mentions/module_registry.py`

## Environment

Copy `env.example` to `.env` and configure:

- `KALSHI_API_KEY`
- `KALSHI_API_URL`
- `KALSHI_ENV`
- `NEWSAPI_KEY`
- `TELEGRAM_BOT_TOKEN`
