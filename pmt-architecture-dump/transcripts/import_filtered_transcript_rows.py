import sqlite3, json
DB='/root/.openclaw/workspace/pmt_trader_knowledge.db'
conn=sqlite3.connect(DB)
cur=conn.cursor()

video_for = {
    'foster': 'foster---88830119-e55f-4054-975b-635fce0f3e83',
    'logan': 'logan---dfc37c1c-12b9-4386-9354-3d0c310d3e01',
    'nate': 'nate---d6d7387d-9e40-4d80-ba90-a8a8c49c1ad8',
    'tyrael': 'tyrael---f5dae1a5-e645-4d7a-b3b8-caab7f68d3bb',
}

def upsert_execution(name, execution_type, description, best_used_when, avoid_when, risk_note, video_key):
    row=cur.execute("SELECT id FROM execution_patterns WHERE pattern_name=?", (name,)).fetchone()
    if row: return row[0]
    cur.execute("INSERT INTO execution_patterns (pattern_name, execution_type, description, best_used_when, avoid_when, risk_note, example_video_id) VALUES (?,?,?,?,?,?,?)",
                (name, execution_type, description, best_used_when, avoid_when, risk_note, video_for[video_key]))
    return cur.lastrowid

def upsert_sizing(text, lesson_type, description, applies_to, risk_note):
    row=cur.execute("SELECT id FROM sizing_lessons WHERE lesson_text=?", (text,)).fetchone()
    if row: return row[0]
    cur.execute("INSERT INTO sizing_lessons (lesson_text, lesson_type, description, applies_to, risk_note) VALUES (?,?,?,?,?)",
                (text, lesson_type, description, applies_to, risk_note))
    return cur.lastrowid

def upsert_crowd(name, mistake_type, description, why_it_happens, how_to_exploit, video_key):
    row=cur.execute("SELECT id FROM crowd_mistakes WHERE mistake_name=?", (name,)).fetchone()
    if row: return row[0]
    cur.execute("INSERT INTO crowd_mistakes (mistake_name, mistake_type, description, why_it_happens, how_to_exploit, example_video_id) VALUES (?,?,?,?,?,?)",
                (name, mistake_type, description, why_it_happens, how_to_exploit, video_for[video_key]))
    return cur.lastrowid

def upsert_signal(name, signal_type, description, interpretation, typical_action, confidence):
    row=cur.execute("SELECT id FROM pricing_signals WHERE signal_name=?", (name,)).fetchone()
    if row: return row[0]
    cur.execute("INSERT INTO pricing_signals (signal_name, signal_type, description, interpretation, typical_action, confidence) VALUES (?,?,?,?,?,?)",
                (name, signal_type, description, interpretation, typical_action, confidence))
    return cur.lastrowid

def upsert_phase(name, description, more, less, errors, notes):
    row=cur.execute("SELECT id FROM phase_logic WHERE phase_name=? AND event_format_id IS NULL", (name,)).fetchone()
    if row: return row[0]
    cur.execute("INSERT INTO phase_logic (phase_name, event_format_id, description, what_becomes_more_likely, what_becomes_less_likely, common_pricing_errors, execution_notes) VALUES (?,NULL,?,?,?,?,?)",
                (name, description, more, less, errors, notes))
    return cur.lastrowid

def upsert_antipattern(text, why_bad, video_key):
    row=cur.execute("SELECT id FROM anti_patterns WHERE pattern_text=?", (text,)).fetchone()
    if row: return row[0]
    cur.execute("INSERT INTO anti_patterns (pattern_text, why_bad, example_video_id) VALUES (?,?,?)",
                (text, why_bad, video_for[video_key]))
    return cur.lastrowid

def upsert_case(video_key, market_context, setup, decision, reasoning, risk_note, outcome_note, tags):
    row=cur.execute("SELECT id FROM decision_cases WHERE video_id=? AND setup=?", (video_for[video_key], setup)).fetchone()
    if row: return row[0]
    cur.execute("INSERT INTO decision_cases (video_id, market_context, setup, decision, reasoning, risk_note, outcome_note, tags) VALUES (?,?,?,?,?,?,?,?)",
                (video_for[video_key], market_context, setup, decision, reasoning, risk_note, outcome_note, tags))
    return cur.lastrowid

