---
name: mentions-news-context
description: "Build a fresh news/context brief for event-driven mention markets before pricing the trade. Use when analyzing Kalshi mention contracts, speech/briefing/interview/earnings-call markets, or any event-driven word market where current headlines, venue, guest mix, schedule changes, Q&A odds, and topic drift matter. Trigger on requests like: what is the setup here, what changed in the last 24-72h, what is the main narrative, which strikes are direct vs adjacency, what is likely already priced, what should I know before trading this mention event, or give me the news context before the trade."
---

# Mentions News Context

Build the event context before the trade memo.

## Default workflow

1. Identify the event and format.
   - Speaker
   - Event type
   - Venue / format
   - Scheduled timing
   - Whether Q&A is likely
   - Whether this is a recurring/modelable format or a thin-history one-off

2. Classify the setup archetype.
   - Decide whether this is a Trump live Q&A setup, briefing-style setup, recurring announcer-type setup, named policy event, performer/field event, or another context family.
   - Do not do price work here, but do identify what kind of context model should be used.

3. Gather fresh context.
   - Pull the last 24h of directly relevant news first.
   - Expand to 72h only when the narrative is clearly multi-day.
   - Prefer official/event-linked reporting over commentary.

4. Separate paths.
   - Main path: directly live topics
   - Secondary path: plausible but not central topics
   - Weak path: adjacency / vibes / forced linkage
   - Late path: topics that are mainly live through Q&A / detours / sequence changes
   - For Trump press conferences, Brady Briefing Room press events, and briefing-style political availabilities where reporters are live, the late-path bucket is mandatory unless there is explicit evidence Q&A is dead.

5. Highlight setup shifts and crowd traps.
   - Guest changes
   - Topic changes
   - New escalation/de-escalation
   - Schedule/venue changes
   - Emerging Q&A vectors
   - Setup-label distortions (open press / closed press / room shorthand)
   - Cases where the market may be over-reading adjacency instead of direct path

6. End with a context memo, not a trade call.
   - This skill prepares the setup.
   - Use `pmt-mentions-trader` after this when the user needs pricing / execution.
   - If the user explicitly wants both, do context first, then switch into trade analysis.

## Mandatory checks

Before finishing, answer these:
- What exactly is the event?
- What is the event format?
- What kind of setup/archetype is this?
- What is the main narrative?
- What changed in the last 24-72h?
- Which topics are direct paths?
- Which topics are weak adjacency paths?
- Which topics are mainly late-path / Q&A-path topics?
- Is Q&A likely and does it matter?
- If this is a Trump press conference / briefing-room style event, did you explicitly map the late-path bucket?
- What might already be priced?
- What remains unknown?

## Output format

Use this order:
- **Event:** event type, venue, format, timing
- **Main narrative:** 1-3 core themes
- **Fresh changes:** what changed recently
- **Direct paths:** topics/strikes naturally live
- **Weak paths:** adjacency topics likely being over-read
- **Q&A watch:** whether late-question paths matter
- **Probably priced in:** what the market is likely already paying for
- **Unknowns:** unresolved context risks

## Reference loading

Read as needed:
- `references/context-framework.md` when separating direct path from adjacency path
- `references/source-priority.md` when deciding which reporting matters and which headlines are probably noise
- `references/output-template.md` when shaping the final context brief
- `references/examples.md` when you need concrete event-context analogies or calibration examples

## Style rules

- Be concise
- Prefer event structure over headline excitement
- Distinguish direct path from adjacency path
- Do not jump into price/execution unless explicitly asked
- Surface uncertainty clearly
