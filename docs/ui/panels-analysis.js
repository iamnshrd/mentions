// v3 Analysis Panel — rounded, spacious, NotebookLM-inspired
function AnalysisPanel({
  onInspectEvidence,
  queryInput,
  onQueryInputChange,
  onSubmitQuery,
  loading,
  error,
}) {
  const t = useTheme();
  const c = t.colors;
  const variant = useVariant();
  const d = ANALYSIS_CARD;
  const isCalmer = variant === 'calmer';
  const isNb = variant === 'notebook';

  const label = (text, color) => ({
    fontSize: '10px', fontFamily: t.fonts.mono, fontWeight: 600,
    letterSpacing: '0.5px', color: color || c.textTertiary, marginBottom: '8px',
  });

  return (
    <div style={{
      background: c.bg,
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden', minWidth: 0,
      padding: '8px 0',
    }}>
      <div style={{
        background: c.surface, borderRadius: t.radiusXl,
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden', flex: 1,
      }}>
        {/* Query */}
        <div style={{
          padding: isCalmer ? '20px 24px' : '16px 20px',
          borderBottom: `1px solid ${c.border}`,
        }}>
          <div style={{ ...label(''), marginBottom: '6px', fontSize: '10px' }}>Research Query</div>
          <form onSubmit={onSubmitQuery}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'stretch' }}>
              <input
                value={queryInput}
                onChange={(event) => onQueryInputChange && onQueryInputChange(event.target.value)}
                placeholder="Ask a question or paste a market URL"
                style={{
                  flex: 1,
                  minWidth: 0,
                  background: c.surfaceAlt,
                  color: c.text,
                  border: `1px solid ${error ? c.riskBorder : c.border}`,
                  borderRadius: t.radiusSm,
                  padding: isCalmer ? '12px 14px' : '11px 13px',
                  fontFamily: t.fonts.body,
                  fontSize: isCalmer ? '14px' : '13px',
                  outline: 'none',
                }}
              />
              <button type="submit" disabled={loading} style={{
                padding: '0 16px',
                minWidth: '108px',
                border: 'none',
                borderRadius: t.radiusPill,
                background: loading ? c.borderStrong : c.accentBg,
                color: loading ? c.textSecondary : c.accentText,
                fontFamily: t.fonts.mono,
                fontSize: '11px',
                fontWeight: 700,
                cursor: loading ? 'default' : 'pointer',
              }}>
                {loading ? 'Running…' : 'Run Analysis'}
              </button>
            </div>
          </form>
          {error ? (
            <div style={{
              marginTop: '10px',
              padding: '9px 12px',
              background: c.riskBg,
              borderRadius: t.radiusSm,
              color: c.risk,
              fontFamily: t.fonts.body,
              fontSize: '12px',
              lineHeight: 1.5,
            }}>
              {error}
            </div>
          ) : (
            <div style={{
              marginTop: '10px',
              fontFamily: t.fonts.display, fontSize: isCalmer ? '17px' : '15px',
              fontWeight: 500, color: c.text, lineHeight: 1.45,
            }}>{QUERY}</div>
          )}
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: isCalmer ? '20px 24px' : '16px 20px' }}>
          {/* Thesis */}
          <div style={{
            padding: isCalmer ? '16px 18px' : '14px 16px',
            background: c.accentBg,
            borderRadius: t.radius, marginBottom: isCalmer ? '20px' : '16px',
          }}>
            <div style={label('Thesis', c.accent)}>Thesis</div>
            <div style={{
              fontFamily: isNb ? (t.fonts.serif || t.fonts.display) : t.fonts.display,
              fontSize: isCalmer ? '15px' : '14px',
              lineHeight: 1.6, color: c.text, fontWeight: 400,
            }}>{d.thesis}</div>
          </div>

          {/* Evidence */}
          <div style={{ marginBottom: isCalmer ? '20px' : '16px' }}>
            <div style={label('Evidence · ' + d.evidence.length)}>Evidence · {d.evidence.length}</div>
            {d.evidence.map((e, i) => {
              const src = EVIDENCE_SOURCES[i];
              const srcColor = src?.sourceType === 'direct' ? c.direct :
                               src?.sourceType === 'transcript' ? c.transcript : c.textSecondary;
              const srcBg = src?.sourceType === 'direct' ? c.directBg :
                            src?.sourceType === 'transcript' ? c.transcriptBg : c.backgroundBg;
              return (
                <div key={i}
                  onClick={() => onInspectEvidence && onInspectEvidence(src)}
                  style={{
                    padding: isCalmer ? '12px 14px' : '10px 12px',
                    background: c.surfaceAlt,
                    borderRadius: t.radiusSm,
                    marginBottom: '6px', cursor: 'pointer',
                    transition: 'background 0.12s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = c.borderStrong}
                  onMouseLeave={e => e.currentTarget.style.background = c.surfaceAlt}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                    <span style={{
                      fontFamily: t.fonts.mono, fontSize: '10px', fontWeight: 700,
                      color: c.accent,
                    }}>E{i+1}</span>
                    <span style={{
                      padding: '2px 8px', fontSize: '10px', fontFamily: t.fonts.mono, fontWeight: 600,
                      borderRadius: t.radiusPill, background: srcBg, color: srcColor,
                    }}>{src?.sourceType === 'direct' ? 'Direct' : src?.sourceType === 'transcript' ? 'Transcript' : 'Background'}</span>
                    <span style={{ fontFamily: t.fonts.mono, fontSize: '10px', color: c.textTertiary }}>
                      {src?.sourceLabel}
                    </span>
                    <span style={{ marginLeft: 'auto', fontSize: '10px', color: c.textTertiary }}>→</span>
                  </div>
                  <div style={{
                    fontFamily: t.fonts.body, fontSize: isCalmer ? '13px' : '12.5px',
                    lineHeight: 1.55, color: c.text, paddingLeft: '28px',
                  }}>{e}</div>
                </div>
              );
            })}
          </div>

          {/* Uncertainty + Risk */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: isCalmer ? '20px' : '16px' }}>
            <div style={{
              padding: isCalmer ? '14px' : '12px',
              background: c.uncertaintyBg, borderRadius: t.radius,
            }}>
              <div style={label('Uncertainty', c.uncertainty)}>Uncertainty</div>
              <div style={{ fontFamily: t.fonts.body, fontSize: isCalmer ? '12.5px' : '12px', lineHeight: 1.55, color: c.text }}>{d.uncertainty}</div>
            </div>
            <div style={{
              padding: isCalmer ? '14px' : '12px',
              background: c.riskBg, borderRadius: t.radius,
            }}>
              <div style={label('Risk', c.risk)}>Risk</div>
              <div style={{ fontFamily: t.fonts.body, fontSize: isCalmer ? '12.5px' : '12px', lineHeight: 1.55, color: c.text }}>{d.risk}</div>
            </div>
          </div>

          {/* Next Check + Action */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: isCalmer ? '20px' : '16px' }}>
            <div style={{
              padding: isCalmer ? '14px' : '12px',
              background: c.surfaceAlt, borderRadius: t.radius,
            }}>
              <div style={label('Next Check')}>Next Check</div>
              <div style={{ fontFamily: t.fonts.body, fontSize: isCalmer ? '12.5px' : '12px', lineHeight: 1.55, color: c.text }}>{d.next_check}</div>
            </div>
            <div style={{
              padding: isCalmer ? '14px' : '12px',
              background: c.surfaceAlt, borderRadius: t.radius,
            }}>
              <div style={label('Action')}>Action</div>
              <div style={{ fontFamily: t.fonts.body, fontSize: isCalmer ? '12.5px' : '12px', lineHeight: 1.55, color: c.text }}>{d.action}</div>
            </div>
          </div>

          {/* Fair value + context risks */}
          <div style={{
            padding: '10px 12px', borderTop: `1px solid ${c.border}`,
            fontFamily: t.fonts.mono, fontSize: '11px', color: c.textTertiary,
            fontStyle: 'italic',
          }}>{d.fair_value_view}</div>
          <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
            {CONTEXT_RISKS.map((r, i) => (
              <span key={i} style={{
                padding: '3px 10px', fontSize: '10px', fontFamily: t.fonts.mono,
                borderRadius: t.radiusPill, background: c.riskBg, color: c.risk,
              }}>{r}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AnalysisPanel });
