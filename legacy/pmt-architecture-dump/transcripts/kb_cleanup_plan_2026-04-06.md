# KB Cleanup Plan — 2026-04-06

Цель: не удалять rows вслепую, а сначала разложить текущие смысловые пересечения на canonical / near-duplicate / keep-parallel.

---

## Principles

### 1. One abstract idea, many cases
Если несколько rows выражают одну и ту же абстрактную мысль, в базе должен остаться **один canonical principle row**, а остальные лучше:
- либо превратить в evidence/case role,
- либо пометить как near-duplicate,
- либо оставить только если они реально покрывают более узкий отдельный угол.

### 2. Cases are cheaper than extra principles
Если новая информация — это скорее пример старой мысли, чем новая мысль, оформлять её как `decision_case`, а не как новую principle-row.

### 3. Do not hard-delete yet
На первом проходе ничего не удалять физически. Сначала сформировать merge map, потом уже решать, что:
- merge mentally / keep as-is,
- deprecate,
- archive,
- or delete.

---

# Merge Groups

## Group A — Segmentation / pooled history family

### Canonical winner
- `Raw history without format segmentation`

### Near-duplicates / overlapping rows
- `trusting-pooled-historicals`
- `Using pooled historical hit rates for recurring mention markets without segmenting by format, announcer, network, or event context.`

### Why merge
Все три rows выражают одну и ту же core idea:
исторические hit rates без корректной сегментации по реальному market format дают плохой fair value.

### Recommendation
- Keep canonical: `Raw history without format segmentation`
- Keep one older row only if нужен более mentions-specific wording
- Mark the rest as near-duplicate candidates

### Related cases
- `Inch sample-selection failure`
- `Monday Night Football Inch scorebug edge`
- `Next Gen Stats integration shock`

---

## Group B — Phase modeling family

### Canonical winner
- `Prepared remarks and Q&A are separate pricing regimes`

### Keep-parallel rows
- `prepared-remarks`
- `q-and-a-window`

### Near-duplicate / overlapping row
- `model-the-event-in-phases`

### Why merge
`model-the-event-in-phases` и `Prepared remarks and Q&A are separate pricing regimes` — это почти один и тот же abstraction layer.
При этом `prepared-remarks` и `q-and-a-window` полезны как более granular phase rows, их не надо схлопывать автоматически.

### Recommendation
- Keep canonical abstract row: `Prepared remarks and Q&A are separate pricing regimes`
- Keep granular rows: `prepared-remarks`, `q-and-a-window`
- Mark `model-the-event-in-phases` as merge-later candidate

### Related rows
- `Fresh breaking news can collapse Q&A width`

### Related cases
- `Meet the Press promo invalidated by fresh Venezuela shock`

---

## Group C — Blowout / garbage-time yap family

### Canonical winner
- `Blowout late-game yap expansion`

### Near-duplicate / overlapping row
- `garbage-time-yap`

### Why merge
Обе rows описывают один и тот же late-game regime shift:
в неcompetitive фазе announcers начинают больше заполнять эфир случайным разговором.

### Recommendation
- Keep canonical: `Blowout late-game yap expansion`
- Mark `garbage-time-yap` as near-duplicate candidate

### Related cases
- Can later add more announcer blowout cases if corpus grows

---

## Group D — Blind tailing / copy-trading family

### Canonical winner
- `Blind tailing without understanding thesis, fair value, and exit conditions usually turns a good originator trade into a worse follower trade.`

### Keep-parallel candidate
- `Copying someone else's position without matching their entry price or timing.`

### Near-duplicate / overlapping row
- `Blindly tailing a sharp trader after the price has moved, without understanding why the trade was good at the original entry.`

### Why merge
Здесь есть одна общая abstract idea:
фолловер почти всегда получает худший трейд, чем originator.

Но узкий angle про **entry price / timing degradation** можно оставить отдельно, если хочется сохранить tactical distinction.

### Recommendation
- Keep canonical abstract row: `Blind tailing without understanding thesis, fair value, and exit conditions...`
- Optionally keep narrow tactical row: `Copying someone else's position without matching their entry price or timing.`
- Mark `Blindly tailing a sharp trader after the price has moved...` as near-duplicate candidate

### Related cases
- Could later add more explicit tailing-loss cases if useful

---

# Rows to keep as clearly distinct

These currently look worth keeping and **not** merging away:

## Execution / sizing
- `False-bond panic hierarchy`
- `Bond sizing must respect realistic market capacity`
- `Bonding as liquidity service`
- `In fast-settling repeatable markets, idle cash is a meaningful EV leak because edge can be recycled frequently.`
- `As bankroll grows, self-induced price movement and reduced fill quality become part of edge evaluation, not just directional correctness.`
- `Trading full-time with insufficient bankroll can create chronic undersizing even when the trader correctly identifies strong edges.`

## Crowd / pricing
- `Confusing high probability with true settlement certainty`
- `Paying a consensus premium`
- `Overweighting stale history after fresh news changes the setup`
- `Fragmented fills versus informed sweep`
- `Mass-attention event day dislocation`

## Phase
- `Fresh breaking news can collapse Q&A width`

## Anti-patterns
- `Prioritizing speed over certainty in bond-sniping creates expensive misbonds when the trigger is not fully confirmed.`

---

# Rows that should probably remain cases, not become more principles

These are strong as `decision_cases` and do not currently need more abstraction rows:

- `Anthropic versus Claude dispute`
- `Taiwan fast-click misread`
- `Mike Johnson first-vote false bond`
- `Travis Scott pre-halftime proximity mispricing`
- `Picked lexical mispricing`
- `Inch sample-selection failure`
- `Monday Night Football Inch scorebug edge`
- `Next Gen Stats integration shock`
- `Meet the Press promo invalidated by fresh Venezuela shock`

---

# Suggested next cleanup pass

## Pass 1 — annotate only
Create a lightweight annotation layer (markdown/json/sql-notes) with statuses:
- `canonical`
- `near_duplicate`
- `keep_parallel`
- `case_only_support`

## Pass 2 — resolve easiest merges
Safest first-wave merge candidates:
1. segmentation family
2. phase abstraction family
3. blowout-yap family
4. blind-tailing family

## Pass 3 — optional physical cleanup
Only after manual review:
- deprecate or delete near-duplicates
- keep canonical rows + granular sub-rows + cases

---

# Practical recommendation

Do **not** run destructive deletes yet.

Instead:
1. use this file as the merge map,
2. review the four families above,
3. only then decide whether to physically prune rows or simply treat some as deprecated in future reasoning.
