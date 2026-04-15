# Mentions Runtime + OpenClaw Gateway

`Mentions` в этом репо теперь живёт как локальный runtime (`mentions_core`) и отдельный agent pack, который предполагается монтировать за официальным OpenClaw Gateway.
По рабочему паттерну это ближе к `jordan`: OpenClaw снаружи, доменная логика внутри репо, отдельный OpenClaw workspace в `openclaw-workspace/`.

## Structure

- `mentions_core/` - локальный runtime-layer: CLI, pack registry, state/session, scheduler, logging
- `agents/mentions/` - pack с capability-слоями `transcripts`, `wording`, `news_context`, `analysis`
- `openclaw-workspace/` - выделенная OpenClaw-facing persona/workspace поверхность
- `gateway/` - локальные шаблоны и инструкции для официального OpenClaw Gateway
- `legacy/pmt-architecture-dump/` - read-only архив старой skill/pipeline архитектуры
- `library/` - legacy compatibility layer для старых импортов и `python -m library ...`

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

Официальный transport/gateway CLI остаётся за upstream OpenClaw:

```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
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

Для OpenClaw conversational turns удобнее всего:

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

## Gateway integration

- официальный `openclaw` CLI отвечает за transport, pairing, dashboard и channel routing
- локальный `mentions_core` отвечает за pack/runtime-логику
- OpenClaw-facing workspace bootstrap лежит в `openclaw-workspace/`
- пример gateway-конфига лежит в [gateway/openclaw.local.example.json5](/Users/nshrd/Documents/New%20project/gateway/openclaw.local.example.json5:1)

### Telegram ACP Runbook

Для обычного Telegram DM рабочий путь такой:

1. Подними gateway: `./gateway/run-local-gateway.sh`
2. Одобри pairing
3. В чате с ботом отправь:

```text
/acp spawn codex --bind here --cwd /tmp/mentions-openclaw-workspace
```

4. После успешного bind общайся обычными сообщениями

Важно: для DM не используй static `bindings[].type="acp"` в gateway config. Рабочий путь — именно `/acp spawn ... --bind here` из самого чата.

## Compatibility

- локальный runtime CLI: `python -m mentions_core ...` или `mentionsctl ...`
- legacy CLI kept for compatibility: `python -m library ...`
- legacy imports under `library.*` re-export from `mentions_core` and `agents.mentions`

Path migration details are documented in [MIGRATION.md](/Users/nshrd/Documents/New%20project/MIGRATION.md:1).

## Environment

Copy `env.example` to `.env` and configure:

- `KALSHI_API_KEY`
- `KALSHI_API_URL`
- `KALSHI_ENV`
- `NEWSAPI_KEY`
- `TELEGRAM_BOT_TOKEN`
