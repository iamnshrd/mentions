# Migration Guide

Этот репозиторий больше не считает `library/` каноническим runtime-слоем.
Также локальный runtime больше не использует имя `openclaw`, чтобы не конфликтовать с официальным OpenClaw Gateway.

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

## Gateway commands

Официальный `openclaw` теперь используется только для upstream Gateway/transport-команд, например:

- `openclaw onboard --install-daemon`
- `openclaw gateway status`
- `openclaw dashboard`
- `openclaw agent --agent mentions --message "<query>"`

## Module migration

- `library._core.runtime.*` -> `agents.mentions.runtime.*`
- `library._core.analysis.*` -> `agents.mentions.analysis.*`
- `library._core.fetch.*` -> `agents.mentions.fetch.*`
- `library._core.ingest.*` -> `agents.mentions.ingest.*`
- `library._core.kb.*` -> `agents.mentions.kb.*`
- `library._core.eval.*` -> `agents.mentions.eval.*`
- `library._core.scheduler.*` -> `agents.mentions.scheduler.*`
- `library._core.session.*` -> `mentions_core.base.session.*`
- `library._core.state_store` -> `mentions_core.base.state_store`
- `library._adapters.fs_store` -> `mentions_core.base.adapters.fs_store`

## What stays in `library/`

`library/` remains as a compatibility facade for:

- old import paths
- old package-level imports
- old `python -m library ...` CLI usage

It is intentionally thin and should not receive new business logic.
