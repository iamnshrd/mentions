// v3 App shell — NotebookLM-inspired warm rounded layout
function App() {
  const [variant, setVariant] = React.useState(
    localStorage.getItem('mentionless-variant') || 'calmer'
  );
  const [selectedSource, setSelectedSource] = React.useState(null);
  const [debugOpen, setDebugOpen] = React.useState(false);

  const theme = window.getTheme(variant);

  React.useEffect(() => { localStorage.setItem('mentionless-variant', variant); }, [variant]);

  const [winWidth, setWinWidth] = React.useState(window.innerWidth);
  React.useEffect(() => {
    const onResize = () => setWinWidth(window.innerWidth);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const c = theme.colors;
  const isMobile = winWidth < 640;
  const isTablet = winWidth >= 640 && winWidth < 1024;
  const showThreeCol = !isMobile && !isTablet;
  const [activeTab, setActiveTab] = React.useState('analysis');

  const handleSelectSource = (s) => {
    setSelectedSource(s);
    if (isMobile || isTablet) setActiveTab('inspector');
  };

  const handleInspectEvidence = (evidenceSrc) => {
    if (!evidenceSrc) return;
    if (evidenceSrc.sourceType === 'direct') {
      const match = DIRECT_NEWS.find(n => n.headline === evidenceSrc.headline) || DIRECT_NEWS[0];
      setSelectedSource(match);
    } else if (evidenceSrc.sourceType === 'transcript') {
      setSelectedSource({ type: 'transcript', ...TRANSCRIPT_TRACE.lead_candidate });
    } else {
      setSelectedSource(BACKGROUND_NEWS[0]);
    }
  };

  return (
    <ThemeContext.Provider value={theme}>
      <VariantContext.Provider value={variant}>
        <div style={{
          width: '100vw', height: '100vh', background: c.bg,
          display: 'flex', flexDirection: 'column',
          fontFamily: theme.fonts.body, color: c.text, overflow: 'hidden',
        }}>
          {/* Top Bar */}
          <div style={{
            height: '48px', background: c.bg,
            display: 'flex', alignItems: 'center',
            padding: '0 16px', gap: '12px', flexShrink: 0,
          }}>
            <div style={{
              width: '28px', height: '28px', borderRadius: '50%',
              background: `linear-gradient(135deg, ${c.accent}, ${c.transcript})`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '13px', color: c.surfaceDeep, fontWeight: 700,
            }}>M</div>
            <span style={{
              fontFamily: theme.fonts.display, fontSize: '14px', fontWeight: 600,
              color: c.text,
            }}>Mentionless</span>
            <div style={{ flex: 1 }} />
            <span style={{
              fontFamily: theme.fonts.mono, fontSize: '10px', color: c.textTertiary,
            }}>Research Workspace</span>
            <div style={{
              padding: '4px 10px', borderRadius: theme.radiusPill,
              background: window.__WORKSPACE_SOURCE__ === 'runtime' ? c.directBg : c.backgroundBg,
              fontSize: '10px', fontFamily: theme.fonts.mono,
              color: window.__WORKSPACE_SOURCE__ === 'runtime' ? c.direct : c.textSecondary,
              fontWeight: 600,
            }}>
              {window.__WORKSPACE_SOURCE__ === 'runtime' ? 'LIVE DATA' : 'DEMO DATA'}
            </div>
            <div style={{
              padding: '4px 12px', borderRadius: theme.radiusPill,
              background: c.surface, fontSize: '11px', fontFamily: theme.fonts.body,
              color: c.textSecondary, fontWeight: 500,
            }}>v2.4.1</div>
          </div>

          {/* Mobile tab bar */}
          {(isMobile || isTablet) && (
            <div style={{
              display: 'flex', padding: '0 8px', gap: '4px', marginBottom: '4px',
            }}>
              {[
                { key: 'sources', label: 'Sources' },
                { key: 'analysis', label: 'Analysis' },
                { key: 'inspector', label: 'Inspector' },
              ].map(tab => (
                <button key={tab.key} onClick={() => setActiveTab(tab.key)} style={{
                  flex: 1, padding: '8px 0', fontSize: '11px',
                  fontFamily: theme.fonts.body, fontWeight: 600,
                  background: activeTab === tab.key ? c.surface : 'transparent',
                  color: activeTab === tab.key ? c.text : c.textTertiary,
                  border: 'none', borderRadius: theme.radiusSm,
                }}>{tab.label}</button>
              ))}
            </div>
          )}

          {/* Main workspace — 3 rounded panels with bg gaps */}
          <div style={{
            flex: 1, overflow: 'hidden',
            display: showThreeCol ? 'grid' : 'flex',
            gridTemplateColumns: showThreeCol
              ? (variant === 'notebook' ? '280px 1fr 290px' : '260px 1fr 280px')
              : undefined,
          }}>
            {(showThreeCol || activeTab === 'sources') && (
              <SourcePanel selectedSource={selectedSource} onSelectSource={handleSelectSource} />
            )}
            {(showThreeCol || activeTab === 'analysis') && (
              <AnalysisPanel onInspectEvidence={handleInspectEvidence} />
            )}
            {(showThreeCol || activeTab === 'inspector') && (
              <InspectorPanel selectedSource={selectedSource} />
            )}
          </div>

          {/* Debug Drawer */}
          <DebugDrawer isOpen={debugOpen} onToggle={() => setDebugOpen(!debugOpen)} />
        </div>
      </VariantContext.Provider>
    </ThemeContext.Provider>
  );
}

Object.assign(window, { App });
