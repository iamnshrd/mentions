# Tools

Primary domain tool for this workspace:

```bash
mentionsctl
```

Use it for deterministic Mentions workflows instead of rebuilding the analysis manually.

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

Используйте `mentionsctl` или `python -m mentions_core ...` как единственные локальные CLI-пути.
