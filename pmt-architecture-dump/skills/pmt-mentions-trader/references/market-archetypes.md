# Market Archetypes

Use this file when the first question is not “what is fair value?” but “what kind of market is this?”

## Why archetypes matter
The same pricing logic does not transfer cleanly across all mention markets.
A Trump live Q&A market, a recurring announcer market, a performer field market, and a bond-like clarification market may all be “event-driven,” but they break for different reasons.

Always classify the archetype before committing to fair value.

## 1. Recurring announcer mentions
Typical features:
- repeated product
- strong historical comparables
- segmentation matters more than pooled averages
- broadcaster / crew / network / game state can dominate

Good questions:
- Is the market using the right historical subset?
- Does booth or network materially change hit rate?
- Is this a dead-game / garbage-time chatter environment?

Typical errors:
- trusting all-games averages
- ignoring network/booth effects
- treating late-game drift as pure variance

## 2. Trump live Q&A mention markets
Typical features:
- speaker is nonlinear
- current-events regime matters a lot
- prepared remarks and Q&A are different distributions
- setup labels often move the market too much

Good questions:
- Is the word path mainly opening remarks or Q&A?
- Is the market overweighting open press / closed press shorthand?
- Is the event still live for late detours?

Typical errors:
- phase-blind pricing
- killing late-path words too early
- overfitting historical transcript counts

## 3. Briefing-style recurring political markets
Typical features:
- recurring spokesperson / recurring room format
- topic clustering from last 24-72h matters a lot
- Q&A often drives late or reactive mentions

Good questions:
- Is this defensive / reactive / celebratory?
- Is the market blobbing opening remarks and Q&A together?
- Are current topic clusters stronger than older comparables?

Typical errors:
- treating every briefing as the same
- ignoring briefing posture
- failing to separate speaker habit from live question flow

## 4. Rare-speaker or thin-history mention markets
Typical features:
- weak or sparse comparable set
- fake precision is common
- intuition often outruns evidence

Good questions:
- Is there enough recurrence to model this tightly?
- Should size be discounted because uncertainty is structurally wider?
- Is the market pretending this is a solved recurring setup?

Typical errors:
- forced precision
- oversizing
- overtrusting tiny samples

## 5. Name-linked policy announcement markets
Typical features:
- one or more names/entities are directly central to the event
- generic theme words may be weaker than direct name paths
- counterparties often deserve repricing above vague adjacency

Good questions:
- Which names are directly on the path?
- Are long/awkward names still somewhat speech-friction-heavy?
- Is the market underpricing the most direct explicit name?

Typical errors:
- treating all related names equally
- confusing thematic relevance with direct mention path

## 6. Performer / field markets
Typical features:
- multi-name distribution
- informed flow on a few names reprices the rest of the field
- logistics, production, and ambiguity matter

Good questions:
- If these names are getting pumped, what does that imply for everyone else?
- Are logistics signal or noisy signal?
- Does the resolution rule allow multiple live paths or not?

Typical errors:
- treating each name independently
- overreacting to noisy production clues
- ignoring field conditionality

## 7. High-probability bond-like markets
Typical features:
- price often in 90-99 range
- real question is not “likely?” but “what is the last few percent?”
- rules / clarification / tail risk dominate

Good questions:
- Is this a real bond or a false bond?
- What exactly lives in the last 1-5%?
- Is the return worth the capital lockup?

Typical errors:
- calling every high-probability market a bond
- ignoring contract scope / clarification risk
- oversizing because win-rate feels high

## 8. Manual orderbook / execution-driven markets
Typical features:
- fill quality matters as much as fair value
- queue position, spread, and UI friction shape realized EV
- manual speed can be a real edge

Good questions:
- Is this a market where maker discipline matters more than directional genius?
- Are you actually getting good fills or just imagining paper EV?
- Is the book behavior itself giving information?

Typical errors:
- confusing model quality with execution quality
- overpaying because of FOMO
- failing to react to adverse-selection tells
