import { RefreshControl, StyleSheet, Text, View } from "react-native";
import { GlassCard, Metric, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { latestH1Date, reportSummary } from "@/lib/h1";
import { spacing, useOakTheme } from "@/lib/theme";
import { useOakData } from "@/state/data";

export default function ReportsScreen() {
  const theme = useOakTheme();
  const { app, h1, refreshing, refresh } = useOakData();
  const fallback = reportSummary(h1);
  const backend = app?.reports;
  const date = app?.dashboard.brokerDate || latestH1Date(h1);
  const total = backend?.totalSignals ?? fallback.total;
  const buy = backend?.buySignals ?? fallback.buy;
  const sell = backend?.sellSignals ?? fallback.sell;
  const reverse = backend?.reverseSignals ?? fallback.reverse;
  const keep = backend?.keepSignals ?? fallback.keep;
  const balancePct = backend?.signalBalancePct ?? fallback.winRate;
  const reversePct = backend?.reversePct ?? (total ? Math.round((reverse / total) * 100) : 0);
  const trend = backend?.trend.length ? backend.trend : [12, 22, 18, 31, 38, 34, 45, 52, 49, 61].map((value, index) => ({ date: String(index), value, index }));
  const maxTrend = Math.max(1, ...trend.map((item) => item.value));

  return (
    <OakScreen
      eyebrow="OAK / REPORTS"
      title="Reports"
      subtitle="Backend summary cho H1 feed: BUY/SELL mix, hậu signal và nhịp block theo ngày."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <SectionTitle title="Ngày" meta={date || "—"} />
      <View style={styles.grid2}>
        <GlassCard style={styles.half}><Metric label="TỔNG TÍN HIỆU" value={`${total}`} /></GlassCard>
        <GlassCard style={styles.half} glow="buy"><Metric label="SIGNAL BALANCE" value={`${balancePct}%`} tone="buy" /></GlassCard>
        <GlassCard style={styles.half} glow="buy"><Metric label="BUY" value={`${buy}`} tone="buy" /></GlassCard>
        <GlassCard style={styles.half} glow="sell"><Metric label="SELL" value={`${sell}`} tone="sell" /></GlassCard>
        <GlassCard style={styles.half} glow="warning"><Metric label="HẬU ĐẢO" value={`${reverse}`} tone="warning" /></GlassCard>
        <GlassCard style={styles.half}><Metric label="HẬU GIỮ" value={`${keep}`} tone="accent" /></GlassCard>
      </View>

      <SectionTitle title="Performance curve" meta={backend ? "Backend" : "Fallback"} />
      <GlassCard glow="buy">
        <View style={styles.chart}>
          {trend.map((item) => {
            const height = Math.max(8, Math.round((item.value / maxTrend) * 112));
            return (
              <View key={`${item.date}:${item.index}`} style={[styles.barWrap, { borderColor: theme.border }]}>
                <View style={[styles.bar, { height, backgroundColor: item.index < 2 ? theme.sell : theme.buy }]} />
              </View>
            );
          })}
        </View>
        <View style={styles.chartLegend}>
          <Pill label={`BUY ${total ? Math.round((buy / total) * 100) : 0}%`} tone="buy" />
          <Pill label={`SELL ${total ? Math.round((sell / total) * 100) : 0}%`} tone="sell" />
          <Pill label={`ĐẢO ${reversePct}%`} tone="warning" />
        </View>
      </GlassCard>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  grid2: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  half: { width: "48%" },
  chart: { height: 150, flexDirection: "row", alignItems: "flex-end", gap: 8, paddingTop: spacing.md },
  barWrap: { flex: 1, height: 120, justifyContent: "flex-end", borderBottomWidth: 1 },
  bar: { borderRadius: 999, opacity: 0.86 },
  chartLegend: { marginTop: spacing.md, flexDirection: "row", flexWrap: "wrap", gap: 8 },
});