def link(table, left_col, right_col, left_id, right_id):
    cur.execute(f"INSERT OR IGNORE INTO {table} ({left_col}, {right_col}) VALUES (?,?)", (left_id, right_id))

exec_ids = {}
exec_ids['false_bond'] = upsert_execution('False-bond panic hierarchy','bonding/dispute','If a bond-like trade is not mechanically settled, the trader who recognizes invalidity first has a major exit advantage; late panic gets punished.','Rule-sensitive, ambiguous, or process-dependent markets where participants may mistake high probability for certainty.','Truly settled outcomes with no unresolved process or interpretation risk.','The edge disappears if the bond is actually final; oversized size can turn a good insight into catastrophic tail exposure.','logan')
exec_ids['bond_capacity'] = upsert_execution('Bond sizing must respect realistic market capacity','bond sizing','Bond size should be constrained by realistic cash-out demand and market volume; oversized bond walls create asymmetric tail risk.','Illiquid and medium-liquidity markets where notional posted size can exceed realistic exit demand.','Markets with deep, proven exit flow or mechanically final settlement.','Posting size far above plausible cash-out capacity can create very poor risk/reward if the trade is wrong.','tyrael')

sizing_ids = {}
sizing_ids['idle_cash'] = upsert_sizing('In fast-settling repeatable markets, idle cash is a meaningful EV leak because edge can be recycled frequently.','capital efficiency','Repeatable short-cycle markets reward constant capital deployment more than long-idle optionality.','Mentions, announcer markets, bond-like and recurring event markets.','Do not force capital into weak trades merely to avoid cash drag; applies only when a trader has a real repeatable edge.')
sizing_ids['impact'] = upsert_sizing('As bankroll grows, self-induced price movement and reduced fill quality become part of edge evaluation, not just directional correctness.','scaling','A larger trader must think about slippage, market impact, and adverse selection as part of expected value.','Scaling from small to medium or large size in illiquid and semi-liquid markets.','A trade that was highly profitable at small size may become mediocre once the trader moves the market against himself.')

crowd_ids = {}
crowd_ids['segmentation'] = upsert_crowd('Raw history without format segmentation','data misuse','Crowd often uses broad historical counts without segmenting by actual market format, causing major fair-value errors.','People rely on transcripts or historical hit rates without matching the listed market to the relevant subformat.','Segment by the actual listed format: event type, prime-time vs non-prime-time, speaker context, broadcast type, game state, and path structure.','foster')
crowd_ids['certainty'] = upsert_crowd('Confusing high probability with true settlement certainty','rules/probability confusion','Crowd frequently confuses high probability with true settlement certainty, especially in bonds, disputes, and rule-sensitive markets.','Participants compress complex resolution and process risk into a simplistic near-certain price.','Exploit by identifying conditionality, process incompleteness, entity ambiguity, or hidden tail paths before the crowd reprices.','logan')
crowd_ids['consensus'] = upsert_crowd('Paying a consensus premium','meta-pricing','When a trade thesis becomes consensus, the crowd often overpays for the direction itself and compresses away the original edge.','Shared ideas spread faster than liquidity can absorb them, causing price overshoot.','Fade or reduce participation in trades where the logic is right but the crowd has already overpaid for it.','tyrael')
crowd_ids['stale_history'] = upsert_crowd('Overweighting stale history after fresh news changes the setup','stale anchoring','Crowd often anchors to stale historical or promo-based priors after fresh news has already changed the relevant topic tree.','Pre-event materials feel concrete, so participants underweight the impact of fresh shocks.','Exploit by repricing around the new event tree rather than the stale script or promo frame.','tyrael')

