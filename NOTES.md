# NOTES.md — Mentions Development Log

## Status
**v0.4 — split local runtime from official OpenClaw**
Base/pack split implemented. Local runtime now lives under `mentions_core`, while official `openclaw` is reserved for the upstream Gateway/transport layer.

## Evolution
This project evolved from the `mentions` skill into:
- reusable `OpenClaw base`
- pluggable `Mentions` agent pack
- capability-layer split: transcripts / wording / news_context / analysis

## Architecture Notes
- Base layer now lives in `mentions_core/`
- Mentions runtime and capabilities now live in `agents/mentions/`
- Legacy PMT/skill architecture moved to `legacy/pmt-architecture-dump/`
- SQLite DB now lives under `workspace/mentions/`
- `library/` now acts as a compatibility facade instead of a second runtime
- Package-level legacy imports are covered by tests
- `gateway/` now holds local config templates for the official OpenClaw Gateway

## TODO
- [ ] Seed initial transcript corpus (Fed speeches, relevant earnings calls)
- [ ] Expand test coverage around autonomous scan and capability wrappers
- [ ] Add embedding support for transcript semantic search
- [ ] Wire Telegram bot binding (separate from main assistant)
- [ ] Decide when to formally deprecate `python -m library ...`
- [ ] Wire the official OpenClaw Gateway to this workspace and validate Telegram pairing end-to-end
