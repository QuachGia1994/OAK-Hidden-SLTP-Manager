import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { OakScreen, Pill, SectionTitle } from "@/components/ui";
import { allowTradeDetail, latestH1Date, recentAlerts } from "@/lib/h1";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useOakData } from "@/state/data";

type Filter = "all" | "pure" | "blocked";

export default function AlertsScreen() {
  const theme = useOakTheme();
  const router = useRouter();
  const { h1, refreshing, refresh } = useOakData();
  const [filter, setFilter] = useState<Filter>("all");
  const date = latestH1Date(h1);
  const rows = useMemo(() => recentAlerts(h1).filter(({ alert }) => {
    if (filter === "pure") return alert.patternKind === "sw3Pure";
    if (filter === "blocked") return alert.tradeAllowed === false;
    return true;
  }), [h1, filter]);

  return (
    <OakScreen
      eyebrow="OAK / EVENT STREAM"
      title="Alerts"
      subtitle="Recent H1 pattern events from the same normalized cloud feed used by Engine."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.accent} />}
    >
      <View style={[styles.filters, { borderColor: theme.border, backgroundColor: theme.raised }]}>
        {(["all", "pure", "blocked"] as const).map((item) => {
          const active = filter === item;
          return (
            <Pressable
              key={item}
              onPress={() => {
                setFilter(item);
                Haptics.selectionAsync();
              }}
              style={[styles.filter, { backgroundColor: active ? theme.surface : "transparent", borderColor: active ? `${theme.accent}66` : "transparent" }]}
            >
              <Text style={[styles.filterText, { color: active ? theme.text : theme.muted }]}>{item.toUpperCase()}</Text>
            </Pressable>
          );
        })}
      </View>

      <SectionTitle title="H1 activity" meta={date || "—"} />
      <View style={styles.list}>
        {rows.map(({ symbol, alert }) => {
          const pure = alert.patternKind === "sw3Pure";
          const blocked = alert.tradeAllowed === false;
          const signalColor = alert.signal === "SELL" ? theme.sell : theme.buy;
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
                  borderColor: blocked ? `${theme.warning}88` : pure ? `${theme.warning}55` : theme.border,
                  backgroundColor: blocked ? `${theme.warning}12` : theme.surface,
                  opacity: pressed ? 0.72 : 1,
                },
              ]}
            >
              <View style={styles.rowTop}>
                <View style={styles.rowIdentity}>
                  <Text style={[styles.symbol, { color: theme.text }]}>{symbol}</Text>
                  <Text style={[styles.hour, { color: theme.muted }]}>H{String(alert.slotHour).padStart(2, "0")}</Text>
                </View>
                <Text style={[styles.signal, { color: blocked ? theme.warning : signalColor }]}>{blocked ? "BLOCK" : alert.signal}</Text>
              </View>
              <View style={styles.badges}>
                {pure ? <Pill label="⚠ PURE" tone="warning" /> : <Pill label={alert.patternKind === "sw2" ? "SW2" : "SW NORMAL"} />}
                <Pill label={blocked ? "NOT TRADE" : "ACTIVE"} tone={blocked ? "warning" : "online"} />
              </View>
              <Text style={[styles.meta, { color: theme.muted }]}>{alert.pattern.replaceAll(" ", " · ")} · {alert.scannerBase} → base {alert.baseSymbol}</Text>
              {blocked ? <Text style={[styles.blockedBy, { color: theme.warning }]}>{allowTradeDetail(alert)} · calculated {alert.signal}</Text> : null}
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
  blockedBy: { fontSize: 11, fontWeight: "800" },
  empty: { padding: spacing.lg, gap: 6, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  emptyTitle: { fontSize: 16, fontWeight: "900" },
  emptyCopy: { fontSize: 12, lineHeight: 18 },
});
