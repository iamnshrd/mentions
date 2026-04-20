# Framework coverage map (2026-04-18)

## Purpose

This document maps the current `mentions` framework coverage by event class.

It answers:
- what market/event types exist conceptually
- how well the current stack covers them
- what fallback quality exists today
- what is still missing
- what the next module/framework step should be

This is a product-and-architecture map, not a marketing status note.

---

## Coverage scale

### Coverage labels
- **strong** — current path is structurally aligned and usually interpretable
- **usable** — framework exists and can often produce honest reads, but quality ceiling is visible
- **partial** — some framework elements exist, but current output is brittle or often under-grounded
- **weak** — only generic fallback exists
- **not built** — no real dedicated framework yet

### Data dependency note
Some classes are blocked more by **corpus coverage** than by architecture.
Where that is true, it is called out explicitly.

---

## 1. Classic political event classes

### 1.1 Press briefing / press conference
**Examples**
- White House Press Secretary mention markets
- briefing-room / presser style events

**Current coverage:** strong

**What exists**
- event-prior fallback for `press_briefing`
- format recognition in `analysis/event_context.py`
- interpretation support for semi-open/Q&A logic
- event-level, not strike-level, reading

**Current weakness**
- still relies on fallback when transcript infrastructure is thin
- could still overread weak side branches if retrieval is noisy

**Next useful improvement**
- better market-surface scanning to quantify how often this family appears
- optional future retrieval polish, but framework shape is already solid

---

### 1.2 Sunday show interview
**Examples**
- Fox News Sunday
- Meet the Press
- Face the Nation
- This Week
- State of the Union

**Current coverage:** usable

**What exists**
- event-prior fallback for `sunday_show_interview`
- media framework V0 now also recognizes this as media/show-format class
- show registry seeded for major Sunday shows
- path evaluator exists in rule-based V0 form

**Current weakness**
- no media transcript corpus yet
- historical analog layer is mostly missing
- show-specific logic is still shallow

**Main blocker**
- transcript/data coverage, not core architecture

**Next useful improvement**
- ingest tagged Sunday-show transcripts
- then add same-show / same-format historical analog retrieval

---

### 1.3 Generic interview / host-driven interview
**Examples**
- non-Sunday TV interviews
- structured one-on-one political interviews

**Current coverage:** usable

**What exists**
- event-prior fallback for `interview`
- media framework V0 supports `host_driven_interview`
- path evaluator handles direct/reactive/bridge distinctions

**Current weakness**
- generic detection is still broad
- no strong historical analog support yet
- risk of under-grounding if event title is thin

**Next useful improvement**
- show-specific detection and media transcript coverage

---

### 1.4 Speech / scripted remarks
**Examples**
- formal speeches
- addresses
- prepared remarks

**Current coverage:** strong

**What exists**
- event-prior fallback for `scripted_speech`
- event-context format detection
- interpretation logic understands narrower scripted path

**Current weakness**
- can still underperform if event title parsing is weak
- still depends on good event-level extraction

**Next useful improvement**
- minor retrieval polish only; framework is basically there

---

### 1.5 Rally / campaign event
**Examples**
- rallies
- campaign stops

**Current coverage:** usable

**What exists**
- event-prior fallback for `rally`
- interpretation logic understands broader rhetorical path

**Current weakness**
- no dedicated rally-specific path evaluator
- may still flatten open rhetorical sprawl too crudely

**Next useful improvement**
- only worth deeper work if scanner later shows high market frequency

---

### 1.6 Roundtable / panel / semi-structured event
**Examples**
- Trump roundtables
- panel-like issue events

**Current coverage:** usable to strong

**What exists**
- strong historical work was done here already
- transcript pathing and strike-basket/path interpretation are strongest in this family
- explicit event-level analysis and negative boundary logic

**Current weakness**
- still somewhat dependent on transcript family quality
- format/panel variants could diverge in future

**Next useful improvement**
- none urgently needed; this is one of the better-covered classes

---

### 1.7 Conference / coalition / activist event
**Examples**
- Turning Point USA / Build the Red Wall
- conference-style coalition gatherings

**Current coverage:** usable

**What exists**
- event-prior fallback `conference_coalition`
- interpretation logic already tuned to reduce false “overextension” on coalition/opponents/media branches in this class

**Current weakness**
- no dedicated conference path engine
- still relies on event priors more than rich historical analogs

**Next useful improvement**
- low urgency unless scanner shows this family is extremely frequent

---

### 1.8 Special event appearance / dinner-media-room hybrid
**Examples**
- White House Correspondents' Dinner
- gala / dinner / roast-like public appearance

**Current coverage:** partial

**What exists**
- event-prior fallback `dinner_media_room`

**Current weakness**
- no dedicated framework beyond fallback
- no structured path model for social/media-room events
- transcript analog logic is weak for these events

**Next useful improvement**
- build `special_event_appearance_framework` if this family proves frequent enough

---

## 2. Media-appearance classes

### 2.1 Cable news short hit
**Examples**
- Fox News mention markets
- generic cable-news appearance markets

**Current coverage:** partial, improving

