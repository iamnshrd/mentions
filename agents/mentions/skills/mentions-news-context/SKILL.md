---
name: mentions-news-context
description: "Thin wrapper around the Mentions news_context capability. Use when you need fresh event/news setup before pricing or analysis."
---

# Mentions News Context

Use the `news_context` capability instead of embedding domain logic in this skill.

## Capability call

Primary action:

```bash
mentionsctl capability mentions news_context build "<query>" --category <category>
```

Use `--require-live` when the task explicitly requires a live provider result and should fail if `NEWSAPI_KEY` or the provider is unavailable.

## Output contract

Return the capability output as the source of truth:
- `news_status`
- `news_summary`
- `event_context`
- `direct_paths`
- `weak_paths`
- `late_paths`

## References

Use these only for framing and wording, not as executable logic:
- `references/context-framework.md`
- `references/source-priority.md`
- `references/output-template.md`
- `references/examples.md`
