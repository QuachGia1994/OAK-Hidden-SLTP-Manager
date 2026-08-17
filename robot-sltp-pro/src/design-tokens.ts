/**
 * ROBOT SLTP Pro - Design Tokens
 * Centralized design system foundation
 */

// Color palettes by theme
export const colors = {
  // Dark theme (default)
  dark: {
    bg: "#050b17",
    surface: "#081323",
    surface2: "#0b1728",
    surface3: "#0e1d31",
    border: "#18304b",
    borderSoft: "rgba(64, 139, 170, 0.2)",
    text: "#e6f5ff",
    muted: "#8aa0b6",
    green: "#00e899",
    greenSoft: "rgba(0, 232, 153, 0.14)",
    cyan: "#24cfff",
    cyanSoft: "rgba(36, 207, 255, 0.13)",
    amber: "#ffc04a",
    red: "#ff5d67",
    reverseBg: "rgba(139, 92, 246, 0.18)",
    reverseBorder: "#9f7aea",
    reverseText: "#ddd0ff",
    shadow: "0 16px 50px rgba(0, 0, 0, 0.28)",
  },
  // Deep Sea theme
  deepSea: {
    bg: "#020914",
    surface: "#061528",
    surface2: "#082039",
    surface3: "#0b2947",
    border: "#174267",
    borderSoft: "rgba(43, 145, 196, 0.26)",
    text: "#e9f8ff",
    muted: "#86a8bd",
    green: "#22e6c3",
    greenSoft: "rgba(34, 230, 195, 0.13)",
    cyan: "#27bfff",
    cyanSoft: "rgba(39, 191, 255, 0.14)",
    amber: "#ffc857",
    red: "#ff6873",
    reverseBg: "rgba(96, 90, 255, 0.20)",
    reverseBorder: "#8b8cff",
    reverseText: "#e3e4ff",
    shadow: "0 18px 56px rgba(0, 5, 15, 0.38)",
  },
  // Light theme
  light: {
    bg: "#eef5f8",
    surface: "#ffffff",
    surface2: "#f4f9fb",
    surface3: "#e8f2f6",
    border: "#c6d7df",
    borderSoft: "rgba(38, 111, 142, 0.18)",
    text: "#102633",
    muted: "#637d8b",
    green: "#008d68",
    greenSoft: "rgba(0, 141, 104, 0.10)",
    cyan: "#087da7",
    cyanSoft: "rgba(8, 125, 167, 0.10)",
    amber: "#b77800",
    red: "#cf3d4b",
    reverseBg: "#fff0c7",
    reverseBorder: "#b86b00",
    reverseText: "#5f3700",
    shadow: "0 14px 38px rgba(37, 68, 84, 0.12)",
  },
  // Amber theme
  amber: {
    bg: "#090704",
    surface: "#151006",
    surface2: "#1d1609",
    surface3: "#281d0b",
    border: "#5d451c",
    borderSoft: "rgba(255, 183, 71, 0.22)",
    text: "#fff4dc",
    muted: "#c6aa79",
    green: "#ffb547",
    greenSoft: "rgba(255, 181, 71, 0.13)",
    cyan: "#ffd36a",
    cyanSoft: "rgba(255, 211, 106, 0.12)",
    amber: "#ffb547",
    red: "#ff7068",
    reverseBg: "rgba(255, 91, 64, 0.16)",
    reverseBorder: "#ff8b69",
    reverseText: "#ffd8cc",
    shadow: "0 18px 56px rgba(0, 0, 0, 0.48)",
  },
} as const;

// Typography scale
export const typography = {
  fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  monoFamily: '"SFMono-Regular", Consolas, monospace',
  sizes: {
    xs: "9px",
    sm: "10px",
    base: "11px",
    md: "12px",
    lg: "13px",
    xl: "14px",
    "2xl": "16px",
    "3xl": "18px",
    "4xl": "20px",
    "5xl": "24px",
    "6xl": "25px",
    "7xl": "29px",
    "8xl": "31px",
  },
  weights: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
    extrabold: 780,
    black: 800,
  },
  lineHeights: {
    tight: 1.08,
    normal: 1.4,
    relaxed: 1.55,
    loose: 1.7,
  },
  letterSpacing: {
    tighter: "-0.035em",
    tight: "-0.025em",
    normal: "0",
    wide: "0.02em",
    wider: "0.04em",
    widest: "0.06em",
    ultra: "0.14em",
    ultraWide: "0.18em",
  },
} as const;

