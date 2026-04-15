# Deprecated pipeline files

These files remain as compatibility shims only:
- query_kb_for_market.py
- select_kb_bundle.py
- analyze_event_with_kb.py
- build_event_report_json.py
- render_structured_memo.py

Canonical implementation now lives in:
- /root/.openclaw/workspace/market_pipeline/

Future cleanup path:
1. update all references to use `market_pipeline/cli.py` or the package modules directly
2. once no callers depend on the old paths, remove the transcript-level shims
