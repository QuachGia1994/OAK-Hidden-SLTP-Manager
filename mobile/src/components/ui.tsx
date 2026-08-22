import { BlurView } from "expo-blur";
import { LinearGradient } from "expo-linear-gradient";
import { useMinimizeOnScroll } from "expo-glass-tabs";
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
  const onScroll = useMinimizeOnScroll();
  return (
    <LinearGradient colors={[theme.canvas, theme.canvas, theme.raised]} style={styles.flex}>
      <SafeAreaView style={styles.flex} edges={["top"]}>
        <Animated.ScrollView
          onScroll={onScroll}
          scrollEventThrottle={16}
          refreshControl={refreshControl}
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.hero}>
            <Text style={[styles.eyebrow, { color: theme.accent }]}>{eyebrow}</Text>
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

export function GlassCard({ children, style }: { children: ReactNode; style?: ViewStyle | ViewStyle[] }) {
  const theme = useOakTheme();
  return (
    <View style={[styles.cardShell, { borderColor: theme.border }, style]}>
      <BlurView intensity={26} tint="default" style={[styles.cardBlur, { backgroundColor: theme.glass }]}>
        {children}
      </BlurView>
    </View>
  );
}

export function Pill({ label, tone = "muted" }: { label: string; tone?: "muted" | "accent" | "buy" | "sell" | "warning" | "danger" | "online" }) {
  const theme = useOakTheme();
  const color = tone === "accent" ? theme.accent
    : tone === "buy" ? theme.buy
      : tone === "sell" ? theme.sell
        : tone === "warning" ? theme.warning
          : tone === "danger" ? theme.danger
            : tone === "online" ? theme.online
              : theme.muted;
  return (
    <View style={[styles.pill, { borderColor: `${color}66`, backgroundColor: `${color}16` }]}>
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

export function Metric({ label, value }: { label: string; value: string }) {
  const theme = useOakTheme();
  return (
    <View style={styles.metric}>
      <Text style={[styles.metricLabel, { color: theme.muted }]}>{label}</Text>
      <Text style={[styles.metricValue, { color: theme.text }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md },
  hero: { paddingTop: spacing.md, paddingBottom: spacing.sm, gap: 6 },
  eyebrow: { fontSize: 11, fontWeight: "900", letterSpacing: 1.8 },
  title: { fontSize: 34, lineHeight: 38, fontWeight: "900", letterSpacing: -1.4 },
  subtitle: { maxWidth: 520, fontSize: 14, lineHeight: 21 },
  cardShell: { overflow: "hidden", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.lg },
  cardBlur: { padding: spacing.md },
  pill: { alignSelf: "flex-start", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.pill, paddingHorizontal: 9, paddingVertical: 5 },
  pillText: { fontSize: 10, fontWeight: "900", letterSpacing: 0.8 },
  sectionTitle: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", gap: spacing.sm, marginTop: spacing.sm },
  sectionHeading: { fontSize: 18, fontWeight: "900", letterSpacing: -0.4 },
  sectionMeta: { fontSize: 11, fontWeight: "700" },
  metric: { flex: 1, gap: 4 },
  metricLabel: { fontSize: 10, fontWeight: "800", letterSpacing: 0.8 },
  metricValue: { fontSize: 15, fontWeight: "900" },
  bottomSpacer: { height: 88 },
});
