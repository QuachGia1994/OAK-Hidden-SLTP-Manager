import { BlurView } from "expo-blur";
import { LinearGradient } from "expo-linear-gradient";
import type { ReactElement, ReactNode } from "react";
import { StyleSheet, Text, View, type RefreshControlProps, type ViewStyle } from "react-native";
import Animated from "react-native-reanimated";
import { SafeAreaView } from "react-native-safe-area-context";
import { radius, spacing, useOakTheme } from "@/lib/theme";

export function OakScreen({
  eyebrow,
  title,
  subtitle,
  children,
  refreshControl,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
  refreshControl?: ReactElement<RefreshControlProps>;
}) {
  const theme = useOakTheme();
  return (
    <LinearGradient colors={[theme.canvas, "#07101D", theme.canvas]} style={styles.flex}>
      <View style={styles.gridLayer} pointerEvents="none">
        <View style={[styles.orb, { backgroundColor: theme.glow }]} />
        <View style={[styles.orbSmall, { backgroundColor: `${theme.purple}20` }]} />
      </View>
      <SafeAreaView style={styles.flex} edges={["top"]}>
        <Animated.ScrollView
          refreshControl={refreshControl}
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.hero}>
            <Text style={[styles.eyebrow, { color: theme.cyan }]}>{eyebrow}</Text>
            <Text style={[styles.title, { color: theme.text }]}>{title}</Text>
            {subtitle ? <Text style={[styles.subtitle, { color: theme.muted }]}>{subtitle}</Text> : null}
          </View>
          {children}
          <View style={styles.bottomSpacer} />
        </Animated.ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

export function GlassCard({ children, style, glow = "accent" }: { children: ReactNode; style?: ViewStyle | ViewStyle[]; glow?: "accent" | "buy" | "sell" | "warning" | "purple" | "muted" }) {
  const theme = useOakTheme();
  const color = glow === "buy" ? theme.buy
    : glow === "sell" ? theme.sell
      : glow === "warning" ? theme.warning
        : glow === "purple" ? theme.purple
          : glow === "muted" ? theme.border
            : theme.cyan;
  return (
    <View style={[styles.cardShell, { borderColor: `${color}4D`, shadowColor: color }, style]}>
      <BlurView intensity={30} tint="dark" style={[styles.cardBlur, { backgroundColor: theme.glass }]}>
        <LinearGradient colors={[`${color}12`, "transparent"]} style={styles.cardGlow} pointerEvents="none" />
        {children}
      </BlurView>
    </View>
  );
}

export function Pill({ label, tone = "muted" }: { label: string; tone?: "muted" | "accent" | "buy" | "sell" | "warning" | "danger" | "online" | "purple" }) {
  const theme = useOakTheme();
  const color = tone === "accent" ? theme.cyan
    : tone === "buy" ? theme.buy
      : tone === "sell" ? theme.sell
        : tone === "warning" ? theme.warning
          : tone === "danger" ? theme.danger
            : tone === "online" ? theme.online
              : tone === "purple" ? theme.purple
                : theme.muted;
  return (
    <View style={[styles.pill, { borderColor: `${color}66`, backgroundColor: `${color}18` }]}>
      <Text style={[styles.pillText, { color }]}>{label}</Text>
    </View>
  );
}

export function SectionTitle({ title, meta }: { title: string; meta?: string }) {
  const theme = useOakTheme();
  return (
    <View style={styles.sectionTitle}>
      <Text style={[styles.sectionHeading, { color: theme.text }]}>{title}</Text>
      {meta ? <Text style={[styles.sectionMeta, { color: theme.muted }]}>{meta}</Text> : null}
    </View>
  );
}

export function Metric({ label, value, tone = "text" }: { label: string; value: string; tone?: "text" | "buy" | "sell" | "warning" | "accent" | "muted" }) {
  const theme = useOakTheme();
  const valueColor = tone === "buy" ? theme.buy
    : tone === "sell" ? theme.sell
      : tone === "warning" ? theme.warning
        : tone === "accent" ? theme.cyan
          : tone === "muted" ? theme.muted
            : theme.text;
  return (
    <View style={styles.metric}>
      <Text style={[styles.metricLabel, { color: theme.muted }]}>{label}</Text>
      <Text style={[styles.metricValue, { color: valueColor }]}>{value}</Text>
    </View>
  );
}

export function Beacon({ tone = "online" }: { tone?: "online" | "warning" | "danger" | "accent" }) {
  const theme = useOakTheme();
  const color = tone === "warning" ? theme.warning : tone === "danger" ? theme.danger : tone === "accent" ? theme.cyan : theme.online;
  return <View style={[styles.beacon, { backgroundColor: color, shadowColor: color }]} />;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md },
  gridLayer: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, overflow: "hidden" },
  orb: { position: "absolute", width: 260, height: 260, borderRadius: 999, top: -80, right: -90, opacity: 0.6 },
  orbSmall: { position: "absolute", width: 180, height: 180, borderRadius: 999, bottom: 90, left: -80, opacity: 0.55 },
  hero: { paddingTop: spacing.md, paddingBottom: spacing.xs, gap: 6 },
  eyebrow: { fontSize: 10, fontWeight: "900", letterSpacing: 2.1 },
  title: { fontSize: 32, lineHeight: 36, fontWeight: "900", letterSpacing: -1.3, textShadowColor: "rgba(88,166,255,.35)", textShadowRadius: 16 },
  subtitle: { maxWidth: 520, fontSize: 13, lineHeight: 20 },
  cardShell: {
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    shadowOpacity: 0.22,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 },
    elevation: 3,
  },
  cardBlur: { padding: spacing.md, overflow: "hidden" },
  cardGlow: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, opacity: 0.85 },
  pill: { alignSelf: "flex-start", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.pill, paddingHorizontal: 9, paddingVertical: 5 },
  pillText: { fontSize: 10, fontWeight: "900", letterSpacing: 0.8 },
  sectionTitle: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", gap: spacing.sm, marginTop: spacing.sm },
  sectionHeading: { fontSize: 18, fontWeight: "900", letterSpacing: -0.4 },
  sectionMeta: { fontSize: 11, fontWeight: "800" },
  metric: { flex: 1, gap: 4 },
  metricLabel: { fontSize: 10, fontWeight: "800", letterSpacing: 0.8 },
  metricValue: { fontSize: 16, fontWeight: "900" },
  beacon: { width: 7, height: 7, borderRadius: 999, shadowOpacity: 0.8, shadowRadius: 10, shadowOffset: { width: 0, height: 0 } },
  bottomSpacer: { height: 120 },
});