signal_ids = {}
signal_ids['fragmented_vs_sweep'] = upsert_signal('Fragmented fills versus informed sweep','microstructure','Many small fragmented fills are more consistent with recreational flow, while a sudden full-size sweep is more likely to reflect informed flow or structural change.','Fill pattern itself contains information about the type of counterparty and whether the market may be repricing for a real reason.','Treat full-size sudden sweeps as a warning to reevaluate assumptions; treat fragmented fills as lower-information retail flow unless other evidence disagrees.',0.76)
signal_ids['mass_attention'] = upsert_signal('Mass-attention event day dislocation','flow-driven dislocation','Mass-attention event days can push prices far beyond baseline comps because recreational flow overwhelms normal equilibrium.','Large public events create retail order flow that can dominate historical baselines and temporarily distort side markets.','Inspect front-page high-attention events aggressively, especially side markets where casual participants anchor on narrative rather than fair value.',0.79)

phase_ids = {}
phase_ids['prepared_vs_qna'] = upsert_phase('Prepared remarks and Q&A are separate pricing regimes','Prepared remarks and Q&A should be treated as separate pricing regimes because many strikes live almost entirely in one phase or the other.','Phase-specific words, repricing after scripted sections end, and phase-based yes/no basket differentiation.','Mispricing of unsaid words that mostly belong to the other phase.','Traders often use total event time remaining instead of phase-specific opportunity.','Reprice aggressively at the boundary between scripted remarks and open Q&A.')
phase_ids['breaking_news'] = upsert_phase('Fresh breaking news can collapse Q&A width','A major breaking story before or during an event can sharply narrow or suppress Q&A, invalidating many late-path priors.','Focused questioning on the dominant breaking issue, fewer side paths, and shorter topic tree breadth.','Peripheral late-path themes and preplanned broad Q&A baskets.','Traders often continue to price the event as if the original broad Q&A path still exists.','Reassess whether the event still has a real open-ended Q&A phase once the new dominant topic arrives.')
phase_ids['blowout_yap'] = upsert_phase('Blowout late-game yap expansion','Late non-competitive game state increases announcer tangent risk and raises hit probability for off-path or dead-looking strikes.','Random commentary, anecdotal references, and low-structure chatter.','Structured play-by-play-only expectations.','Traders often treat a nearly dead game as if remaining word risk is strictly shrinking.','Be careful shorting dead-looking announcer strikes late in blowouts if announcers are likely to fill air time with tangents.')

anti_ids = {}
anti_ids['blind_tailing'] = upsert_antipattern('Blind tailing without understanding thesis, fair value, and exit conditions usually turns a good originator trade into a worse follower trade.','Followers get worse prices, less context, and slower reaction time when the trade breaks against them.','nate')
anti_ids['speed_misbond'] = upsert_antipattern('Prioritizing speed over certainty in bond-sniping creates expensive misbonds when the trigger is not fully confirmed.','The desire to win top-of-book leads traders to click before they have actually verified the trigger.','logan')

