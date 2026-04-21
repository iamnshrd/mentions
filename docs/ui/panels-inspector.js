// v3 Inspector + Debug — rounded, warm, NotebookLM-inspired
function InspectorPanel({ selectedSource }) {
  const t = useTheme();
  const c = t.colors;
  const variant = useVariant();
  const isCalmer = variant === 'calmer';

  const label = (text, color) => ({
    fontSize: '10px', fontFamily: t.fonts.mono, fontWeight: 600,
    letterSpacing: '0.5px', color: color || c.textTertiary, marginBottom: '6px',
  });

  const kv = (k, v, color) => (
    <div style={{ marginBottom: '6px' }}>
      <div style={{ fontFamily: t.fonts.mono, fontSize: '10px', color: c.textTertiary }}>{k}</div>
      <div style={{ fontFamily: t.fonts.mono, fontSize: '11px', color: color || c.text, marginTop: '1px' }}>{v}</div>
    </div>
  );

  const lc = TRANSCRIPT_TRACE.lead_candidate;
  const rh = TRANSCRIPT_TRACE.retrieval_hits[0];
  const transcriptExcerpt = TRANSCRIPT_TRACE.excerpt || (rh && rh.text) || '';
  const excerptSpeaker = TRANSCRIPT_TRACE.excerpt_speaker || lc.speaker || (rh && rh.speaker) || '';
  const noSel = !selectedSource;
  const rankMatch = selectedSource?.headline
    ? RANKING_DEBUG.top_ranked.find(r => r.headline === selectedSource.headline) : null;

  return (
    <div style={{
      background: c.bg, display: 'flex', flexDirection: 'column',
      overflow: 'hidden', minWidth: 0, padding: '8px 8px 8px 0',
    }}>
      <div style={{
        background: c.surface, borderRadius: t.radiusXl,
        display: 'flex', flexDirection: 'column', overflow: 'hidden', flex: 1,
      }}>
        <div style={{
          padding: '16px 16px 12px',
          display: 'flex', alignItems: 'center', gap: '8px',
        }}>
          <span style={{ fontFamily: t.fonts.body, fontSize: '14px', fontWeight: 600, color: c.panelHeader }}>Inspector</span>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: isCalmer ? '4px 16px 16px' : '4px 14px 14px' }}>
          {noSel ? (
            <div style={{ textAlign: 'center', padding: '48px 20px', color: c.textTertiary }}>
              <div style={{ fontSize: '32px', opacity: 0.15, marginBottom: '12px' }}>◎</div>
              <div style={{ fontFamily: t.fonts.body, fontSize: '13px', lineHeight: 1.6 }}>
                Select a source to inspect its provenance and evidence chain.
              </div>
            </div>
          ) : selectedSource?.type === 'transcript' ? (
            <>
              <div style={{
                padding: '14px', background: c.transcriptBg,
                borderRadius: t.radius, marginBottom: '12px',
              }}>
                <div style={label('Lead Transcript Segment', c.transcript)}>Lead Transcript Segment</div>
                <div style={{ fontFamily: t.fonts.display, fontSize: '13px', color: c.text, lineHeight: 1.5, marginBottom: '10px' }}>
                  {lc.event_title}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                  {kv('Segment', '#' + lc.segment_index)}
                  {kv('Timecode', lc.start_ts + ' → ' + lc.end_ts)}
                  {kv('Date', lc.event_date)}
                  {kv('Ref', lc.source_ref, c.accent)}
                </div>
              </div>

              <div style={{ ...label('Retrieval Chain'), marginBottom: '8px' }}>Retrieval Chain</div>
              {TRANSCRIPT_TRACE.retrieval_hits.map((hit, i) => (
                <div key={i} style={{
                  padding: '10px 12px', background: c.surfaceAlt,
                  borderRadius: t.radiusSm, marginBottom: '6px',
                  fontFamily: t.fonts.mono, fontSize: '10px',
                }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                    <div><span style={{ color: c.textTertiary }}>chunk:</span> <span style={{ color: c.accent }}>{hit.chunk_id}</span></div>
                    <div><span style={{ color: c.textTertiary }}>doc:</span> {hit.document_id}</div>
                    <div><span style={{ color: c.textTertiary }}>speaker:</span> {hit.speaker}</div>
                    <div><span style={{ color: c.textTertiary }}>file:</span> {hit.source_file}</div>
                  </div>
                </div>
              ))}

              <div style={{ ...label('Excerpt'), marginTop: '12px', marginBottom: '6px' }}>Excerpt</div>
              <div style={{
                padding: '12px 14px', background: c.surfaceDeep,
                borderRadius: t.radius, borderLeft: `3px solid ${c.transcript}`,
                fontFamily: t.fonts.mono, fontSize: '11px', lineHeight: 1.7, color: c.text,
              }}>
                <div style={{ color: c.textTertiary, fontSize: '10px', marginBottom: '6px' }}>
                  [{lc.start_ts}] {excerptSpeaker}
                </div>
                {transcriptExcerpt ? `"${transcriptExcerpt}"` : 'No transcript excerpt available yet.'}
                <div style={{ color: c.textTertiary, fontSize: '10px', marginTop: '8px', fontStyle: 'italic', borderTop: `1px solid ${c.border}`, paddingTop: '6px' }}>
                  Reconstructed from retrieval chunks when exact transcript text is unavailable
                </div>
              </div>

              <div style={{ ...label('Provenance'), marginTop: '14px', marginBottom: '6px' }}>Provenance</div>
              <div style={{ fontFamily: t.fonts.mono, fontSize: '10px', color: c.textTertiary, lineHeight: 1.8, background: c.surfaceAlt, padding: '10px 12px', borderRadius: t.radiusSm }}>
                <div>transcript_id: <span style={{ color: c.text }}>{lc.transcript_id}</span></div>
                <div>source_ref: <span style={{ color: c.accent }}>{lc.source_ref}</span></div>
                <div>segment: <span style={{ color: c.text }}>{lc.segment_index}</span></div>
              </div>
            </>
          ) : (
            <>
              <div style={{
                padding: '14px',
                background: selectedSource?.tag === 'direct' ? c.directBg : c.backgroundBg,
                borderRadius: t.radius, marginBottom: '12px',
              }}>
                <div style={label(
                  selectedSource?.tag === 'direct' ? 'Direct Event Source' : 'Background Source',
                  selectedSource?.tag === 'direct' ? c.direct : c.textSecondary
                )}>
                  {selectedSource?.tag === 'direct' ? 'Direct Event Source' : 'Background Source'}
                </div>
                <div style={{ fontFamily: t.fonts.display, fontSize: '13px', color: c.text, lineHeight: 1.5, marginBottom: '10px' }}>
                  {selectedSource?.headline}
                </div>
                {kv('Publisher', selectedSource?.source)}
                {kv('Published', selectedSource?.published_at ? new Date(selectedSource.published_at).toLocaleString() : '')}
              </div>

              <div style={{ ...label('Ranking'), marginBottom: '6px' }}>Ranking</div>
              <div style={{
                padding: '10px 12px', background: c.surfaceAlt,
                borderRadius: t.radiusSm, fontFamily: t.fonts.mono, fontSize: '11px', marginBottom: '12px',
              }}>
                {rankMatch ? (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <span style={{ color: c.textTertiary }}>relevance:</span>
                      <span style={{ color: c.accent, fontWeight: 700, fontSize: '16px' }}>{rankMatch.final_relevance_score}</span>
                      <span style={{ padding: '2px 8px', background: c.directBg, color: c.direct, borderRadius: t.radiusPill, fontSize: '10px' }}>kept</span>
                    </div>
                    <div style={{ color: c.textTertiary, fontSize: '10px' }}>
                      noise_flags: {rankMatch.noise_flags.length === 0 ? 'none' : rankMatch.noise_flags.join(', ')}
                    </div>
                  </div>
                ) : (
                  <span style={{ color: c.textTertiary }}>No direct ranking match — background source</span>
                )}
              </div>

              <div style={{ ...label('Coverage'), marginBottom: '6px' }}>Coverage</div>
              <div style={{
                padding: '10px 12px', background: c.surfaceAlt,
                borderRadius: t.radiusSm, fontFamily: t.fonts.mono, fontSize: '10px', lineHeight: 1.8, color: c.textTertiary,
              }}>
                <div>state: <span style={{ color: c.text }}>{RANKING_DEBUG.typed_coverage.coverage_state}</span></div>
                <div>core: <span style={{ color: c.direct }}>{RANKING_DEBUG.typed_coverage.core_count}</span> · expansion: {RANKING_DEBUG.typed_coverage.expansion_count} · ambient: {RANKING_DEBUG.typed_coverage.ambient_count}</div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// v3 Debug Drawer — softer, rounded
function DebugDrawer({ isOpen, onToggle }) {
  const t = useTheme();
  const c = t.colors;
  const db = DEBUG_VIEW;
  const rk = RANKING_DEBUG;
  const lb = { fontSize: '9px', fontFamily: t.fonts.mono, fontWeight: 600, letterSpacing: '0.5px', color: c.textTertiary };

  return (
    <div style={{
      background: c.bg, padding: '0 8px 8px',
      flexShrink: 0,
    }}>
      <div style={{
        background: c.debugBg, borderRadius: isOpen ? t.radius : t.radiusSm,
        overflow: 'hidden',
        transition: 'all 0.2s ease',
      }}>
        <div onClick={onToggle} style={{
          padding: '8px 16px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: '8px',
          fontFamily: t.fonts.mono, fontSize: '10px', fontWeight: 600,
          color: c.textTertiary, userSelect: 'none',
        }}>
          <span style={{ transform: isOpen ? 'rotate(90deg)' : 'rotate(0)', transition: 'transform 0.15s', display: 'inline-block', fontSize: '8px' }}>▶</span>
          Provenance
          <span style={{
            padding: '2px 8px', fontSize: '9px', borderRadius: t.radiusPill,
            background: c.directBg, color: c.direct,
          }}>{db.runtime_health.news.status === 'ok' ? 'OK' : '!'}</span>
          <span style={{ marginLeft: 'auto', fontSize: '10px' }}>
            {rk.ranking_summary.kept_count}/{rk.ranking_summary.ranked_count} kept
          </span>
        </div>
        {isOpen && (
          <div style={{ padding: '4px 16px 12px' }}>
            <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
              {[
                ['News', db.summary.news_count], ['Transcripts', db.summary.transcript_count],
                ['Ranked', rk.ranking_summary.ranked_count], ['Kept', rk.ranking_summary.kept_count],
                ['Rejected', rk.ranking_summary.rejected_count], ['Mode', rk.typed_coverage.coverage_state],
              ].map(([l, v], i) => (
                <div key={i} style={{ padding: '6px 10px', background: c.surface, borderRadius: t.radiusSm, minWidth: '80px' }}>
                  <div style={lb}>{l}</div>
                  <div style={{ fontFamily: t.fonts.mono, fontSize: '14px', fontWeight: 700, color: typeof v === 'number' && v > 0 ? c.direct : c.text }}>{v}</div>
                </div>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div>
                <div style={{ ...lb, marginBottom: '3px' }}>Kept</div>
                {rk.top_ranked.map((r, i) => (
                  <div key={i} style={{ fontFamily: t.fonts.mono, fontSize: '10px', color: c.text, lineHeight: 1.6 }}>
                    <span style={{ color: c.direct }}>●</span> {r.headline.substring(0, 42)}… <span style={{ color: c.accent }}>{r.final_relevance_score}</span>
                  </div>
                ))}
              </div>
              <div>
                <div style={{ ...lb, marginBottom: '3px' }}>Rejected</div>
                {rk.top_rejected.map((r, i) => (
                  <div key={i} style={{ fontFamily: t.fonts.mono, fontSize: '10px', color: c.textTertiary, lineHeight: 1.6 }}>
                    <span style={{ color: c.risk }}>●</span> {r.headline.substring(0, 42)}… {r.final_relevance_score}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { InspectorPanel, DebugDrawer });
