# Workflow Notes

## Purpose
This skill is not a third source of domain knowledge.
It is a router/orchestrator.

## Correct order
1. Build setup/context first
2. Map direct / weak / late paths
3. Only then analyze fair value, execution, and sizing
4. Return one combined memo

## Failure modes to avoid
- giving a trade call before establishing the setup
- collapsing direct paths and adjacency paths into one bucket
- failing to separate weak paths from late but still live paths
- repeating the same caveat in both context and trade sections
- returning two separate mini-answers instead of one integrated memo
- acting as if open/closed setup shorthand already is the analysis

## If the user gives only a market link or ticker
- infer the event from market data
- reconstruct likely event structure
- then do the full memo

## If the user gives event context explicitly
- use it
- do not waste space re-deriving obvious context
- focus more on pricing/execution
- but still name the event format, main path map, and key crowd mistake if those drive the trade read

## Report format rules
- Use `memo-template-v2-structured.md` as the default report shape.
- Consult `/root/.openclaw/workspace/wording/markets_wording_db.json` before writing final prose.
- Start with a human-readable event title, not raw shorthand.
- Include one compact line for topic / venue / format / expected duration.
- Explicitly state whether guests are likely to speak and whether Q&A is likely.
- Classify market difficulty as легкий / средний / тяжелый.
- Classify regime as Y fest / N fest / mixed.
- Organize the trade view by baskets.
- Every basket must include:
  - thesis
  - why
  - win condition
  - invalidation
- Every strike mentioned must include current price and FV price.
- Add strike-level invalidation or win condition only when it materially helps.
