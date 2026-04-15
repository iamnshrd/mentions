---
name: mentions-analyst
description: "Thin wrapper around the Mentions analysis capability for query, URL, prompt, and autonomous flows."
---

# Mentions Analyst

Use the `analysis` capability as the executable layer.

## Capability calls

```bash
mentionsctl capability mentions analysis query "<query>"
mentionsctl capability mentions analysis url "<kalshi-url>"
mentionsctl capability mentions analysis prompt "<query>" --system-only
mentionsctl capability mentions analysis autonomous --dry-run
```
