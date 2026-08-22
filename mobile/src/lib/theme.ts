import { useColorScheme } from "react-native";

const dark = {
  canvas: "#070B11",
  surface: "#0D141D",
  raised: "#121C28",
  text: "#F5F7FA",
  muted: "#8C9BAD",
  border: "#243244",
  accent: "#4D9FFF",
  buy: "#20C997",
  sell: "#FF6B6B",
  warning: "#F5B942",
  danger: "#FF5D5D",
  online: "#12B76A",
  glass: "rgba(13,20,29,0.76)",
};

const light = {
  canvas: "#F3F6FA",
  surface: "#FFFFFF",
  raised: "#F7F9FC",
  text: "#101828",
  muted: "#667085",
  border: "#D0D5DD",
  accent: "#1677FF",
  buy: "#07875F",
  sell: "#D92D20",
  warning: "#A15C07",
  danger: "#B42318",
  online: "#07875F",
  glass: "rgba(255,255,255,0.82)",
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
