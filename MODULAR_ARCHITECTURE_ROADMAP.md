# Mentions Modular Architecture Roadmap

This document defines the target modular architecture for `mentions`, using the Jordan codebase as the structural reference point, but adapted for market-analysis workloads.

---

## 1. Why this refactor exists

The current `mentions` repo already has the right general direction:
- OpenClaw as transport/runtime shell
- local domain runtime behind it
- pack/capability decomposition
- separate workspace surface

But the codebase is still transitional:
- `mentions_core/` + `agents/mentions/` + `library/` coexist
- query -> event/market resolution is weak
- workflow policy is not strongly separated from orchestration
- output quality is below investor-grade memo usefulness
- several components are replaceable in practice, but not formalized as modules

The goal is to turn `mentions` into a **modular market-analysis runtime** whose parts can be swapped, tested, reused, embedded, or removed cleanly.

---

## 2. Jordan patterns to reuse

Jordan provides several good architectural ideas worth porting:

1. **Thin orchestrator, richer modules**
   - orchestrator coordinates, modules think
2. **Protocol-style contracts**
   - structural interfaces make components replaceable
3. **Central config/path layer**
   - shared paths/settings, no random path hardcoding
4. **Separate runtime layers**
   - retrieval, frame selection, synthesis, rendering, policy
5. **State-aware policy modules**
   - boundary behavior and adaptive policy should not live inside rendering glue

Mentions should adopt the same discipline, but with market-analysis modules instead of psychological ones.

---

## 3. Target architecture

Mentions should be organized into four layers.

### Layer A. Interfaces
External entry surfaces only.

Suggested modules:
- `mentions_core.cli`
- `mentions_core.scheduler`
- `agents.mentions.pack`
- OpenClaw prompt bridge
- Telegram/render adapters

These should not contain domain reasoning.

### Layer B. Orchestrators
Thin composition layer only.

Suggested orchestrators:
- `query_orchestrator`
- `url_orchestrator`
- `scan_orchestrator`
- `prompt_orchestrator`

Responsibilities:
- call modules in order
- pass typed bundles
- apply workflow policy
- choose renderer/output path

They should **not** own domain heuristics directly.

### Layer C. Domain modules
These are the real replaceable units.

#### 1. `market_resolution`
Input:
- free-text query or URL metadata

Output:
- candidate events
- candidate markets
- resolved primary market
- confidence
- resolution rationale

Responsibilities:
- entity extraction
- event alias matching
- speaker/event parsing
- candidate ranking
- disambiguation

This is the highest-priority missing module.

#### 2. `market_data`
Input:
- ticker / event / market ids

Output:
- normalized market snapshot
- orderbook
- history
- metadata

Responsibilities:
- Kalshi API client
- schema normalization
- fallback handling
- market history retrieval
- top movers / search helpers

#### 3. `news_context`
Input:
- event/query/category

Output:
- context bundle
- freshness status
- sufficiency score
- path classification (direct / weak / late)

Responsibilities:
- live provider calls
- cache fallback
- relevance filtering
- event-context assembly

#### 4. `transcript_intelligence`
Input:
- speaker / event / query

Output:
- transcript hits
- speaker-history summary
- extracted tendencies / evidence

Responsibilities:
- ingest
- chunking
- FTS/semantic retrieval
- speaker evidence selection

#### 5. `analysis_engine`
Input:
- resolved market
- market data
- news context
- transcript evidence

Output:
- structured thesis bundle

Responsibilities:
- signal vs noise
- regime / difficulty
- speaker/event logic
- fair value reasoning
- crowd-mistake reasoning
- execution / skip logic
- invalidation logic

#### 6. `workflow_policy`
Input:
- request type
- available evidence
- freshness
- confidence

Output:
- allow / partial / block / clarify
- output mode
- quality gate rationale

Responsibilities:
- enforce “no full memo without fresh context”
- decide when to ask for clarification
- decide when to downgrade to partial output
- decide when to skip analysis entirely

#### 7. `memo_renderer`
Input:
- thesis bundle
- workflow decision
- target surface

Output:
- telegram brief
- investor memo
- dashboard note
- structured JSON

Responsibilities:
- output formatting
- wording enforcement
- strike label formatting
- user-approved phrasing discipline

#### 8. `scheduler_scan`
Input:
- scan policy
- watch universe

Output:
- ranked candidate markets
- scan notes
- dashboard artifacts

Responsibilities:
- autonomous scan logic
- watchlist generation
- alert candidate generation

### Layer D. Providers / adapters
Replaceable provider-specific implementations.

Suggested providers:
- `providers.kalshi`
- `providers.newsapi`
- `providers.transcript_db`
- `providers.cache`

These should be dumb adapters, not business logic owners.

---

## 4. Suggested contract model

Mentions should adopt protocol-style contracts similar to Jordan.

Suggested contract file:
- `agents/mentions/contracts.py`

Suggested protocols:
- `MarketResolver`
- `MarketDataProvider`
- `NewsContextProvider`
- `TranscriptRetriever`
- `AnalysisEngine`
- `WorkflowPolicy`
- `MemoRenderer`
- `ScanEngine`

