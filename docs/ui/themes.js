// Theme variants for the terminal direction
// variant: 'default' | 'calmer' | 'notebook'
window.getTheme = function(variant) {
  const base = {
    fonts: {
      display: "'IBM Plex Sans', sans-serif",
      body: "'IBM Plex Sans', sans-serif",
      mono: "'JetBrains Mono', monospace"
    },
    colors: {
      bg: "#0F1117",
      surface: "#161920",
      surfaceAlt: "#1C1F2A",
      surfaceDeep: "#0D0F14",
      border: "#252838",
      borderStrong: "#353950",
      text: "#E2E4EA",
      textSecondary: "#8B8FA3",
      textTertiary: "#5C6078",
      accent: "#4DA3FF",
      accentBg: "#142440",
      accentText: "#70B8FF",
      direct: "#00D68F",
      directBg: "#0A2A1E",
      directBorder: "#0D3D2B",
      background_tag: "#7B7F93",
      backgroundBg: "#1A1D28",
      backgroundBorder: "#282B3A",
      transcript: "#C4A0FF",
      transcriptBg: "#1A1530",
      transcriptBorder: "#2A2045",
      risk: "#FF6B6B",
      riskBg: "#2A1515",
      riskBorder: "#3D1F1F",
      uncertainty: "#FFB547",
      uncertaintyBg: "#2A2010",
      uncertaintyBorder: "#3D301A",
      debugBg: "#0C0E14",
      debugBorder: "#1E2130",
      panelHeader: "#E2E4EA",
    },
    radius: "2px",
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
      surface: "#171A22",
      surfaceAlt: "#1D2030",
    };
  }

  return base;
};
