// v3 Source Panel — NotebookLM-inspired warm rounded style
const { useState, useEffect, useContext, createContext, useRef, useCallback } = React;
const ThemeContext = createContext();
const useTheme = () => useContext(ThemeContext);
const VariantContext = createContext('default');
const useVariant = () => useContext(VariantContext);

function timeAgo(dateStr) {
  const d = new Date(dateStr);
  const now = new Date('2026-04-21T00:00:00Z');
  const h = Math.floor((now - d) / 3600000);
  if (h < 1) return 'just now';
  if (h < 24) return h + 'h ago';
  return Math.floor(h / 24) + 'd ago';
}

function SourceGroupHeader({ icon, label, count, color, t, c }) {
  return (
    <div style={{
      padding: '10px 16px 6px',
      display: 'flex', alignItems: 'center', gap: '8px',
    }}>
      <span style={{
        fontFamily: t.fonts.body, fontSize: '11px', fontWeight: 600,
        letterSpacing: '0.3px', color,
      }}>{icon} {label}</span>
      <span style={{
        marginLeft: 'auto', fontFamily: t.fonts.mono, fontSize: '10px',
        color: c.textTertiary,
      }}>{count}</span>
    </div>
  );
}

function SourceCard({ item, isSelected, isDirect, isTranscript, onClick, t, c, variant }) {
  const [hovered, setHovered] = useState(false);
  const typeColor = isTranscript ? c.transcript : isDirect ? c.direct : c.textSecondary;
  const isNb = variant === 'notebook';

  return (
    <div onClick={onClick}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
      style={{
        padding: '10px 14px',
        margin: '0 8px 4px',
        cursor: 'pointer',
        background: isSelected ? c.surfaceAlt : hovered ? c.surfaceAlt + '80' : 'transparent',
        borderRadius: t.radiusSm,
        transition: 'all 0.15s ease',
      }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '5px' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: '3px',
          padding: '2px 8px', fontSize: '10px', fontFamily: t.fonts.mono, fontWeight: 600,
          borderRadius: t.radiusPill,
          background: isTranscript ? c.transcriptBg : isDirect ? c.directBg : c.backgroundBg,
          color: typeColor,
        }}>
          {isTranscript ? 'Transcript' : isDirect ? 'Direct' : 'Background'}
        </span>
        <span style={{ fontSize: '10px', color: c.textTertiary, fontFamily: t.fonts.mono }}>
          {item.published_at ? timeAgo(item.published_at) : item.start_ts + '–' + item.end_ts}
        </span>
      </div>
      <div style={{
        fontFamily: isNb ? (t.fonts.serif || t.fonts.body) : t.fonts.body,
        fontSize: '13px',
        fontWeight: 400, lineHeight: 1.5, color: c.text,
        marginBottom: '3px',
      }}>{item.headline || item.event_title}</div>
      <div style={{
        fontFamily: t.fonts.mono, fontSize: '10px', color: c.textTertiary,
        display: 'flex', alignItems: 'center', gap: '6px',
      }}>
        {item.source || ('Speaker: ' + (item.speaker || ''))}
      </div>
    </div>
  );
}

function SourcePanel({ selectedSource, onSelectSource }) {
  const t = useTheme();
  const c = t.colors;
  const variant = useVariant();

  const transcriptItem = {
    type: 'transcript',
    ...TRANSCRIPT_TRACE.lead_candidate,
    speaker: TRANSCRIPT_TRACE.retrieval_hits[0].speaker,
  };

  const isSourceSelected = (item) => {
    if (item.type === 'transcript') return selectedSource?.type === 'transcript';
    return selectedSource?.headline === item.headline;
  };

  return (
    <div style={{
      background: c.bg,
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden', minWidth: 0,
      padding: '8px 0 8px 8px',
    }}>
      <div style={{
        background: c.surface,
        borderRadius: t.radiusXl,
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden', flex: 1,
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 16px 12px',
          display: 'flex', alignItems: 'center', gap: '8px',
        }}>
          <span style={{
            fontFamily: t.fonts.body, fontSize: '14px', fontWeight: 600,
            color: c.panelHeader,
          }}>Sources</span>
          <span style={{
            marginLeft: 'auto', fontFamily: t.fonts.mono, fontSize: '11px',
            color: c.textTertiary, background: c.surfaceAlt,
            padding: '2px 8px', borderRadius: t.radiusPill,
          }}>{DIRECT_NEWS.length + BACKGROUND_NEWS.length + 1}</span>
        </div>

        {/* Scrollable */}
        <div style={{ flex: 1, overflowY: 'auto', paddingBottom: '8px' }}>
          <SourceGroupHeader icon="◆" label="Direct Event" count={DIRECT_NEWS.length} color={c.direct} t={t} c={c} />
          {DIRECT_NEWS.map((n, i) => (
            <SourceCard key={'d'+i} item={n} isSelected={isSourceSelected(n)} isDirect={true}
              onClick={() => onSelectSource(n)} t={t} c={c} variant={variant} />
          ))}

          <SourceGroupHeader icon="▸" label="Transcript" count={1} color={c.transcript} t={t} c={c} />
          <SourceCard item={transcriptItem} isSelected={isSourceSelected(transcriptItem)} isTranscript={true}
            onClick={() => onSelectSource(transcriptItem)} t={t} c={c} variant={variant} />

          <SourceGroupHeader icon="◇" label="Background" count={BACKGROUND_NEWS.length} color={c.textSecondary} t={t} c={c} />
          {BACKGROUND_NEWS.map((n, i) => (
            <SourceCard key={'b'+i} item={n} isSelected={isSourceSelected(n)} isDirect={false}
              onClick={() => onSelectSource(n)} t={t} c={c} variant={variant} />
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ThemeContext, useTheme, VariantContext, useVariant, SourcePanel, timeAgo });
