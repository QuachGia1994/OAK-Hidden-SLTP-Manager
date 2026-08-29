import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { OakScreen, Pill, SectionTitle } from "@/components/ui";
import { latestH1Date, recentAlerts } from "@/lib/h1";
import type { H1SignalAlert } from "@/lib/types";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useOakData } from "@/state/data";

type Filter = "all" | "buy" | "sell" | "reverse" | "keep";

type FilterItem = { key: Filter; label: string };

const FILTERS: readonly FilterItem[] = [
  { key: "all", label: "ALL" },
  { key: "buy", label: "BUY" },
  { key: "sell", label: "SELL" },
  { key: "reverse", label: "ĐẢO" },
  { key: "keep", label: "GIỮ" },
];

function matchesFilter(alert: H1SignalAlert, filter: Filter): boolean {
  if (filter === "all") return true;
  if (filter === "buy" || filter === "sell") return alert.signal === filter.toUpperCase();
  if (filter === "reverse") return alert.postSignalInverted === true;
  return alert.postSignalInverted !== true;
}

function phaseLabel(alert: H1SignalAlert): string {
  const family = alert.postSignalRule?.startsWith("cycle-") ? "CHU KỲ" : alert.postSignalRule?.startsWith("regular-") ? "THÁNG THƯỜNG" : "PHA";
  return `${alert.postSignalInverted ? "ĐẢO" : "GIỮ"} · ${family}`;
}

function baseCandleLabel(alert: H1SignalAlert): string {
  const hour = typeof alert.baseHour === "number" ? `H${String(alert.baseHour).padStart(2, "0")}` : "H—";
  const minute = typeof alert.baseMinute === "number" ? String(alert.baseMinute).padStart(2, "0") : "00";
  const direction = alert.baseDirection || "—";
  const baseSignal = alert.baseSignal || "—";
  return `Base ${hour}:${minute} ${direction} → ${baseSignal}`;
}

export default function AlertsScreen() {
  const theme = useOakTheme();
  const router = useRouter();
  const { h1, refreshing, refresh } = useOakData();
  const [filter, setFilter] = useState<Filter>("all");
  const date = latestH1Date(h1);
  const rows = useMemo(() => recentAlerts(h1).filter(({ alert }) => matchesFilter(alert, filter)), [h1, filter]);

  return (
    <OakScreen
      eyebrow="OAK / H1 STREAM"
      title="Alerts"
      subtitle="Recent H1 block signals from schema v17 cloud feed."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.accent} />}
    >
      <View style={[styles.filters, { borderColor: theme.border, backgroundColor: theme.raised }]}>
        {FILTERS.map((item) => {
          const active = filter === item.key;
          return (
            <Pressable
              key={item.key}
              onPress={() => {
                setFilter(item.key);
                Haptics.selectionAsync();
              }}
              style={[styles.filter, { backgroundColor: active ? theme.surface : "transparent", borderColor: active ? `${theme.accent}66` : "transparent" }]}
            >
              <Text style={[styles.filterText, { color: active ? theme.text : theme.muted }]}>{item.label}</Text>
            </Pressable>
          );
        })}
      </View>

      <SectionTitle title="H1 activity" meta={date || "—"} />
      <View style={styles.list}>
        {rows.map(({ symbol, alert }) => {
          const signal = alert.signal || "—";
          const signalColor = signal === "SELL" ? theme.sell : signal === "BUY" ? theme.buy : theme.muted;
          return (
            <Pressable
              key={`${symbol}:${alert.slotHour}`}
              onPress={() => {
                Haptics.selectionAsync();
                router.push({ pathname: "/signal/[symbol]/[hour]", params: { symbol, hour: String(alert.slotHour) } } as never);
              }}
              style={({ pressed }) => [
                styles.row,
                {
                  borderColor: theme.border,
                  backgroundColor: theme.surface,
                  opacity: pressed ? 0.72 : 1,
                },
              ]}
            >
              <View style={styles.rowTop}>
                <View style={styles.rowIdentity}>
                  <Text style={[styles.symbol, { color: theme.text }]}>{symbol}</Text>
                  <Text style={[styles.hour, { color: theme.muted }]}>H{String(alert.slotHour).padStart(2, "0")}</Text>
                </View>
                <Text style={[styles.signal, { color: signalColor }]}>{signal}</Text>
              </View>
              <View style={styles.badges}>
                <Pill label={phaseLabel(alert)} />
                <Pill label={`BLOCK H${String(alert.slotHour).padStart(2, "0")}`} />
              </View>
              <Text style={[styles.meta, { color: theme.muted }]}>{baseCandleLabel(alert)} · {alert.profile}</Text>
            </Pressable>
          );
        })}
        {!rows.length ? (
          <View style={[styles.empty, { borderColor: theme.border, backgroundColor: theme.surface }]}>
            <Text style={[styles.emptyTitle, { color: theme.text }]}>No matching alerts</Text>
            <Text style={[styles.emptyCopy, { color: theme.muted }]}>The filter has no H1 events for the current broker day.</Text>
          </View>
        ) : null}
      </View>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  filters: { flexDirection: "row", padding: 4, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, gap: 4 },
  filter: { flex: 1, minHeight: 42, alignItems: "center", justifyContent: "center", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm },
  filterText: { fontSize: 10, fontWeight: "900", letterSpacing: 1 },
  list: { gap: spacing.sm },
  row: { padding: spacing.md, gap: spacing.sm, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  rowTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  rowIdentity: { flexDirection: "row", alignItems: "baseline", gap: 8 },
  symbol: { fontSize: 18, fontWeight: "900", letterSpacing: -0.4 },
  hour: { fontSize: 11, fontWeight: "800" },
  signal: { fontSize: 18, fontWeight: "900" },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  meta: { fontSize: 11, fontWeight: "700" },
  empty: { padding: spacing.lg, gap: 6, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  emptyTitle: { fontSize: 16, fontWeight: "900" },
  emptyCopy: { fontSize: 12, lineHeight: 18 },
});