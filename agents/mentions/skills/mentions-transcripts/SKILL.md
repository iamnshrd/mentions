---
name: mentions-transcripts
description: "Thin wrapper around transcript ingest, search, and KB rebuild capability actions."
---

# Mentions Transcripts

Use the `transcripts` capability as the source of truth.

## Capability calls

```bash
mentionsctl capability mentions transcripts ingest auto --dry-run
mentionsctl capability mentions transcripts ingest transcript <file> --speaker "<speaker>"
mentionsctl capability mentions transcripts search "<query>" --limit 5
mentionsctl capability mentions transcripts build
```