Suggested data objects:
- `MarketQuery`
- `ResolvedMarket`
- `EvidenceBundle`
- `AnalysisBundle`
- `WorkflowDecision`
- `RenderedOutput`

This matters because modularity should be defined by contracts, not just folders.

---

## 5. Proposed target directory layout

```text
mentions_core/
  cli.py
  scheduler/
  base/

agents/mentions/
  contracts.py
  config.py
  pack.py

  orchestrators/
    query.py
    url.py
    prompt.py
    scan.py

  modules/
    market_resolution/
    market_data/
    news_context/
    transcript_intelligence/
    analysis_engine/
    workflow_policy/
    memo_renderer/
    scheduler_scan/

  providers/
    kalshi/
    newsapi/
    transcript_db/
    cache/

  capabilities/
    analysis/
    transcripts/
    news_context/
    wording/

  assets/
    thresholds.json
    market_categories.json
    source_profiles.json
    analysis_modes.json
```

Notes:
- `runtime/`, `analysis/`, `fetch/` should gradually collapse into `orchestrators/`, `modules/`, and `providers/`
- `library/` remains compatibility-only until fully removable

---

## 6. Migration strategy

Do not do a giant rewrite. Move in controlled phases.

### Phase A. Foundation cleanup
Goal: stabilize runtime and define module boundaries.

Tasks:
1. Freeze `library/` as compatibility-only
2. Introduce `agents/mentions/contracts.py`
3. Add central module registry / wiring layer
4. Make `pytest` and dev dependencies actually runnable in environment
5. Add smoke tests for:
   - pack registration
   - query path
   - URL path
   - news context path
   - transcript search path

Deliverable:
- stable base for refactor

### Phase B. Extract `market_resolution`
Goal: fix the most important functional weakness.

Tasks:
1. Create dedicated `modules/market_resolution/`
2. Move query/url candidate ranking logic there
3. Add:
   - entity extraction
   - speaker/event parsing
   - candidate scoring
   - exact/alias matching
   - relevance penalties
4. Add real-case regressions:
   - Trump / Iran
   - Powell / rates
   - named mention markets
   - query vs URL parity

Deliverable:
- query -> correct market matching becomes reliable

### Phase C. Extract `workflow_policy` and `memo_renderer`
Goal: separate “what is allowed” from “how it is said”.

Tasks:
1. Create `modules/workflow_policy/`
2. Encode:
   - require fresh context for full memo
   - partial mode rules
   - low-confidence downgrade rules
3. Create `modules/memo_renderer/`
4. Add outputs for:
   - telegram brief
   - structured investor memo
   - JSON bundle
5. Enforce wording DB here, not ad hoc across the stack

Deliverable:
- clean quality gates and cleaner outputs

### Phase D. Extract and harden `analysis_engine`
Goal: make the actual thesis logic better and more reusable.

Tasks:
1. Consolidate existing analysis logic into a formal module
2. Separate:
   - market summary
   - signal assessment
   - regime/difficulty
   - fair value reasoning
   - execution/sizing
   - invalidation
3. Add explicit output schema
4. Add regression cases for trading usefulness, not just shape

Deliverable:
- analysis engine becomes replaceable and testable

### Phase E. Provider hardening
Goal: ensure adapters are reliable.

Tasks:
1. Harden Kalshi provider
2. Normalize schema assumptions
3. Better error taxonomy
4. Better news cache/provider abstraction
5. Better transcript-provider selection and scoring

Deliverable:
- provider layer becomes stable and boring

### Phase F. Autonomous scan only after core quality
Goal: avoid automating weak judgment.

Tasks:
1. Move scan logic to `scheduler_scan`
2. Use same market_resolution + workflow_policy + renderer stack
3. Produce dashboard/watchlist artifacts only after query path is trustworthy

Deliverable:
- autonomous mode that doesn’t amplify garbage

---

## 7. Priority order

Recommended execution order:

1. **Phase A** — foundation cleanup
2. **Phase B** — market resolution
3. **Phase C** — workflow policy + memo renderer
4. **Phase D** — analysis engine
5. **Phase E** — provider hardening
6. **Phase F** — scheduler/autonomous

This order matters because the current biggest practical failures are:
- wrong market selection
- weak output gating
- generic output quality

---

## 8. Non-goals

Do not spend time first on:
- cosmetic renames without contract changes
- fancy dashboard work before query correctness
- autonomous scans before event resolution is reliable
- more compatibility shims unless strictly needed

---

## 9. Definition of success

Mentions modular refactor is successful when:

1. Query -> correct market resolution works on core real cases
2. Full memo cannot be generated without sufficient fresh context
3. Output feels like a trading memo, not a generic analytics paragraph
4. Major modules can be replaced independently
5. `library/` is thin enough to ignore, or removable entirely
6. Scheduler uses the same modules as interactive analysis instead of a separate brain

---

## 10. Immediate recommendation

Start with:
- Phase A foundation cleanup
- then Phase B market resolution extraction immediately

Reason:
market resolution is currently the largest real-world failure point, and all later quality work depends on it.
