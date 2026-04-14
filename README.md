# Mentions — Kalshi Prediction Market Analyst

A rigorous, data-driven prediction market analyst agent for OpenClaw.

Designed for:
- Real-time analysis of Kalshi prediction market movements
- Multi-source synthesis: live data + news context + speaker transcript history
- Autonomous market monitoring (cron/scheduled mode)
- Structured output for dashboards and decision support
- Calibrated probability assessment with explicit reasoning chains

## Personality
Precise, analytical, intellectually honest. Shows its work. Labels uncertainty.
Contrast: Jordan finds meaning. Mentions finds signal.

## Best use cases
- "What's moving on Kalshi today and why?"
- "Is this price move in [market] signal or noise?"
- "What has [speaker] said historically about [topic]?"
- "Give me a deep analysis of [market ticker]."
- "Run an autonomous scan of top movers and write to dashboard."

## Telegram separation
This agent runs behind a separate Telegram bot binding.
Set `TELEGRAM_BOT_TOKEN` in `.env` (separate from the main assistant and Jordan).

## Data sources
1. **Kalshi API** — live market prices, volume, orderbook, history
2. **News context** — recent headlines affecting market categories
3. **Transcript corpus** — `library/transcripts/` — speaker history indexed for FTS

## Transcript ingestion
Drop transcripts (`.txt`, `.pdf`) into `library/incoming/` and run:
```
python -m library ingest auto
```
This chunks, indexes, and FTS-indexes the transcripts for retrieval during analysis.

## KB-backed runtime
All runtime logic lives under `library/_core/` and is accessed via the unified CLI:
```
python -m library run "<query>"              # full orchestrated response
python -m library prompt "<query>"           # LLM prompt bundle for OpenClaw
python -m library frame "<query>"            # market frame selection
python -m library fetch auto                 # fetch latest Kalshi market data
python -m library fetch market <ticker>      # fetch a single market
python -m library analyze "<query>"          # run analysis pipeline
python -m library ingest auto                # ingest transcripts from incoming/
python -m library ingest transcript <file>   # register a single transcript
python -m library kb build                   # rebuild market data + transcript index
python -m library kb query --query "fed"     # query cached data and transcripts
python -m library schedule run               # autonomous scheduled run (→ dashboard/)
python -m library eval audit                 # quality audit
```

## Architecture
```
Query / Cron
  ↓
Orchestrator (library/_core/runtime/orchestrator.py)
  ├── Route detection (routes.py)
  ├── Frame selection (frame.py)
  ├── Live data fetch (fetch/kalshi.py + fetch/news.py)
  ├── Transcript retrieval (kb/query.py + FTS)
  ├── Analysis pipeline (analysis/market.py, signal.py, speaker.py, reasoning.py)
  ├── LLM prompt assembly (llm_prompt.py)
  └── Response rendering (respond.py)
       ↓
  Session update (session/)
       ↓
  Dashboard output (dashboard/latest_analysis.json)
```

## Environment
Copy `env.example` to `.env` and fill in:
- `KALSHI_API_KEY` — Kalshi API credentials
- `TELEGRAM_BOT_TOKEN` — separate bot token for this agent
