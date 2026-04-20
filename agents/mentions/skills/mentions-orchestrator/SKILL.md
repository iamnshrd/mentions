---
name: mentions-orchestrator
description: "Thin orchestration wrapper for news_context -> analysis -> wording."
---

# Mentions Orchestrator

This wrapper orchestrates capabilities in a fixed order and keeps business logic out of the skill file.

## Flow

1. Build fresh context:

```bash
mentionsctl capability mentions news_context build "<query>"
```

2. Run analysis:

```bash
mentionsctl capability mentions analysis query "<query>"
```

3. If prose needs cleanup, rewrite through wording:

```bash
mentionsctl capability mentions wording rewrite "<text>"
```
