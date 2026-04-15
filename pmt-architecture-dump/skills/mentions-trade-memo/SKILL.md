---
name: mentions-trade-memo
description: "Build a full event-driven mention-market memo by chaining context analysis and trade analysis in the correct order. Use when the user wants a complete market breakdown, full event memo, setup plus trade call, or a one-shot answer to prompts like: break down this market, how would you trade this strike, give me the setup and trade, do a full mention-market analysis, first explain the event then tell me how to trade it, or give me one final memo instead of separate context and trade steps. This skill should do context first, then pricing/execution second, then return one unified memo."
---

# Mentions Trade Memo

Use this as a thin orchestration skill.

## Core rule

Do not jump straight into price or direction.
Always:
1. build event/news context first
2. then evaluate the trade
3. then return one unified memo

## Mandatory enforcement

Before giving any final lean, fair value, or execution opinion, perform a fresh context pass using current information sources.
That means:
- inspect market/event structure
- gather fresh event/news context
- only then move into trade analysis

If fresh context was **not** gathered, do **not** present the output as a full memo.
Instead, explicitly label it as:
- `partial read`
- `market-structure-only read`
- or `needs fresh context before trade call`

Do not silently skip the context stage.

## Workflow

### Stage 1 — Context
Use the logic of `mentions-news-context`.
Determine:
- what the event actually is
- what kind of setup / archetype this is
- the main narrative
- recent setup changes
- direct paths vs weak adjacency paths
- late paths / Q&A paths
- whether Q&A / venue / format matter
- what may already be priced in
- whether setup shorthand is likely being over-read

This stage should use fresh external context when available, not just priors and market structure.

### Stage 2 — Trade
Use the logic of `pmt-mentions-trader`.
Determine:
- market archetype / event format / speaker relevance
- main pricing signal or crowd mistake
- fair value range
- lean: yes / no / no-trade
- execution plan
- sizing posture
- main risks
- invalidation / no-trade condition

### Stage 3 — Unified memo
Merge both layers into one final answer.
The final memo should feel like one stack:
context -> path map -> trade quality -> execution -> risk.

## Output format

Use the structured report format from `references/memo-template-v2-structured.md`.

Mandatory report sections:
- **Название события** (human readable title)
- **Тема / место / формат / предполагаемая длительность**
- **Гости / Q&A**
- **Уровень рынка** (легкий / средний / тяжелый)
- **Market regime** (Y fest / N fest / mixed)
- **Core read**
- **Basket breakdown** with basket thesis / why / win condition / invalidation
- **Per-strike lines** with current price and FV
- **Final execution view**

Before writing the final prose, consult `/root/.openclaw/workspace/wording/markets_wording_db.json` and use it as the wording source of truth.

## Mandatory rules

- If context is weak, say so before giving any lean
- If setup is unclear, prefer no-trade over fake precision
- Do not collapse event context into price talk too early
- Distinguish direct path from adjacency path explicitly
- Distinguish weak path from late path explicitly when that matters
- Name the main pricing signal explicitly in the final memo, not just implicitly in the reasoning
- Name the main crowd mistake explicitly in the final memo
- Include the most relevant phase-logic row when one materially changes the path
- Include the closest useful case when KB retrieval finds one that materially sharpens the read
- Every strike mentioned must include current price and FV price
- Every basket must include a win condition and invalidation
- Add strike-level invalidation or win condition only when needed
- Explicitly classify the event as Y fest / N fest / mixed
- Explicitly classify market difficulty as легкий / средний / тяжелый
- Use exact wording-db replacements where available instead of ad-lib paraphrases
- Keep the final memo tight enough to fit in one chat message when possible
- If no fresh context was gathered, the answer must be labeled partial rather than full-scope

## Reference loading

Read as needed:
- `references/memo-template.md` when shaping the final combined answer
- `references/workflow-notes.md` when deciding ordering, compression, or how much context vs trade detail to keep
- then use the local skills `mentions-news-context` and `pmt-mentions-trader` as the two domain layers

## Style rules

- Be concise but not shallow
- Avoid repeated caveats
- Use no-trade freely when edge is weak
- Final answer should feel like one coherent memo, not two stapled analyses
