# Event Types

Use this file when the main edge question depends on event family rather than just strike price.

Before using any event-type note, classify both:
- the **market archetype**
- the **event format**

Those are not always the same thing.
Example:
- archetype = Trump live Q&A mention market
- format = bilateral / open-press availability

Or:
- archetype = recurring announcer mention market
- format = live sports broadcast

## Press briefings
Typical features:
- recurring format
- known spokesperson habits matter
- Q&A often drives a large share of late mentions
- opening remarks and Q&A should be modeled separately

Watch for:
- topic clusters from the last 24-72h
- whether briefing is defensive, celebratory, or reactive
- whether the market is pricing the open and Q&A as one blob
- whether crowd shorthand about the room/setup is overwhelming the real event tree

## EO signings
Typical features:
- can begin topic-focused
- can drift if Trump goes off-script
- Q&A is highly format-dependent, not automatic

Watch for:
- whether the signing topic overlaps with other active headlines
- whether a fresh grievance/news item is likely to hijack the speech
- whether the event setup historically includes side remarks or press questions
- whether setup labels are causing crowd overreaction relative to actual detour risk

## Bilaterals / leader meetings
Typical features:
- topic path is strongly shaped by the guest and current geopolitical agenda
- closed-press vs open-press matters a lot
- headline topics can dominate even when the ceremonial reason is different

Watch for:
- whether this is a photo-op, sit-down, or real press availability
- whether there is a clean opening statement only, or actual press interaction
- whether the market is overpricing generic hot-button topics without a real path
- whether setup shorthand is collapsing a still-live late path too early

## Rallies / campaign speeches
Typical features:
- broader topic surface
- more rhetorical drift
- more room for repeated slogans and recurring talking points

Watch for:
- crowd/location-specific themes
- whether current news flow is likely to hijack the rally
- whether the market overstates novelty when the speaker is likely to repeat standard lines

## Interviews / podcasts / TV hits
Typical features:
- host matters a lot
- interviewer agenda shapes topic path
- format may create more direct question-dependent mentions than speeches do

Watch for:
- host topic preferences
- whether questions are adversarial, softball, or promo-focused
- whether a topic only becomes live if explicitly asked

## Earnings calls / prepared remarks + Q&A
Typical features:
- prepared remarks and Q&A are different distributions
- speaker-specific word habits matter
- management may repeat house phrases or avoid certain loaded words

Watch for:
- whether the target word historically comes from the CEO, CFO, or analyst Q&A
- whether the market overreacts to the prepared remarks phase
- whether the word path is mostly post-prepared-remarks

## Sports announcer mention markets
Typical features:
- highly path-dependent
- commentary crew, broadcaster, and game script all matter
- good markets can often be modeled with event-family data

Watch for:
- broadcast network / crew differences
- whether game state or team tendencies make the strike more likely
- whether the market is using the wrong comparables
- whether late-game / garbage-time drift changes the language mix

## Entertainment / partial-trigger markets
Typical features:
- live sequence matters more than static probabilities
- resolution/dispute risk can dominate
- temporary mispricings appear around partial progress toward a trigger

Watch for:
- whether the trigger is clean or ambiguous
- whether the market is pricing “almost happened” as “already happened”
- whether similar disputes exist in historical examples
- whether production/logistics clues are being priced as certainty instead of noisy signal
