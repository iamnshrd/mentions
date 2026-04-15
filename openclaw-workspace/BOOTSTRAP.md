# Bootstrap

This directory is the dedicated OpenClaw workspace for the `mentions` agent.

Rules for first turns:

1. Use `mentionsctl` as the default domain entrypoint.
2. If `mentionsctl` is unavailable, use `./mentions-agent`.
3. Use `mentionsctl answer mentions "<query>"` when you want the final analyst reply.
4. Use `mentionsctl run mentions "<query>"` when you need the structured reasoning payload.
5. Use `mentionsctl prompt mentions "<query>" --system-only` when you need the prompt bundle.
6. Treat the parent repo as implementation detail and source material, not as the primary conversational surface.
