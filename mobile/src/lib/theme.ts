import { useColorScheme } from "react-native";

const dark = {
  canvas: "#05080E",
  surface: "#09111D",
  raised: "#0D1726",
  text: "#F6F8FF",
  muted: "#8EA4C4",
  border: "#1E3350",
  accent: "#58A6FF",
  cyan: "#00F0FF",
  purple: "#B026FF",
  amber: "#FFB800",
  buy: "#00FF88",
  sell: "#FF2E63",
  warning: "#FFB800",
  danger: "#FF2E63",
  online: "#00FF88",
  glass: "rgba(8, 14, 26, 0.78)",
  glow: "rgba(0, 240, 255, 0.22)",
  vip: "#FFC44D",
};

const light = {
  canvas: "#F3F6FA",
  surface: "#FFFFFF",
  raised: "#F7F9FC",
  text: "#101828",
  muted: "#667085",
  border: "#D0D5DD",
  accent: "#1677FF",
  cyan: "#1677FF",
  purple: "#6941C6",
  amber: "#B54708",
  buy: "#07875F",
  sell: "#D92D20",
  warning: "#A15C07",
  danger: "#B42318",
  online: "#07875F",
  glass: "rgba(255,255,255,0.84)",
  glow: "rgba(22,119,255,0.16)",
  vip: "#B54708",
};

export type OakTheme = typeof dark;

export function useOakTheme(): OakTheme {
  return useColorScheme() === "light" ? light : dark;
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
