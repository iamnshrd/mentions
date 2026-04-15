# market_pipeline

Small coherent wrapper around the current DB-backed market analysis helpers.

## Commands

### Analyze with KB retrieval
```bash
python3 /root/.openclaw/workspace/market_pipeline/cli.py analyze KXTRUMPMENTIONB-26APR06B --preset trump-live-qa --freeform "Iran press conference / Brady Briefing Room style event, live remarks, likely direct Iran paths plus possible broader geopolitics and reporter-driven expansion"
```

### Render structured report
```bash
python3 /root/.openclaw/workspace/market_pipeline/cli.py report KXTRUMPMENTIONB-26APR06B --preset iran-press
```

### Render report JSON only
```bash
python3 /root/.openclaw/workspace/market_pipeline/cli.py report KXTRUMPMENTIONB-26APR06B --preset iran-press --json
```

### General Trump live-Q&A report scaffold
```bash
python3 /root/.openclaw/workspace/market_pipeline/cli.py report KXTRUMPMENTION-26APR25 --preset trump-live-qa --json
```

### General briefing-style report scaffold
```bash
python3 /root/.openclaw/workspace/market_pipeline/cli.py report KXTRUMPMENTIONB-26APR06B --preset briefing-style --json
```

### Strike classification scaffold
```bash
python3 /root/.openclaw/workspace/market_pipeline/classify_strikes.py KXTRUMPMENTIONB-26APR06B --preset iran-press
```

`iran-press` report preset now auto-fills basket strikes from `classify_strikes.py` instead of hardcoding them inside the report builder.

### Overrides
- `/root/.openclaw/workspace/market_pipeline/overrides.json`
- supports:
  - `ticker_overrides`
  - `label_overrides`
  - `preset_overrides`

### Publish flow
```bash
python3 /root/.openclaw/workspace/market_pipeline/publish.py KXTRUMPMENTIONB-26APR06B --preset iran-press
```
Now includes:
- report validation
- wording warnings
- classifier diagnostics

## Notes
- This is a wrapper/refactor layer, not a replacement for the underlying scripts yet.
- It keeps the current working pieces but gives the stack a coherent entrypoint.
