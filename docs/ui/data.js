(function () {
  const DEFAULT_WORKSPACE_DATA = {
    query: "What will Bernie Sanders say at the More Perfect University Kick Off Call?",
    analysis_card: {
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
    },
    direct_event_news: [
      {
        headline: "Bernie Sanders to join More Perfect University Kick Off Call",
        source: "Action Network",
        published_at: "2026-04-20T18:00:00Z",
        url: "#",
        tag: "direct"
      },
      {
        headline: "Bernie Sanders co-hosts launch event for More Perfect University",
        source: "Common Dreams",
        published_at: "2026-04-20T15:00:00Z",
        url: "#",
        tag: "direct"
      }
    ],
    background_news: [
      {
        headline: "Progressive media group launches More Perfect University to compete for students",
        source: "Inside Higher Ed",
        published_at: "2026-04-17T14:00:00Z",
        url: "#",
        tag: "background"
      },
      {
        headline: "Liberals launch campus organizing project as rival to Turning Point USA",
        source: "The Independent",
        published_at: "2026-04-18T12:00:00Z",
        url: "#",
        tag: "background"
      }
    ],
    transcript_trace: {
      lead_candidate: {
        transcript_id: "bern-0420-kickoff",
        segment_index: 12,
        source_ref: "youtube:abc123",
        event_title: "More Perfect University Kick Off Call",
        event_date: "2026-04-20",
        start_ts: "00:08:14",
        end_ts: "00:08:52",
        speaker: "Bernie Sanders"
      },
      retrieval_hits: [
        {
          chunk_id: 91,
          document_id: 17,
          chunk_index: 12,
          source_file: "bernie_kickoff_call.txt",
          speaker: "Bernie Sanders",
          event: "More Perfect University Kick Off Call",
          text: "What we are doing today with More Perfect University is building something that has never existed before — a national network of young people who understand that the real fight is not left vs right, it is working people vs corporate oligarchy.",
          start_ts: "00:08:14",
          end_ts: "00:08:52"
        }
      ],
      excerpt: "What we are doing today with More Perfect University is building something that has never existed before — a national network of young people who understand that the real fight is not left vs right, it is working people vs corporate oligarchy.",
      excerpt_speaker: "Bernie Sanders"
    },
    ranking_debug: {
      provider_coverage: { google_news_status: "ok", google_news_count: 6 },
      ranking_summary: { ranked_count: 6, kept_count: 3, rejected_count: 3, final_news_count: 3 },
      typed_coverage: { coverage_state: "event-led", core_count: 2, expansion_count: 1, ambient_count: 1 },
      lead_news: { headline: "Bernie Sanders to join More Perfect University Kick Off Call", source: "Action Network" },
      top_ranked: [{ headline: "Bernie Sanders to join More Perfect University Kick Off Call", decision: "keep", final_relevance_score: 3.2, noise_flags: [] }],
      top_rejected: [{ headline: "Generic campus politics article", decision: "reject", final_relevance_score: 1.1, noise_flags: ["generic-context-only"] }]
    },
    context_risks: ["limited-direct-event-coverage", "organizer-owned-source-heavy", "exact-remarks-uncertain"],
    debug_view: {
      summary: { sources_used: ["news", "transcripts"], news_count: 3, transcript_count: 2, has_market_data: true },
      runtime_health: { news: { status: "ok", contract: "news_search" }, transcripts: { status: "ok", contract: "transcript_search" } },
      context_risks: { news: ["limited-direct-event-coverage"], transcripts: [] },
      top_evidence: { lead_transcript: { transcript_id: "bern-0420-kickoff", segment_index: 12 }, news_items: [{ headline: "Bernie Sanders to join More Perfect University Kick Off Call", source: "Action Network" }] }
    },
    evidence_sources: [
      { evidenceIdx: 0, sourceType: "direct", sourceLabel: "Action Network", tag: "DIRECT", headline: "Bernie Sanders to join More Perfect University Kick Off Call" },
      { evidenceIdx: 1, sourceType: "direct", sourceLabel: "Common Dreams", tag: "DIRECT", headline: "Bernie Sanders co-hosts launch event for More Perfect University" },
      { evidenceIdx: 2, sourceType: "background", sourceLabel: "Inside Higher Ed + The Independent", tag: "BG", headline: null }
    ]
  };

  function ensureObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  }

  function ensureArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function normalizeNewsItem(item, tag) {
    const source = ensureObject(item);
    return {
      headline: source.headline || '',
      source: source.source || '',
      published_at: source.published_at || source.published || '',
      url: source.url || '#',
      tag: source.tag || tag,
    };
  }

  function buildEvidenceSources(data) {
    const evidence = ensureArray(ensureObject(data.analysis_card).evidence);
    const direct = ensureArray(data.direct_event_news);
    const background = ensureArray(data.background_news);
    const transcript = ensureObject(data.transcript_trace);
    const leadTranscript = ensureObject(transcript.lead_candidate);

    const queue = [];
    direct.slice(0, 2).forEach((item) => {
      queue.push({
        sourceType: 'direct',
        sourceLabel: item.source || 'Direct source',
        tag: 'DIRECT',
        headline: item.headline || '',
      });
    });
    if (leadTranscript.event_title || leadTranscript.source_ref) {
      queue.push({
        sourceType: 'transcript',
        sourceLabel: leadTranscript.source_ref || leadTranscript.event_title || 'Transcript',
        tag: 'TRANSCRIPT',
        headline: leadTranscript.event_title || '',
      });
    }
    background.slice(0, 2).forEach((item) => {
      queue.push({
        sourceType: 'background',
        sourceLabel: item.source || 'Background source',
        tag: 'BG',
        headline: item.headline || '',
      });
    });

    if (!queue.length) {
      queue.push({
        sourceType: 'background',
        sourceLabel: 'No linked source yet',
        tag: 'BG',
        headline: '',
      });
    }

    return evidence.map((_, idx) => ({
      evidenceIdx: idx,
      ...queue[Math.min(idx, queue.length - 1)],
    }));
  }

  function normalizeWorkspaceData(payload) {
    const raw = ensureObject(payload);
    const hasOwn = (key) => Object.prototype.hasOwnProperty.call(raw, key);
    const analysisCard = ensureObject(raw.analysis_card);
    const transcriptTrace = ensureObject(raw.transcript_trace);
    const leadCandidate = ensureObject(transcriptTrace.lead_candidate);
    const retrievalHits = ensureArray(transcriptTrace.retrieval_hits).map((item) => {
      const hit = ensureObject(item);
      return {
        chunk_id: hit.chunk_id || hit.id || '',
        document_id: hit.document_id || hit.transcript_id || '',
        chunk_index: hit.chunk_index || hit.segment_index || '',
        source_file: hit.source_file || hit.source_ref || '',
        speaker: hit.speaker || '',
        event: hit.event || hit.event_title || '',
        text: hit.text || '',
        start_ts: hit.start_ts || '',
        end_ts: hit.end_ts || '',
      };
    });

    const normalized = {
      query: raw.query || DEFAULT_WORKSPACE_DATA.query,
      analysis_card: {
        thesis: analysisCard.thesis || DEFAULT_WORKSPACE_DATA.analysis_card.thesis,
        evidence: ensureArray(analysisCard.evidence).filter(Boolean).length
          ? ensureArray(analysisCard.evidence).filter(Boolean)
          : DEFAULT_WORKSPACE_DATA.analysis_card.evidence,
        uncertainty: analysisCard.uncertainty || DEFAULT_WORKSPACE_DATA.analysis_card.uncertainty,
        risk: analysisCard.risk || DEFAULT_WORKSPACE_DATA.analysis_card.risk,
        next_check: analysisCard.next_check || DEFAULT_WORKSPACE_DATA.analysis_card.next_check,
        action: analysisCard.action || DEFAULT_WORKSPACE_DATA.analysis_card.action,
        fair_value_view: analysisCard.fair_value_view || DEFAULT_WORKSPACE_DATA.analysis_card.fair_value_view,
      },
      direct_event_news: ensureArray(raw.direct_event_news).map((item) => normalizeNewsItem(item, 'direct')),
      background_news: ensureArray(raw.background_news).map((item) => normalizeNewsItem(item, 'background')),
      transcript_trace: {
        lead_candidate: {
          transcript_id: leadCandidate.transcript_id || '',
          segment_index: leadCandidate.segment_index || '',
          source_ref: leadCandidate.source_ref || '',
          event_title: leadCandidate.event_title || leadCandidate.event || DEFAULT_WORKSPACE_DATA.transcript_trace.lead_candidate.event_title,
          event_date: leadCandidate.event_date || '',
          start_ts: leadCandidate.start_ts || '',
          end_ts: leadCandidate.end_ts || '',
          speaker: leadCandidate.speaker || transcriptTrace.excerpt_speaker || '',
        },
        retrieval_hits: retrievalHits,
        excerpt: transcriptTrace.excerpt || (retrievalHits[0] && retrievalHits[0].text) || DEFAULT_WORKSPACE_DATA.transcript_trace.excerpt,
        excerpt_speaker: transcriptTrace.excerpt_speaker || leadCandidate.speaker || (retrievalHits[0] && retrievalHits[0].speaker) || DEFAULT_WORKSPACE_DATA.transcript_trace.excerpt_speaker,
      },
      ranking_debug: ensureObject(raw.ranking_debug),
      context_risks: ensureArray(raw.context_risks),
      debug_view: ensureObject(raw.debug_view),
      evidence_sources: ensureArray(raw.evidence_sources),
    };

    if (!hasOwn('direct_event_news') && !normalized.direct_event_news.length) {
      normalized.direct_event_news = DEFAULT_WORKSPACE_DATA.direct_event_news;
    }
    if (!hasOwn('background_news') && !normalized.background_news.length) {
      normalized.background_news = DEFAULT_WORKSPACE_DATA.background_news;
    }
    if (
      !hasOwn('transcript_trace')
      && !normalized.transcript_trace.retrieval_hits.length
    ) {
      normalized.transcript_trace.retrieval_hits = DEFAULT_WORKSPACE_DATA.transcript_trace.retrieval_hits;
      normalized.transcript_trace.excerpt = DEFAULT_WORKSPACE_DATA.transcript_trace.excerpt;
      normalized.transcript_trace.excerpt_speaker = DEFAULT_WORKSPACE_DATA.transcript_trace.excerpt_speaker;
      normalized.transcript_trace.lead_candidate = DEFAULT_WORKSPACE_DATA.transcript_trace.lead_candidate;
    }
    if (!hasOwn('ranking_debug') && !Object.keys(normalized.ranking_debug).length) {
      normalized.ranking_debug = DEFAULT_WORKSPACE_DATA.ranking_debug;
    }
    if (!hasOwn('context_risks') && !normalized.context_risks.length) {
      normalized.context_risks = DEFAULT_WORKSPACE_DATA.context_risks;
    }
    if (!hasOwn('debug_view') && !Object.keys(normalized.debug_view).length) {
      normalized.debug_view = DEFAULT_WORKSPACE_DATA.debug_view;
    }
    if (!normalized.evidence_sources.length) normalized.evidence_sources = buildEvidenceSources(normalized);

    return normalized;
  }

  function hydrateWorkspaceGlobals(payload) {
    const normalized = normalizeWorkspaceData(payload);
    window.__WORKSPACE_DATA__ = normalized;
    window.__WORKSPACE_SOURCE__ = payload === DEFAULT_WORKSPACE_DATA ? 'demo' : 'runtime';
    window.QUERY = normalized.query;
    window.ANALYSIS_CARD = normalized.analysis_card;
    window.DIRECT_NEWS = normalized.direct_event_news;
    window.BACKGROUND_NEWS = normalized.background_news;
    window.TRANSCRIPT_TRACE = normalized.transcript_trace;
    window.RANKING_DEBUG = normalized.ranking_debug;
    window.CONTEXT_RISKS = normalized.context_risks;
    window.DEBUG_VIEW = normalized.debug_view;
    window.EVIDENCE_SOURCES = normalized.evidence_sources;
    return normalized;
  }

  async function loadWorkspaceData(explicitUrl) {
    const params = new URLSearchParams(window.location.search);
    const dataUrl = explicitUrl || params.get('data') || './ui/workspace-data.json';
    try {
      const response = await fetch(dataUrl, { cache: 'no-store' });
      if (response.ok) {
        const payload = await response.json();
        return hydrateWorkspaceGlobals(payload);
      }
    } catch (_error) {
      // Fallback to baked demo payload when no exported workspace data exists.
    }
    return hydrateWorkspaceGlobals(DEFAULT_WORKSPACE_DATA);
  }

  window.DEFAULT_WORKSPACE_DATA = DEFAULT_WORKSPACE_DATA;
  window.hydrateWorkspaceGlobals = hydrateWorkspaceGlobals;
  window.loadWorkspaceData = loadWorkspaceData;

  hydrateWorkspaceGlobals(DEFAULT_WORKSPACE_DATA);
})();
