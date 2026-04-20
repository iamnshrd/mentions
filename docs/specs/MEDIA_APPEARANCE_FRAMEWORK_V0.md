# Media appearance framework V0

## Purpose

This framework covers mention markets where the relevant event is a media appearance rather than a classic event-format speech / rally / press briefing.

Target cases include:
- cable news hits
- studio interviews
- Sunday shows
- panel segments
- anchor exchanges
- remote hits / satellite interviews
- show-format appearances more generally

The goal is to move analysis from:
- topic looks related

to:
- what is the realistic conversational path to mention in this media format?

---

## 1. Product problem

Current mention analysis is strongest when it can treat the market as:
- speaker + event + transcript analogs + topic grounding

That works reasonably for:
- speeches
- rallies
- press briefings
- roundtables
- conference-like appearances

It is weaker for media-appearance markets, because these need a different framework.

The main unit is not just:
- topic relevance

but:
- segment structure
- host control
- outlet/show format
- likely topic transition path
- whether the mention would need prompting or bridging

---

## 2. New framework object

Introduce a separate conceptual family:

- `media_appearance_framework`

This should sit alongside existing event-prior logic, not be forced into generic event fallback.

---

## 3. Core layers

### Layer A. Media event classification

The system should first detect that the market belongs to a media-appearance class.

### Output
A normalized media event type, for example:
- `cable_news_short_hit`
- `host_driven_interview`
- `panel_segment`
- `friendly_longform_interview`
- `sunday_show_interview`
- `townhall_media_format`
- `remote_hit`
- `special_media_appearance`

### Inputs
- event title
- market title
- series family
- show name
- outlet name
- host/program tokens

### Why
This lets path-read start from the actual media format rather than from generic topic proximity.

---

### Layer B. Media prior registry

Create a dedicated registry, analogous to event-prior handling, but for media appearances.

Suggested file:
- `agents/mentions/runtime/media_prior_registry.py`

### For each media prior store:
- expected segment length
- host control over transitions
- spontaneity / interruption level
- openness to side branches
- whether mentions usually arrive via:
  - direct host prompt
  - reactive answer
  - bridge from another topic
  - opening monologue
  - closing riff
- baseline path risk
- baseline overextension risk

---

### Layer C. Show / outlet knowledge layer

Media appearances need show-specific context.

Suggested file:
- `agents/mentions/runtime/media_show_registry.py`

### Initial show families to support
- `fox_news_sunday`
- `hannity`
- `the_ingraham_angle`
- `jesse_watters_primetime`
- `special_report_bret_baier`
- `fox_and_friends`
- generic `fox_news_hit`
- Sunday-show bucket:
  - `meet_the_press`
  - `face_the_nation`
  - `this_week`
  - `state_of_the_union`

### For each store:
- outlet
- program type
- host-control level
- ideological/friendly/hostile orientation
- panel vs one-on-one
- typical topic breadth
- whether side-topic mentions are common or usually host-driven

---

### Layer D. Mention-path model

This is the key layer.

The framework must score realistic paths to mention rather than generic topical relevance.

Suggested path classes:
- `direct_prompt_path`
- `agenda_native_path`
- `reactive_path`
- `bridge_path`
- `closing_riff_path`
- `weak_lexical_path`

### Definitions
- `direct_prompt_path`
  - host explicitly raises the target issue
- `agenda_native_path`
  - target belongs naturally to the announced segment topic
- `reactive_path`
  - target emerges as a reaction to another topic or attack line
- `bridge_path`
  - speaker is known to steer conversation into target territory
- `closing_riff_path`
  - mention appears in wrap-up / slogan / generic framing
- `weak_lexical_path`
  - target is thematically nearby but no realistic conversation path is visible

### Desired output
A block like:
- realistic paths
- weak paths
- blocked/unlikely paths
- path control source (host-driven vs speaker-driven)

---

### Layer E. Historical analogs for media appearances

Historical retrieval for these cases should not just mean:
- same speaker said similar topic before

It should prefer:
- same speaker
- same media format
- same show/outlet or similar show class
- similar host-control pattern
- similar path-to-topic shape

### Retrieval priorities
1. same speaker + same show
2. same speaker + same outlet format
3. same speaker + same interview/panel family
4. same speaker + similar conversational path

### Additional analog features
- did target topic appear only when prompted?
- did speaker self-bridge into it?
- did topic appear only in longer formats, not short hits?
- did host repeatedly force the topic?

---

### Layer F. Strike discipline for media appearances

Media-appearance cases need stronger anti-strike-first controls.

Rule:
- strike labels do not become direct event topics unless supported by media-format path logic

This prevents failures where a strike word becomes the synthetic event baseline with no real event grounding.

---

## 4. V0 implementation plan

### Step 1. Add media-family detection
Suggested file:
- `agents/mentions/runtime/media_detection.py`

Responsibilities:
- detect media-appearance market
- assign media event type
- identify show/outlet/host hints where possible

### Step 2. Add media prior registry
Suggested file:
- `agents/mentions/runtime/media_prior_registry.py`

Responsibilities:
- store media prior definitions
- expose:
  - `detect_media_prior_mode(...)`
  - `get_media_prior(...)`

### Step 3. Add media show registry
Suggested file:
- `agents/mentions/runtime/media_show_registry.py`

Responsibilities:
- show metadata and host-control priors
- show-class mapping

### Step 4. Add path evaluator
Suggested file:
- `agents/mentions/runtime/media_pathing.py`

Responsibilities:
- infer likely mention paths
- classify weak vs strong paths
- expose path-read block for synthesis

### Step 5. Integrate into synthesis
Primary integration point:
- `runtime/speaker_paths.py`
- possibly `runtime/synthesize_speaker.py`

Responsibilities:
- when market is media-appearance class, use media framework instead of generic event fallback
- feed path analysis into interpretation / market_gets_right / market_flattens / strike discipline

---

## 5. Initial V0 output schema

Suggested synthesis block:

```python
{
  'media_event_type': 'host_driven_interview',
  'show_family': 'fox_news_sunday',
  'host_control': 'high',
  'segment_shape': 'topic_bounded',
  'realistic_paths': ['direct_prompt_path', 'reactive_path'],
  'weak_paths': ['bridge_path'],
  'blocked_paths': ['agenda_native_path'],
  'path_confidence': 'medium',
  'historical_media_support': 'partial',
}
```

---

## 6. Coverage goals

This framework is meant to cover the observed weak spots in mention-market analysis such as:
- Fox News mention markets
- Sunday show mention markets
- other TV/show appearance markets

It is not the creator-video framework.
That should remain a separate future framework.

---

## 7. Immediate next practical step

Implement only the minimum viable spine first:

1. media detection
2. media prior registry
3. simple path evaluator
4. anti-strike-first guardrail for media cases
5. synthesis integration for one concrete family:
   - `FOXNEWSMENTION`

That is enough for V0.
