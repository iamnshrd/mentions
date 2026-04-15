---
name: mentions-trade-memo
description: "Legacy wrapper skill. For new flows, prefer mentions-orchestrator."
---

# Mentions Trade Memo

This skill is kept as a compatibility wrapper.

## Preferred flow

1. Run `mentions-news-context`
2. Run `mentions-analyst`
3. If the answer is user-facing prose, run `mentions-wording`

## Canonical commands

```bash
mentionsctl capability mentions news_context build "<query>"
mentionsctl capability mentions analysis query "<query>"
mentionsctl capability mentions wording rewrite "<text>"
```
