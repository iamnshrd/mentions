# Bootstrap

This repository hosts the `mentions` runtime.

Rules for first turns:

1. Prefer `mentionsctl` for domain analysis, transcript search, wording checks, and scheduled scan workflows.
2. For conversational turns, start with `mentionsctl answer mentions "<query>"`.
3. Treat `mentions_core/` plus `agents/mentions/` as the only live runtime surface.
4. Historical migration context lives in `docs/notes/` and the migration specs, not in runtime code paths.
5. Prefer the local runtime surfaces in this repo (`mentionsctl`, `python -m mentions_core`, and the GitHub Pages UI) over ad-hoc wrappers.
