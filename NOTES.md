# NOTES.md — Mentions Development Log

## Status
**v0.1 — Scaffolding**
Repository created. Core structure in place. Runtime wired. No live data yet.

## Evolution
This agent evolved from the `mentions` skill (standalone Kalshi analysis skill) into a full OpenClaw agent with:
- Persistent session state and continuity tracking (like Jordan)
- A transcript corpus as a second knowledge source alongside live market data
- Autonomous cron/scheduler mode for unattended market monitoring
- Structured JSON output for downstream dashboards

## Architecture Notes
- Mirrors Jordan's structure: `library/_core/runtime/`, `library/_core/session/`, `library/_adapters/`
- Two knowledge sources: live Kalshi API + local transcript corpus (FTS-indexed)
- Runtime orchestrator supports both interactive (query/response) and autonomous (scheduled) modes
- SQLite DB: `library/mentions_data.db` — markets, history, analysis cache, transcript chunks

## TODO
- [ ] Connect Kalshi API client (requires `KALSHI_API_KEY`)
- [ ] Seed initial transcript corpus (Fed speeches, relevant earnings calls)
- [ ] Configure cron schedule for autonomous market monitoring
- [ ] Build dashboard output pipeline
- [ ] Add embedding support for transcript semantic search
- [ ] Add eval/regression test suite
- [ ] Wire Telegram bot binding (separate from main assistant)
