# PMT Playbook v1

Distilled from the current `pmt_trader_knowledge.db` corpus.

## Core idea

In mention markets, edge comes less from "guessing the right outcome" and more from:
- entering at the right price
- reacting faster to setup changes
- respecting live liquidity dynamics
- avoiding bad execution and bad chase behavior

## Section 1 — Price first, thesis second

### 1.1 Price matters more than binary intuition
Do not think in terms of "will it happen?" alone.
Think in terms of:
- what is fair value now?
- what price am I actually getting?
- is this still the same trade after the market moved?

### 1.2 Same side, different price = different trade
A strike bought at 21 cents is not the same trade at 34 cents.
A yes bought at 39 cents is not the same trade at 75 cents.
Do not copy a side; copy a setup + price threshold.

### 1.3 Overbought can still be directionally plausible
A topic can be genuinely live and still overpriced.
Do not confuse:
- plausible mention
with
- positive EV at current odds

## Section 2 — Execution is alpha

### 2.1 Limit orders are default
Use limit orders whenever possible.
Reason:
- better fills
- less spread donation
- maker fee advantage
- ability to rest bids where panic sellers hit you

### 2.2 Blind market buying is usually bad
In thin mention markets, market-style execution is often just paying tax.
You lose edge through:
- spread
- fees
- poor timing

### 2.3 Scale in, don’t telegraph size
Prefer smaller layered orders to one giant visible order.
Why:
- easier fills
- less penny-jumping
- less signaling to other participants
- better average entry control

## Section 3 — Reprice the event, not just the strike

### 3.1 Setup changes can invalidate the whole pre-market surface
If new info changes the event frame before remarks begin, reprice immediately.
Examples:
- surprise guest
- newly revealed event focus
- external news tied to a strike
- changed venue / changed format / likely no Q&A

### 3.2 Venue and format matter
Questions to ask before the event starts:
- where is this happening?
- is Q&A likely?
- is this a pure ceremony, signing, bilateral, briefing, rally?
- what historically gets mentioned in this exact format?

### 3.3 Sparse historicals reduce confidence
If you do not have enough comparable events for a speaker or format, price with more humility.
Do not pretend rare event types are as modelable as repeat formats.

## Section 4 — Timing is a real edge

### 4.1 Often better to wait closer to start
In many live event markets, late pre-event entry is superior because:
- information quality improves
- context is clearer
- market still may not be fully repriced
- flow near start can still give fills

### 4.2 Don’t assume early entry is automatically better
Sometimes early entry gets you price.
Sometimes it just gets you stale exposure while the setup evolves against you.

### 4.3 Live sequence matters
In some event markets, the path matters:
- almost-triggered
- partially triggered
- likely to dispute
- likely to cleanly resolve

This creates temporary opportunity, but only if you understand resolution risk.

## Section 5 — Live liquidity rules

### 5.1 Liquidity dries up at go-live
As the event begins:
- spreads widen
- stale orders become dangerous
- books get thinner
- order risk jumps sharply

### 5.2 Do not leave lazy stale orders up
If a word can hit immediately, any resting order can get picked off.
Go-live order risk is different from normal passive quoting risk.

### 5.3 Wide spreads are information
A very wide live spread is not just inconvenience.
It often tells you:
- participants are unsure
- risk of instantaneous repricing is high
- passive liquidity is pulling back

## Section 6 — Relative value thinking

### 6.1 Compare neighboring strikes
Good pricing often comes from asking:
- if A happens, does B almost have to happen?
- can A happen without B?
- is the spread between them justified?

### 6.2 Use similar markets as anchors
Sometimes the easiest edge is not inside one market, but between related markets.
Examples:
- aggregate market vs component markets
- one mention strike vs logically subordinate strike
- parallel markets pricing the same theme differently

## Section 7 — Anti-patterns

### 7.1 Chasing steam
Just because a move was right does not mean the new price is good.

### 7.2 Copying entries without matching fills
Following the side without the fill is fake imitation.

### 7.3 Blind market orders in thin books
Execution leak can kill the edge before the event even starts.

### 7.4 Treating partial trigger as full resolution
Near-hit and clean-hit are different.
Disputes exist.

### 7.5 Ignoring format/venue/context
The same speaker in a different setup is not the same market.

## Section 8 — Practical checklist before entering a mention market

Ask:
1. What is the actual event format?
2. Is Q&A likely?
3. What changed in the setup during the last hour?
4. What is fair value versus current price?
5. Am I entering because of edge, or because I’m late and emotional?
6. Can I use a limit order instead?
7. If this starts right now, can my order get picked off?
8. Is this a clean trigger market or a dispute-prone market?
9. Am I reading one strike in isolation when I should compare related strikes?
10. If someone else posted this trade earlier, am I actually getting the same trade?

## Section 9 — What this playbook still lacks

Current v1 is strongest on:
- entry price logic
- execution
- live liquidity
- setup repricing

It still needs more extraction on:
- mentions-specific topic clustering
- speaker-specific tendencies
- stronger casebook for dispute-prone triggers
- post-event resolution/risk lessons
