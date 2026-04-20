# AGENTS.md - Mentions

`Mentions` runs behind the official OpenClaw Gateway, but its domain logic lives in the local runtime.

## Mission

Be a rigorous, data-driven analyst of Kalshi prediction markets.
Collect live market data, transcript history, and news context, then return calibrated reasoning with explicit uncertainty.

## Interfaces

Official Gateway / transport layer:

- `openclaw gateway`
- `openclaw dashboard`
- dedicated OpenClaw workspace in `openclaw-workspace/`

Local runtime / pack tooling:

- `python -m mentions_core answer mentions "<query>"`
- `python -m mentions_core run mentions "<query>"`
- `python -m mentions_core prompt mentions "<query>"`
- `python -m mentions_core capability mentions analysis query "<query>"`
- `python -m mentions_core capability mentions analysis url "<kalshi-url>"`
- `python -m mentions_core schedule mentions run`
- `python -m mentions_core capability mentions news_context build "<query>" --require-live`

Default OpenClaw-facing domain entrypoint:

- `mentionsctl answer mentions "<query>"`

## Pack pipeline

Every request flows through:

1. `Route`
2. `Frame`
3. `Fetch`
4. `Retrieve`
5. `Analyze`
6. `Respond`

Capability boundaries:

- `transcripts`
- `wording`
- `news_context`
- `analysis`

## Data locations

- base session/continuity state: `workspace/`
- Mentions pack data and DB: `workspace/mentions/`
- OpenClaw persona/bootstrap workspace: `openclaw-workspace/`
- OpenClaw gateway config for local testing: `gateway/openclaw.local.example.json5`

## Required env

- `KALSHI_ENV`
- `KALSHI_API_URL`
- `KALSHI_API_KEY`
- `NEWSAPI_KEY`
- `TELEGRAM_BOT_TOKEN`

## Transport

Design assumption: this agent should run behind a separate Telegram bot token/binding from other assistants.
