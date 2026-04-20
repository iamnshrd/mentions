# Bootstrap

This repository hosts the `mentions` runtime.

Rules for first turns:

1. Prefer `mentionsctl` for domain analysis, transcript search, wording checks, and scheduled scan workflows.
2. For conversational turns, start with `mentionsctl answer mentions "<query>"`.
3. Treat `mentions_core/` plus `agents/mentions/` as the only live runtime surface.
4. Historical migration context lives in `docs/notes/` and the migration specs, not in runtime code paths.
5. Use Telegram and other transport surfaces through the official OpenClaw Gateway, not through custom bot code in this repo.
