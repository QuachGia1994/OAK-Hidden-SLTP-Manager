const dark = {
  canvas: "#05080E",
  surface: "#0A1220",
  raised: "#101B2D",
  text: "#F8FAFF",
  muted: "#A9B8D3",
  faint: "#71809B",
  border: "#284468",
  accent: "#58A6FF",
  cyan: "#00E5FF",
  purple: "#A855F7",
  amber: "#FFB800",
  buy: "#00E08A",
  sell: "#FF476F",
  warning: "#FFB800",
  danger: "#FF476F",
  online: "#00E08A",
  glass: "rgba(10, 18, 32, 0.88)",
  glow: "rgba(0, 229, 255, 0.20)",
  vip: "#FFC44D",
};

export type OakTheme = typeof dark;

export function useOakTheme(): OakTheme {
  // The concept is intentionally dark. Do not follow system light mode: the
  // light palette washed out text against the glass cards on iOS screenshots.
  return dark;
}

export const spacing = {
  xs: 6,
  sm: 10,
  md: 14,
  lg: 18,
  xl: 24,
  xxl: 32,
} as const;

export const radius = {
  sm: 10,
  md: 16,
  lg: 22,
  pill: 999,
} as const;