case_ids = {}
case_ids['inch_sample'] = upsert_case('foster','NFL announcer mentions','Broad all-games historical sample suggested an Inch No edge.','The sample was re-segmented to prime-time games after repeated losses showed the broad sample was mismatched to the listed market.','Prime-time games differed materially from the all-games sample, so the original fair value estimate was too optimistic.','Using broad history without matching the listed format can produce a false edge.','The refined sample showed the original bet was much weaker than first thought.','nfl_announcer_mentions,format_segmentation,data_error')
case_ids['mnf_inch'] = upsert_case('foster','NFL announcer mentions','ESPN Monday Night Football scorebug used and-one rather than and-inches, changing spoken hit mechanics.','Broadcast-specific observation was combined with transcript splits to isolate a subformat edge.','Structural broadcast details altered the effective hit rate enough to matter for pricing.','Assuming all prime-time broadcasts are linguistically identical can hide format-specific edges.','Inch No was more defensible in this specific broadcast environment than in generic prime-time games.','nfl_announcer_mentions,broadcast_structure,format_specific_edge')
case_ids['picked'] = upsert_case('foster','NFL announcer mentions','Crowd priced picked as if it referred mostly to a rare interception-style event.','Broader football usages were considered, including picked up the first down, picked in the draft, and picked up the ball.','Lexical breadth mattered more than the crowd’s narrow narrative framing.','Literal framing can obscure common alternate hit paths.','The no side had been materially mispriced.','nfl_announcer_mentions,lexical_ambiguity,mispricing')
case_ids['anthropic'] = upsert_case('foster','Super Bowl ad market','The market referenced Anthropic advertising, but the aired content promoted Claude without explicit Anthropic mention.','Traders had to evaluate brand-versus-subbrand semantics and clarification risk rather than rely on intuitive association.','Entity definition and contract wording were more important than casual brand linkage.','Entering entity-ambiguous disputes without rule clarity can turn intuition into a coin flip.','Clarification favored no and created a major temporary dislocation before full repricing.','super_bowl_ads,entity_definition,rule_ambiguity,dispute')
case_ids['mtp_venezuela'] = upsert_case('tyrael','Political mentions / scheduled interview','Promo materials implied one topic tree, but a fresh Venezuela shock changed likely live content before airtime.','Fresh-news salience was prioritized over stale promo framing.','Current events overrode prepublished topic expectations and changed what the market should price.','Anchoring on promo materials after a major fresh shock leads to stale pricing.','Topic expectations were mispriced by traders who kept using the old frame.','scheduled_interview,current_events_override,topic_tree')
case_ids['nextgen'] = upsert_case('nate','NFL announcer mentions','Traders relied on historical no-side confidence from pre-integration conditions.','A sudden broadcast/product integration changed the live environment and invalidated the old sample.','Infrastructure or product changes can zero out a previously strong historical edge.','Historical data is fragile when the underlying product or broadcast structure changes.','Existing maker-side positions became immediately offside.','nfl_announcer_mentions,integration_shock,regime_change')
case_ids['taiwan'] = upsert_case('foster','Politics / news reaction market','A Trump Truth post was skimmed and Taiwan was misread as a visit signal rather than a discussion topic.','The market was clicked before full syntactic and contextual parsing.','Speed without full parse turned a plausible news reaction into a pure self-inflicted error.','Fast-clicking before full comprehension can create avoidable losses and mislead followers.','The trader took an immediate avoidable loss.','news_reaction,fast_click,parse_error')
case_ids['mike_johnson'] = upsert_case('logan','Politics / process market','A market appeared settled at one cent because traders thought the first vote had failed.','Some traders failed to account for vote changes before the process was actually final.','Process finality mattered more than the crowd’s assumption that the outcome was already locked.','One-cent pricing is still wrong if the decision process is incomplete.','Yes side recovered after members returned and changed votes.','politics,false_bond,process_finality')

link('case_crowd_mistakes','case_id','crowd_mistake_id',case_ids['inch_sample'],crowd_ids['segmentation'])
link('case_crowd_mistakes','case_id','crowd_mistake_id',case_ids['anthropic'],crowd_ids['certainty'])
link('case_crowd_mistakes','case_id','crowd_mistake_id',case_ids['mtp_venezuela'],crowd_ids['stale_history'])
link('case_execution_patterns','case_id','execution_pattern_id',case_ids['mike_johnson'],exec_ids['false_bond'])
link('case_execution_patterns','case_id','execution_pattern_id',case_ids['taiwan'],exec_ids['false_bond'])
link('case_execution_patterns','case_id','execution_pattern_id',case_ids['mike_johnson'],exec_ids['bond_capacity'])
link('case_pricing_signals','case_id','pricing_signal_id',case_ids['nextgen'],signal_ids['fragmented_vs_sweep'])
link('case_pricing_signals','case_id','pricing_signal_id',case_ids['anthropic'],signal_ids['mass_attention'])
link('case_anti_patterns','case_id','anti_pattern_id',case_ids['taiwan'],anti_ids['speed_misbond'])
link('case_anti_patterns','case_id','anti_pattern_id',case_ids['mike_johnson'],anti_ids['blind_tailing'])

conn.commit()
print(json.dumps({
    'video_for': video_for,
    'counts': {
        'execution_patterns': len(exec_ids),
        'sizing_lessons': len(sizing_ids),
        'crowd_mistakes': len(crowd_ids),
        'pricing_signals': len(signal_ids),
        'phase_logic': len(phase_ids),
        'anti_patterns': len(anti_ids),
        'decision_cases': len(case_ids)
    }
}, indent=2))
