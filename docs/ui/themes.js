// Theme variants for the research workspace direction
// variant: 'default' | 'calmer' | 'notebook'
window.getTheme = function(variant) {
  const base = {
    fonts: {
      display: "'IBM Plex Sans', sans-serif",
      body: "'IBM Plex Sans', sans-serif",
      mono: "'JetBrains Mono', monospace"
    },
    colors: {
      bg: "#12100F",
      surface: "#1C1917",
      surfaceAlt: "#24211E",
      surfaceDeep: "#0E0C0B",
      border: "#2B2622",
      borderStrong: "#3A332E",
      text: "#EEE6DE",
      textSecondary: "#A89E93",
      textTertiary: "#72685F",
      accent: "#4DA3FF",
      accentBg: "#21314A",
      accentText: "#9DC7FF",
      direct: "#78D39D",
      directBg: "#1F3425",
      directBorder: "#2F4A34",
      background_tag: "#B0A89E",
      backgroundBg: "#26211E",
      backgroundBorder: "#38312C",
      transcript: "#B69BE7",
      transcriptBg: "#241F31",
      transcriptBorder: "#3A314B",
      risk: "#E39185",
      riskBg: "#35211E",
      riskBorder: "#4A2E29",
      uncertainty: "#D1B060",
      uncertaintyBg: "#312918",
      uncertaintyBorder: "#463B23",
      debugBg: "#14110F",
      debugBorder: "#27221E",
      panelHeader: "#EEE6DE",
    },
    radius: "16px",
    radiusSm: "12px",
    radiusXl: "24px",
    radiusPill: "999px",
  };

  if (variant === 'calmer') {
    base.colors = {
      ...base.colors,
      bg: "#12141A",
      surface: "#181B24",
      surfaceAlt: "#1E212C",
      surfaceDeep: "#10121A",
      border: "#222638",
      borderStrong: "#2E3248",
      text: "#D0D3DE",
      textSecondary: "#7E829A",
      textTertiary: "#555972",
      accent: "#5BA0E0",
      accentBg: "#162438",
      direct: "#2EC08A",
      directBg: "#0D2820",
      directBorder: "#14382C",
      transcript: "#B090E0",
      transcriptBg: "#18142A",
      transcriptBorder: "#261E3A",
      risk: "#E07070",
      riskBg: "#241818",
      uncertainty: "#E0A848",
      uncertaintyBg: "#241E10",
      debugBg: "#0F1118",
    };
  }

  if (variant === 'notebook') {
    base.fonts = {
      display: "'IBM Plex Sans', sans-serif",
      body: "'IBM Plex Sans', sans-serif",
      mono: "'JetBrains Mono', monospace",
      serif: "'Source Serif 4', serif"
    };
    base.colors = {
      ...base.colors,
      bg: "#161210",
      surface: "#24201D",
      surfaceAlt: "#2B2622",
      surfaceDeep: "#110E0C",
      border: "#342E29",
      borderStrong: "#463E38",
      text: "#F1E8DE",
      textSecondary: "#B2A79B",
      textTertiary: "#7D7268",
      accent: "#8DB3FF",
      accentBg: "#2A3A54",
      accentText: "#C0D7FF",
      direct: "#8ADDAB",
      directBg: "#233A29",
      directBorder: "#3A5840",
      background_tag: "#C6BCB1",
      backgroundBg: "#302925",
      backgroundBorder: "#433A34",
      transcript: "#C3A7F0",
      transcriptBg: "#2A2438",
      transcriptBorder: "#453A57",
      risk: "#E5A094",
      riskBg: "#3A2621",
      riskBorder: "#53352F",
      uncertainty: "#DABD75",
      uncertaintyBg: "#3B311C",
      uncertaintyBorder: "#55482A",
      debugBg: "#1A1512",
      debugBorder: "#2C2621",
    };
  }

  return base;
};