**What exists**
- `MEDIA_APPEARANCE_FRAMEWORK_V0.md`
- `runtime/media_prior_registry.py`
- `runtime/media_show_registry.py`
- `runtime/media_detection.py`
- `runtime/media_pathing.py`
- media-aware interpretation in synthesis
- anti-strike-first media guardrails

**Current weakness**
- no actual media transcript corpus yet
- show-specific logic still shallow
- historical media analog retrieval plumbing exists, but returns empty without data

**Main blocker**
- corpus coverage first, then retrieval quality

**Next useful improvement**
- ingest show-format transcripts
- then build same-show / same-format analog retrieval

---

### 2.2 Show-specific cable news families
**Examples**
- Hannity
- Ingraham
- Bret Baier / Special Report
- Fox & Friends
- Jesse Watters

**Current coverage:** partial

**What exists**
- show registry entries
- show metadata now flows into synthesis

**Current weakness**
- no deeper show-specific path behavior yet
- generic fallback still dominates

**Next useful improvement**
- enrich show-specific path logic once transcript corpus exists

---

### 2.3 Media panel segment / crossfire-like segment
**Examples**
- TV panel discussions
- segmented multi-host exchanges

**Current coverage:** weak

**What exists**
- only broad media framework concepts
- no dedicated panel-specific runtime logic

**Current weakness**
- no panel-mode-aware path logic
- no retrieval/data layer

**Next useful improvement**
- low priority until scanner shows it matters

---

## 3. Non-political / adjacent mention classes

### 3.1 Creator video / YouTube mention markets
**Examples**
- MrBeast next video mention markets

**Current coverage:** not built

**What exists**
- conceptual recognition that this is a separate class
- explicit decision that current political/media event framework is not the right abstraction

**Current weakness**
- no creator-format framework
- no content-structure path logic
- no creator transcript/video corpus

**Needed framework**
- `creator_video_framework`

**Next useful improvement**
- build design doc + initial framework spine only after priorities are confirmed

---

### 3.2 Podcast / longform conversational appearance
**Examples**
- future podcast mention markets
- longform talk-show / podcast episodes

**Current coverage:** weak / not built

**What exists**
- generic interview logic only

**Current weakness**
- longform structure differs materially from short TV hit
- needs different path assumptions and different analog logic

**Next useful improvement**
- could be grouped later into a broader appearance framework, but not urgent yet

---

## 4. Cross-cutting framework infrastructure status

### 4.1 Event-level interpretation layer
**Status:** strong

**What exists**
- interpretation block
- market_gets_right / market_flattens
- event-first analysis target
- strike list as supporting structure only

**Comment**
This is one of the strongest architectural pieces now.

---

### 4.2 Strike-path / basket layer
**Status:** usable

**What exists**
- strike baskets
- topic paths
- family evidence
- weak/core/late distinctions
- reasons per strike

**Current weakness**
- still needs class-specific guardrails in special domains
- media anti-strike-first guardrails were added, but more class-specific controls may be needed later

---

### 4.3 Event-prior fallback framework
**Status:** strong

**What exists**
- speaker-agnostic fallback system
- registry-driven prior modes
- already validated across several event families

**Comment**
This is the core reason the system can stay honest when transcript path infrastructure is missing.

---

### 4.4 Media framework infrastructure
**Status:** partial, but structurally real

**What exists**
- media design doc
- media prior registry
- media detection
- show registry
- media path evaluator
- anti-strike-first guardrails
- media analog plumbing in transcript builder

**Current weakness**
- missing corpus
- missing high-quality historical analog retrieval

---

### 4.5 Broad market-surface intelligence
**Status:** weak

**What exists**
- idea is clear
- attempted wide scan exposed provider limitations

**Current weakness**
- no good broad closed-market scanner utility yet
- current provider path is optimized for targeted retrieval, not full weekly taxonomy sweeps

**Next useful improvement**
- build separate recent-market scanner utility

---

## 5. Priority map from here

### Priority A — market-surface planning layer
Build:
- broad market-surface scanner
- coverage map refresh based on real recent market surface

Why:
- this lets framework priorities be driven by actual market frequency

---

### Priority B — media framework completion (data-dependent)
Build next after transcript ingest:
- media transcript corpus
- same-show / same-format analog retrieval
- show-specific path tuning

Why:
- architecture is now mostly ready; data is the next constraint

---

### Priority C — creator-video framework
Build when ready:
- separate framework doc + V0 spine

Why:
- clearly a different market class with different priors and path logic

---

### Priority D — retrieval/refactor stabilization
Continue selectively:
- `runtime/retrieve.py` cleanup
- retrieval contract tightening

Why:
- maintainability and correctness still matter, even while framework coverage expands

---

## 6. Short recommendation

If choosing the next best branch right now:

1. **build broad market-surface scanner**
2. **refresh coverage map from real market data**
3. **hold media framework until transcript corpus arrives**
4. **then choose next framework based on actual frequency**

If choosing the next best framework-only branch right now:

1. media framework is structurally enough for pause
2. next likely new framework should be `creator_video_framework`
3. special-event appearance framework is a secondary candidate
