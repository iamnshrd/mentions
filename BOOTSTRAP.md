# Bootstrap

This repository hosts the `mentions` runtime.

Rules for first turns:

1. Prefer `mentionsctl` for domain analysis, transcript search, wording checks, and scheduled scan workflows.
2. For conversational turns, start with `mentionsctl answer mentions "<query>"`.
3. Treat `library/` as a compatibility facade, not the primary runtime.
4. Treat `legacy/pmt-architecture-dump/` as historical reference only.
5. Use Telegram and other transport surfaces through the official OpenClaw Gateway, not through custom bot code in this repo.
