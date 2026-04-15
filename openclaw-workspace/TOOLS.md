# Tools

Primary domain tool for this workspace:

```bash
mentionsctl
```

## Common commands

```bash
mentionsctl answer mentions "<query>"
mentionsctl run mentions "<query>"
mentionsctl prompt mentions "<query>" --system-only
mentionsctl capability mentions analysis query "<query>"
mentionsctl capability mentions analysis url "<kalshi-url>"
mentionsctl capability mentions news_context build "<query>"
mentionsctl capability mentions transcripts search "<query>" --limit 5
mentionsctl capability mentions wording rewrite "<text>"
mentionsctl schedule mentions run --dry-run
```

## Notes

- `mentionsctl answer` is the best default for conversational turns.
- `mentionsctl run` returns the full structured analysis payload.
- The codebase lives one directory above this workspace.

## Workspace fallback

If `mentionsctl` is not installed on PATH in this workspace, use:

```bash
./mentions-agent answer mentions "<query>"
./mentions-agent run mentions "<query>"
./mentions-agent prompt mentions "<query>" --system-only
```
