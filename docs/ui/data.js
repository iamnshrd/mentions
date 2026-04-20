// Data contracts for the research workspace
window.QUERY = "What will Bernie Sanders say at the More Perfect University Kick Off Call?";

window.ANALYSIS_CARD = {
  thesis: "Bernie will most likely frame the call around student organizing against corporate power.",
  evidence: [
    "Direct event materials frame the call as a launch for More Perfect University.",
    "Organizer messaging emphasizes youth organizing, anti-corporate politics, and movement building.",
    "Independent coverage supports the broader launch framing, though exact remarks remain uncertain."
  ],
  uncertainty: "Independent event-specific reporting is thin, so exact phrasing and narrower policy mentions remain uncertain.",
  risk: "The event could stay broad and motivational rather than policy-specific.",
  next_check: "Look for direct transcript-backed language about student organizing, oligarchy, or working-class politics.",
  action: "Treat movement-building and anti-corporate rhetoric as the core expected message cluster.",
  fair_value_view: "This is a directional interpretation, not a precise policy-level prediction."
};

window.DIRECT_NEWS = [
  { headline: "Bernie Sanders to join More Perfect University Kick Off Call", source: "Action Network", published_at: "2026-04-20T18:00:00Z", url: "#", tag: "direct" },
  { headline: "Bernie Sanders co-hosts launch event for More Perfect University", source: "Common Dreams", published_at: "2026-04-20T15:00:00Z", url: "#", tag: "direct" }
];

window.BACKGROUND_NEWS = [
  { headline: "Progressive media group launches More Perfect University to compete for students", source: "Inside Higher Ed", published_at: "2026-04-17T14:00:00Z", url: "#", tag: "background" },
  { headline: "Liberals launch campus organizing project as rival to Turning Point USA", source: "The Independent", published_at: "2026-04-18T12:00:00Z", url: "#", tag: "background" }
];

window.TRANSCRIPT_TRACE = {
  lead_candidate: { transcript_id: "bern-0420-kickoff", segment_index: 12, source_ref: "youtube:abc123", event_title: "More Perfect University Kick Off Call", event_date: "2026-04-20", start_ts: "00:08:14", end_ts: "00:08:52" },
  retrieval_hits: [
    { chunk_id: 91, document_id: 17, chunk_index: 12, source_file: "bernie_kickoff_call.txt", speaker: "Bernie Sanders", event: "More Perfect University Kick Off Call" }
  ]
};

window.RANKING_DEBUG = {
  provider_coverage: { google_news_status: "ok", google_news_count: 6 },
  ranking_summary: { ranked_count: 6, kept_count: 3, rejected_count: 3, final_news_count: 3 },
  typed_coverage: { coverage_state: "event-led", core_count: 2, expansion_count: 1, ambient_count: 1 },
  lead_news: { headline: "Bernie Sanders to join More Perfect University Kick Off Call", source: "Action Network" },
  top_ranked: [{ headline: "Bernie Sanders to join More Perfect University Kick Off Call", decision: "keep", final_relevance_score: 3.2, noise_flags: [] }],
  top_rejected: [{ headline: "Generic campus politics article", decision: "reject", final_relevance_score: 1.1, noise_flags: ["generic-context-only"] }]
};

window.CONTEXT_RISKS = ["limited-direct-event-coverage", "organizer-owned-source-heavy", "exact-remarks-uncertain"];

window.DEBUG_VIEW = {
  summary: { sources_used: ["news", "transcripts"], news_count: 3, transcript_count: 2, has_market_data: true },
  runtime_health: { news: { status: "ok", contract: "news_search" }, transcripts: { status: "ok", contract: "transcript_search" } },
  context_risks: { news: ["limited-direct-event-coverage"], transcripts: [] },
  top_evidence: { lead_transcript: { transcript_id: "bern-0420-kickoff", segment_index: 12 }, news_items: [{ headline: "Bernie Sanders to join More Perfect University Kick Off Call", source: "Action Network" }] }
};

// Evidence-to-source linkage
window.EVIDENCE_SOURCES = [
  { evidenceIdx: 0, sourceType: 'direct', sourceLabel: 'Action Network', tag: 'DIRECT', icon: '◆', headline: "Bernie Sanders to join More Perfect University Kick Off Call" },
  { evidenceIdx: 1, sourceType: 'direct', sourceLabel: 'Common Dreams', tag: 'DIRECT', icon: '◆', headline: "Bernie Sanders co-hosts launch event for More Perfect University" },
  { evidenceIdx: 2, sourceType: 'background', sourceLabel: 'Inside Higher Ed + The Independent', tag: 'BG', icon: '◇', headline: null },
];
