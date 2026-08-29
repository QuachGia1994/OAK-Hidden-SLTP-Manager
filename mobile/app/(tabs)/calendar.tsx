import * as Haptics from "expo-haptics";
import { useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { GlassCard, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { h1Hours, latestH1Date, phaseLabel, signalFor } from "@/lib/h1";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useOakData } from "@/state/data";

const FALLBACK_SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"];

function isoDaysAgo(days: number) {
  const value = new Date();
  value.setDate(value.getDate() - days);
  return value.toISOString().slice(0, 10);
}

export default function CalendarScreen() {
  const theme = useOakTheme();
  const { h1, refreshing, refresh } = useOakData();
  const dates = useMemo(() => Object.keys(h1?.days || {}).sort().reverse(), [h1]);
  const [offset, setOffset] = useState(0);
  const selectedDate = dates[offset] || latestH1Date(h1) || isoDaysAgo(0);
  const symbols = h1?.symbols?.length ? h1.symbols : FALLBACK_SYMBOLS;
  const hours = h1Hours(h1);

  function move(delta: number) {
    const next = Math.max(0, Math.min(Math.max(dates.length - 1, 0), offset + delta));
    setOffset(next);
    Haptics.selectionAsync();
  }

  return (
    <OakScreen
      eyebrow="OAK / H1 CALENDAR"
      title="H1 Calendar"
      subtitle="Lịch block H1, tín hiệu BUY/SELL và hậu signal theo từng symbol."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <GlassCard>
        <View style={styles.dateRail}>
          <Pressable style={[styles.arrow, { borderColor: theme.border }]} onPress={() => move(1)}><Text style={[styles.arrowText, { color: theme.text }]}>‹</Text></Pressable>
          <View style={[styles.dateBox, { borderColor: theme.border, backgroundColor: theme.raised }]}>
            <Text style={[styles.dateText, { color: theme.text }]}>{selectedDate}</Text>
            <Text style={[styles.dateMeta, { color: theme.muted }]}>{dates.length ? `${offset + 1}/${dates.length} ngày` : "calendar dự phòng"}</Text>
          </View>
          <Pressable style={[styles.arrow, { borderColor: theme.border }]} onPress={() => move(-1)}><Text style={[styles.arrowText, { color: theme.text }]}>›</Text></Pressable>
        </View>
      </GlassCard>

      <SectionTitle title="Block matrix" meta="Vuốt ngang" />
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={[styles.table, { borderColor: theme.border }]}> 
          <View style={[styles.tr, { backgroundColor: theme.raised }]}> 
            <Text style={[styles.symbolHead, { color: theme.muted }]}>SYMBOL</Text>
            {hours.map((hour) => <Text key={hour} style={[styles.th, { color: theme.muted }]}>H{String(hour).padStart(2, "0")}</Text>)}
          </View>
          {symbols.map((symbol) => (
            <View key={symbol} style={[styles.tr, { borderTopColor: theme.border }]}> 
              <Text style={[styles.symbolCell, { color: theme.text }]}>{symbol}</Text>
              {hours.map((hour) => {
                const alert = signalFor(h1, selectedDate, symbol, hour);
                const signal = alert?.signal;
                const tone = signal === "SELL" ? "sell" : signal === "BUY" ? "buy" : "muted";
                return (
                  <View key={hour} style={[styles.cell, { borderLeftColor: theme.border, backgroundColor: alert?.postSignalInverted ? `${theme.warning}18` : "transparent" }]}> 
                    {signal ? <Pill label={signal} tone={tone} /> : <Text style={[styles.empty, { color: theme.muted }]}>–</Text>}
                  </View>
                );
              })}
            </View>
          ))}
        </View>
      </ScrollView>

      <GlassCard glow="warning">
        <View style={styles.legendRow}>
          <Pill label="BUY" tone="buy" />
          <Pill label="SELL" tone="sell" />
          <Pill label="ĐẢO" tone="warning" />
          <Text style={[styles.legendCopy, { color: theme.muted }]}>Cell vàng là hậu signal đảo theo rule H1.</Text>
        </View>
      </GlassCard>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  dateRail: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  arrow: { width: 42, height: 42, borderRadius: radius.sm, borderWidth: StyleSheet.hairlineWidth, alignItems: "center", justifyContent: "center" },
  arrowText: { fontSize: 24, fontWeight: "900" },
  dateBox: { flex: 1, minHeight: 54, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, alignItems: "center", justifyContent: "center", gap: 4 },
  dateText: { fontSize: 16, fontWeight: "900" },
  dateMeta: { fontSize: 10, fontWeight: "800" },
  table: { overflow: "hidden", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  tr: { minHeight: 58, flexDirection: "row", alignItems: "stretch", borderTopWidth: StyleSheet.hairlineWidth },
  symbolHead: { width: 92, padding: spacing.sm, fontSize: 10, fontWeight: "900", letterSpacing: 0.8 },
  symbolCell: { width: 92, padding: spacing.sm, fontSize: 12, fontWeight: "900" },
  th: { width: 70, padding: spacing.sm, textAlign: "center", fontSize: 10, fontWeight: "900" },
  cell: { width: 70, borderLeftWidth: StyleSheet.hairlineWidth, alignItems: "center", justifyContent: "center" },
  empty: { fontSize: 18, fontWeight: "900" },
  legendRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: spacing.sm },
  legendCopy: { flex: 1, minWidth: 160, fontSize: 12, lineHeight: 18, fontWeight: "700" },
});
