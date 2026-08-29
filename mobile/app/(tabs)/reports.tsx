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
  const balancePct = backend?.signalBalancePct ?? fallback.winRate;
  const trend = backend?.trend || [];
  const maxTrend = Math.max(1, ...trend.map((item) => item.value));

  return (
    <OakScreen
      eyebrow="OAK / REPORTS"
      title="Reports"
      subtitle="Backend summary cho H1 feed: tổng tín hiệu, BUY/SELL mix và khối lượng tín hiệu theo ngày."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <SectionTitle title="Ngày" meta={date || "—"} />
      <View style={styles.grid2}>
        <GlassCard style={styles.half}><Metric label="TỔNG TÍN HIỆU" value={`${total}`} /></GlassCard>
        <GlassCard style={styles.half} glow="accent"><Metric label="SIGNAL BALANCE" value={`${balancePct}%`} tone="accent" /></GlassCard>
        <GlassCard style={styles.half} glow="buy"><Metric label="BUY" value={`${buy}`} tone="buy" /></GlassCard>
        <GlassCard style={styles.half} glow="sell"><Metric label="SELL" value={`${sell}`} tone="sell" /></GlassCard>
      </View>

      <SectionTitle title="Signal volume" meta={backend ? "Backend" : "Backend unavailable"} />
      <GlassCard glow="accent">
        {trend.length ? (
          <>
            <View style={styles.chart}>
              {trend.map((item) => {
                const height = Math.max(8, Math.round((item.value / maxTrend) * 112));
                return (
                  <View key={`${item.date}:${item.index}`} style={[styles.barWrap, { borderColor: theme.border }]}>
                    <View style={[styles.bar, { height, backgroundColor: theme.cyan }]} />
                  </View>
                );
              })}
            </View>
            <View style={styles.chartLegend}>
              <Pill label={`BUY ${total ? Math.round((buy / total) * 100) : 0}%`} tone="buy" />
              <Pill label={`SELL ${total ? Math.round((sell / total) * 100) : 0}%`} tone="sell" />
              <Pill label={`${trend.length} DAYS`} tone="accent" />
            </View>
          </>
        ) : (
          <Text style={[styles.emptyCopy, { color: theme.muted }]}>Chưa có history từ backend để dựng signal volume.</Text>
        )}
      </GlassCard>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  grid2: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  half: { width: "48%" },
  chart: { height: 150, flexDirection: "row", alignItems: "flex-end", gap: 8, paddingTop: spacing.md },
  barWrap: { flex: 1, height: 120, justifyContent: "flex-end", borderBottomWidth: 1 },
  bar: { borderRadius: 999, opacity: 0.9 },
  chartLegend: { marginTop: spacing.md, flexDirection: "row", flexWrap: "wrap", gap: 8 },
  emptyCopy: { fontSize: 13, lineHeight: 20, fontWeight: "700" },
});
