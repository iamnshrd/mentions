# Migration Guide

Этот репозиторий больше не использует `library/` как runtime-слой.
Также локальный runtime больше не использует старое transport-specific branding.

## CLI migration

- старый путь: `python -m library run "<query>"`
- новый путь: `python -m mentions_core run mentions "<query>"`

- старый путь: `python -m library prompt "<query>"`
- новый путь: `python -m mentions_core prompt mentions "<query>"`

- старый путь: `python -m library ingest auto`
- новый путь: `python -m mentions_core capability mentions transcripts ingest auto`

- старый путь: `python -m library ingest transcript <file>`
- новый путь: `python -m mentions_core capability mentions transcripts ingest transcript <file>`

- старый путь: `python -m library analyze "<query>"`
- новый путь: `python -m mentions_core capability mentions analysis query "<query>"`

- старый путь: `python -m library schedule run`
- новый путь: `python -m mentions_core schedule mentions run`

## Module migration

- `library._core.runtime.*` -> `agents.mentions.workflows.*`
- `library._core.analysis.*` -> `agents.mentions.services.analysis.*`, `agents.mentions.services.markets.*`, `agents.mentions.services.speakers.*`
- `library._core.fetch.*` -> `agents.mentions.providers.*`, `agents.mentions.workflows.fetch_auto`, `mentions_core.base.net.*`
- `library._core.ingest.*` -> `agents.mentions.ingest.*`
- `library._core.kb.*` -> `agents.mentions.services.knowledge.*`, `agents.mentions.storage.knowledge.*`, `agents.mentions.storage.importers.*`
- `library._core.eval.*` -> `agents.mentions.eval.*`
- `library._core.scheduler.*` -> `agents.mentions.workflows.scheduling.*`, `agents.mentions.workflows.*`
- `library._core.session.*` -> `mentions_core.base.session.*`
- `library._core.state_store` -> `mentions_core.base.state_store`
- `library._core.obs.*` -> `mentions_core.base.obs.*`
- `library._core.retrieve.*` -> `agents.mentions.services.retrieval.*`, `agents.mentions.storage.retrieval.*`
- `library._core.extract.*` -> `agents.mentions.services.extraction.*`
- `library._adapters.fs_store` -> `mentions_core.base.adapters.fs_store`

## Legacy status

`library/` removed from the live tree. Historical references remain only in migration docs and notes.

## Post-migration domain promotions

- `agents.mentions.services.analysis.regime` -> `mentions_domain.analysis.regime`
- pure hedge/contradiction rules from `agents.mentions.services.markets.hedge_check` -> `mentions_domain.analysis.hedge_check`
- `agents.mentions.services.analysis.evidence_conflict` -> `mentions_domain.analysis.evidence_conflict`
- pure anti-pattern projection/scoring from `agents.mentions.services.analysis.anti_patterns` -> `mentions_domain.analysis.anti_patterns`
