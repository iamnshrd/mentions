# AGENTS.md - Mentions OpenClaw Workspace

This workspace is the OpenClaw-facing surface for `Mentions`.
Treat OpenClaw as the transport and orchestration shell, and treat the local runtime as the domain engine.

## First-Turn Rules

1. Read `SOUL.md`, `IDENTITY.md`, `USER.md`, and `TOOLS.md` before substantive work.
2. Prefer `mentionsctl` for market analysis, transcript search, wording checks, and prompt generation.
3. Treat `../library/` as a compatibility facade, not the primary runtime.
4. Treat `../legacy/pmt-architecture-dump/` as historical reference only.
5. Do not reimplement Mentions logic in ad-hoc shell snippets when `mentionsctl` already exposes it.
6. If `mentionsctl` is unavailable on PATH, use `./mentions-agent` from this workspace.

## Runtime Boundary

- OpenClaw handles transport, pairing, delivery, memory, and general workspace tooling.
- `mentionsctl` handles the actual Mentions domain pipeline.
- If you need the domain answer, start with:

```bash
mentionsctl answer mentions "<query>"
```

Fallback from this workspace:

```bash
./mentions-agent answer mentions "<query>"
```

- If you need the structured payload:

```bash
mentionsctl run mentions "<query>"
```
