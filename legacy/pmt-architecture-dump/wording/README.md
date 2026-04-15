# Markets Wording DB

This folder is the source of truth for wording discipline in market analysis writeups.

## Files
- `markets_wording_db.json` — machine-readable wording rules

## Core rules
- Russian by default
- Keep English only where market language is genuinely better
- Avoid ugly Russian-English hybrids
- If the user gave an exact preferred phrase, use it verbatim
- Do not "improve" approved wording

## Important formatting rule
For strike names in prose:
- prefer the human label only
- format it in monospace
- avoid ticker + full pair spam

Example:
- avoid: `SETT — Settle / Deal`
- prefer: `` `Deal` ``

## Workflow rule
Before sending market-analysis prose, check whether the phrase already has a preferred replacement in `markets_wording_db.json`.
