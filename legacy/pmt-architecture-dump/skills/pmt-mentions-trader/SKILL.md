---
name: pmt-mentions-trader
description: "Evaluate Kalshi-style or similar mention markets with a PMT-style framework focused on price, event setup, timing, Q&A path dependence, live execution, and dispute risk. Use for requests like: analyze this mention market, price this strike, should I buy yes/no here, is this overbought, should I chase this, is this a good entry, what is fair value, how would PMT trade this, is this a no-trade, or how should I execute this live speech / briefing / interview / announcer market. This skill is specifically for event-driven word / mention contracts, not generic macro or sports handicapping."
---

# PMT Mentions Trader

Evaluate the trade, not just the outcome.

## Default workflow

1. Classify the market archetype.
   - Identify whether this is a recurring announcer mention market, Trump live Q&A mention market, briefing-style market, named policy announcement, performer/field market, bond-like high-probability market, or another event-driven mention setup.
   - Do not jump straight to fair value before deciding what kind of market this actually is.

2. Classify the event format.
   - Identify whether this is a briefing, rally, EO signing, bilateral, interview, earnings call, sports broadcast, entertainment live event, or another format.
   - Determine whether prepared remarks and Q&A are separate distributions.
   - Note venue/format features that change mention paths.

3. Rebuild the setup and speaker path.
   - Check for guest changes, topic shifts, external news, schedule drift, room changes, setup-label distortions, and no-Q&A conditions.
   - Ask whether the market is over-anchoring on shorthand like open press / closed press.
   - If speaker behavior matters, identify whether this is a vibes-heavy speaker, a recurring/modelable speaker, or a thin-history speaker where confidence should be discounted.

4. Identify pricing signals and crowd mistakes.
   - Ask what the market is most likely getting wrong: pooled historicals, setup-label overreaction, copy-trader premium, field misread, thin-history fake precision, phase-blind pricing, direct-name underpricing, or another crowd error.
   - Separate true signal from crowd shorthand.

5. Retrieve relevant KB rows.
   - Before final pricing, pull the most relevant live rows from `/root/.openclaw/workspace/pmt_trader_knowledge.db`.
   - Use `/root/.openclaw/workspace/transcripts/query_kb_for_market.py` with the current event title, speaker, format, archetype, and a short freeform setup summary.
   - Pull at least these bundles when available: pricing signals, crowd mistakes, phase logic, execution patterns, and closest decision cases.
   - Prefer a small relevant bundle over a long dump.
   - If retrieval returns weak or generic matches, say so and fall back to the references and your own event reasoning.

6. Price the strike.
   - Separate plausibility from EV.
   - Estimate rough fair value.
   - Compare against neighboring strikes, related markets, similar archetypes, relevant historical comparables, and the retrieved KB bundle.
   - If the path only becomes live in Q&A or late sequence, price that explicitly instead of treating the event as one blob.

7. Decide execution and sizing.
   - Prefer limit orders by default.
   - Use taker execution only if edge is decaying faster than passive fills are likely.
   - Adjust size for setup quality, execution quality, bankroll opportunity cost, dispute risk, and whether this is a recurring edge or a thin-history one-off.
   - If fills are likely to be bad, reduce size even if your paper fair value looks strong.

8. Reject bad trades aggressively.
   - Say no-trade when price is bad, setup is unclear, crowd edge is already gone, execution is weak, or the contract is too dispute-sensitive.
   - Flag anti-patterns, crowd mistakes, dispute patterns, and live-trading tells explicitly when relevant.

## Mandatory checks

Before recommending a trade, answer these:
- What is the market archetype?
- What is the event format?
- Is Q&A likely, and does it materially change the path?
- Did the setup change recently?
- Does speaker behavior matter here?
- What is the main pricing signal?
- What is the main crowd mistake?
- What relevant phase logic applies?
- What is the closest useful case?
- What is rough fair value?
- What makes the current price good or bad?
- What is the execution plan?
- What is the sizing plan?
- What is the main dispute or live-path risk?
- What would make this a no-trade?

## Output format

Use this order exactly:

- **Setup:** event type, venue/format, Q&A odds, recent setup changes
- **Lean:** yes / no / no-trade
- **Fair value:** rough range only
- **Main pricing signal:** one line
- **Main crowd mistake:** one line
- **Relevant phase logic:** one line
- **Closest case:** one line
- **Why:** 2-5 bullets
- **Execution:** limit / taker / wait / size-in / avoid
- **Main risks:** 1-3 bullets
- **Invalidation / no-trade condition:** what would make the setup unplayable

If confidence is weak, say **no-trade** instead of forcing a side.

## Reference loading

Read as needed:
- `references/playbook.md` for the distilled framework and v2 reasoning order
- `references/market-archetypes.md` when the first question is what kind of market this is
- `references/event-types.md` when event family / venue / Q&A structure is doing most of the work
- `references/speaker-profiles.md` when speaker behavior or recurrence is a core variable
- `references/pricing-signals.md` when diagnosing where the market is wrong
- `references/crowd-mistakes.md` when the edge depends on a recurring crowd / order-flow error
- `references/live-trading-tells.md` when orderbook behavior or event sequence itself is informative
- `references/heuristics.md` when the question is mostly about price, entry, execution, fair value, trade structure, or bankroll discipline
- `references/anti-patterns.md` when checking whether the setup is actually a bad trade, bad execution, bad sizing, or fake edge
- `references/cases.md` when you need concrete analogies, precedent setups, or example trades
- `references/output-examples.md` when shaping the final answer format or calibrating no-trade vs yes/no style output

When useful, explicitly reason through this order:
1. archetype
2. format
3. speaker / recurrence / thin-history status
4. KB retrieval bundle
5. pricing signal
6. crowd mistake
7. phase logic
8. closest case
9. fair value
10. execution
11. sizing
12. dispute/live-path risk

## Style rules

- Be direct
- Prefer rough probability bands over fake precision
- Distinguish thesis quality from price quality
- Mention execution explicitly
- Prefer no-trade over weak edge
