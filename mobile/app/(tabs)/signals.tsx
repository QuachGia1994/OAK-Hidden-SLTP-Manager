import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { GlassCard, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { latestH1Date, recentAlerts } from "@/lib/h1";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import type { MobileSignalRow } from "@/lib/types";
import { useOakData } from "@/state/data";

type Filter = "all" | "buy" | "sell";
const FILTERS: Filter[] = ["all", "buy", "sell"];
const TEMP_HIDDEN_H1_ROWS = new Set(["GBPCAD", "GBPJPY"]);

export default function SignalsScreen() {
  const theme = useOakTheme();
  const router = useRouter();
  const { h1, app, refreshing, refresh } = useOakData();
  const [filter, setFilter] = useState<Filter>("all");
  const date = app?.signals?.brokerDate || latestH1Date(h1);
  const manualCloseH16 = Boolean(date && h1?.days?.[date]?.symbols?.XAUUSD?.alerts?.some((alert) => alert.slotHour === 3 && alert.entryHour === 5));
  const rows = useMemo(() => {
    const backendRows = app?.signals?.today?.length ? app.signals.today : null;
    const source: MobileSignalRow[] = backendRows || recentAlerts(h1).map(({ symbol, alert }) => ({
      symbol,
      slotHour: alert.slotHour,
      signal: alert.signal,
      baseSignal: alert.baseSignal,
      baseDirection: alert.baseDirection,
      postSignalInverted: Boolean(alert.postSignalInverted),
      postSignalRule: alert.postSignalRule || "none",
    }));
    return source.filter((row) => {
      if (TEMP_HIDDEN_H1_ROWS.has(row.symbol)) return false;
      if (filter === "buy") return row.signal === "BUY";
      if (filter === "sell") return row.signal === "SELL";
      return true;
    });
  }, [app, h1, filter]);

  return (
    <OakScreen
      eyebrow="OAK / SIGNALS"
      title="Signals"
      subtitle="Realtime BUY/SELL radar và H1 base candle drill-down."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <View style={[styles.filters, { borderColor: theme.border, backgroundColor: theme.raised }]}> 
        {FILTERS.map((item) => {
          const active = filter === item;
          return (
            <Pressable key={item} onPress={() => { setFilter(item); Haptics.selectionAsync(); }} style={[styles.filter, { backgroundColor: active ? theme.surface : "transparent", borderColor: active ? `${theme.cyan}66` : "transparent" }]}> 
              <Text style={[styles.filterText, { color: active ? theme.text : theme.muted }]}>{item.toUpperCase()}</Text>
            </Pressable>
          );
        })}
      </View>

      <SectionTitle title="H1 activity" meta={date || "—"} />
      <View style={styles.list}>
        {rows.map((row) => {
          const manualCloseRow = row.slotHour === 16 && manualCloseH16;
          const tone = manualCloseRow ? "warning" : row.signal === "SELL" ? "sell" : "buy";
          return (
            <Pressable key={`${row.symbol}:${row.slotHour}`} onPress={() => { Haptics.selectionAsync(); router.push({ pathname: "/signal/[symbol]/[hour]", params: { symbol: row.symbol, hour: String(row.slotHour) } } as never); }}>
              <GlassCard glow={tone}>
                <View style={styles.rowTop}>
                  <View style={styles.rowIdentity}>
                    <Text style={[styles.symbol, { color: theme.text }]}>{row.symbol}</Text>
                    <Text style={[styles.hour, { color: theme.muted }]}>H{String(row.slotHour).padStart(2, "0")}</Text>
                  </View>
                  <Text style={[styles.signal, { color: manualCloseRow ? theme.warning : row.signal === "SELL" ? theme.sell : theme.buy }]}>{manualCloseRow ? "CLOSE" : (row.signal || "—")}</Text>
                </View>
                <View style={styles.badges}>
                  <Pill label={`BASE ${row.baseDirection || "—"}`} />
                  <Pill label="BACKEND" tone={app?.signals ? "accent" : "muted"} />
                </View>
              </GlassCard>
            </Pressable>
          );
        })}
        {!rows.length ? (
          <View style={[styles.empty, { borderColor: theme.border, backgroundColor: theme.surface }]}>
            <Text style={[styles.emptyTitle, { color: theme.text }]}>No matching alerts</Text>
            <Text style={[styles.emptyCopy, { color: theme.muted }]}>Feed trống hoặc filter không có tín hiệu hiện tại.</Text>
          </View>
        ) : null}
      </View>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  filters: { flexDirection: "row", padding: 4, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, gap: 4 },
  filter: { flex: 1, minHeight: 40, alignItems: "center", justifyContent: "center", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm },
  filterText: { fontSize: 9, fontWeight: "900", letterSpacing: 0.8 },
  list: { gap: spacing.sm },
  rowTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  rowIdentity: { flexDirection: "row", alignItems: "baseline", gap: 8 },
  symbol: { fontSize: 19, fontWeight: "900", letterSpacing: -0.4 },
  hour: { fontSize: 12, fontWeight: "900" },
  signal: { fontSize: 20, fontWeight: "900" },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: spacing.sm },
  empty: { padding: spacing.lg, gap: 6, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  emptyTitle: { fontSize: 16, fontWeight: "900" },
  emptyCopy: { fontSize: 12, lineHeight: 18 },
});