// Spacing system (4px base unit)
export const spacing = {
  px: "1px",
  0: "0",
  0.5: "2px",
  1: "4px",
  1.5: "6px",
  2: "8px",
  2.5: "10px",
  3: "12px",
  3.5: "14px",
  4: "16px",
  5: "20px",
  6: "24px",
  7: "28px",
  8: "30px",
  9: "36px",
  10: "40px",
  11: "44px",
  12: "48px",
  14: "56px",
  16: "64px",
  20: "80px",
  24: "96px",
} as const;

// Border radius scale
export const borderRadius = {
  none: "0",
  sm: "7px",
  md: "8px",
  lg: "9px",
  xl: "10px",
  "2xl": "11px",
  "3xl": "12px",
  full: "9999px",
} as const;

// Box shadows
export const shadows = {
  sm: "0 1px 2px rgba(0, 0, 0, 0.05)",
  md: "0 4px 6px rgba(0, 0, 0, 0.1)",
  lg: "0 10px 15px rgba(0, 0, 0, 0.1)",
  xl: "0 20px 25px rgba(0, 0, 0, 0.15)",
  "2xl": "0 25px 50px rgba(0, 0, 0, 0.25)",
  inner: "inset 0 2px 4px rgba(0, 0, 0, 0.06)",
  glow: {
    green: "0 0 12px rgba(0, 232, 153, 0.6)",
    cyan: "0 0 12px rgba(36, 207, 255, 0.5)",
    amber: "0 0 12px rgba(255, 192, 74, 0.45)",
    red: "0 0 12px rgba(255, 93, 103, 0.45)",
  },
} as const;

// Z-index scale
export const zIndex = {
  hide: -1,
  auto: "auto",
  base: 0,
  dropdown: 10,
  sticky: 20,
  overlay: 30,
  modal: 40,
  popover: 50,
  tooltip: 60,
  toast: 70,
  max: 9999,
} as const;

// Transitions
export const transitions = {
  fast: "0.18s ease",
  normal: "0.2s ease",
  slow: "0.3s ease",
  properties: {
    colors: "background 0.2s ease, color 0.2s ease",
    transform: "transform 0.18s ease",
    all: "all 0.18s ease",
  },
} as const;

// Component-specific tokens
export const componentTokens = {
  button: {
    heights: {
      sm: "30px",
      md: "34px",
      lg: "38px",
      xl: "40px",
    },
    paddingX: {
      sm: "8px",
      md: "11px",
      lg: "12px",
      xl: "16px",
    },
  },
  card: {
    padding: {
      sm: "12px",
      md: "14px",
      lg: "16px",
      xl: "20px",
    },
  },
  input: {
    height: "40px",
    paddingX: "11px",
  },
  nav: {
    itemHeight: "48px",
    sidebarWidth: "262px",
    topbarHeight: "80px",
  },
} as const;

// Theme configuration
export type ThemeName = "dark" | "deep-sea" | "light" | "amber";
type PaletteName = keyof typeof colors;

const themePaletteMap: Record<ThemeName, PaletteName> = {
  dark: "dark",
  "deep-sea": "deepSea",
  light: "light",
  amber: "amber",
};

export const themeConfig: Record<ThemeName, { name: string; hint: string }> = {
  "dark": { name: "Dark", hint: "Đen xanh tiêu chuẩn" },
  "deep-sea": { name: "Deep-Sea", hint: "Xanh biển sâu, cyan lạnh" },
  "light": { name: "Light", hint: "Sáng sạch, tương phản dịu" },
  "amber": { name: "Amber Contrast", hint: "Đen + vàng hổ phách tương phản cao" },
} as const;

// Export CSS custom properties generator
export function generateCSSVariables(theme: ThemeName): string {
  const palette = colors[themePaletteMap[theme]];
  return `
    --bg: ${palette.bg};
    --surface: ${palette.surface};
    --surface-2: ${palette.surface2};
    --surface-3: ${palette.surface3};
    --border: ${palette.border};
    --border-soft: ${palette.borderSoft};
    --text: ${palette.text};
    --muted: ${palette.muted};
    --green: ${palette.green};
    --green-soft: ${palette.greenSoft};
    --cyan: ${palette.cyan};
    --cyan-soft: ${palette.cyanSoft};
    --amber: ${palette.amber};
    --red: ${palette.red};
    --reverse-bg: ${palette.reverseBg};
    --reverse-border: ${palette.reverseBorder};
    --reverse-text: ${palette.reverseText};
    --shadow: ${palette.shadow};
  `.trim();
}

export default {
  colors,
  typography,
  spacing,
  borderRadius,
  shadows,
  zIndex,
  transitions,
  componentTokens,
  themeConfig,
  generateCSSVariables,
};
