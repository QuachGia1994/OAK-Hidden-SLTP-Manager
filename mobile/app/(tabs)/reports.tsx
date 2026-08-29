import { RefreshControl, StyleSheet, Text, View } from "react-native";
import { GlassCard, Metric, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { latestH1Date, reportSummary } from "@/lib/h1";
import { spacing, useOakTheme } from "@/lib/theme";
import { useOakData } from "@/state/data";

export default function ReportsScreen() {
  const theme = useOakTheme();
  const { h1, refreshing, refresh } = useOakData();
  const summary = reportSummary(h1);
  const date = latestH1Date(h1);
  const buyPct = summary.total ? Math.round((summary.buy / summary.total) * 100) : 0;
  const sellPct = summary.total ? Math.round((summary.sell / summary.total) * 100) : 0;
  const reversePct = summary.total ? Math.round((summary.reverse / summary.total) * 100) : 0;

  return (
    <OakScreen
      eyebrow="OAK / REPORTS"
      title="Reports"
      subtitle="Hiệu suất H1 feed client-side: BUY/SELL mix, reverse ratio và system rhythm."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <SectionTitle title="Ngày" meta={date || "—"} />
      <View style={styles.grid2}>
        <GlassCard style={styles.half}><Metric label="TỔNG TÍN HIỆU" value={`${summary.total}`} /></GlassCard>
        <GlassCard style={styles.half} glow="buy"><Metric label="WIN RATE DEMO" value={`${summary.winRate}%`} tone="buy" /></GlassCard>
        <GlassCard style={styles.half} glow="buy"><Metric label="BUY" value={`${summary.buy}`} tone="buy" /></GlassCard>
        <GlassCard style={styles.half} glow="sell"><Metric label="SELL" value={`${summary.sell}`} tone="sell" /></GlassCard>
        <GlassCard style={styles.half} glow="warning"><Metric label="HẬU ĐẢO" value={`${summary.reverse}`} tone="warning" /></GlassCard>
        <GlassCard style={styles.half}><Metric label="HẬU GIỮ" value={`${summary.keep}`} tone="accent" /></GlassCard>
      </View>

      <SectionTitle title="Performance curve" meta="Synthetic preview" />
      <GlassCard glow="buy">
        <View style={styles.chart}>
          {[12, 22, 18, 31, 38, 34, 45, 52, 49, 61].map((height, index) => (
            <View key={index} style={[styles.barWrap, { borderColor: theme.border }]}> 
              <View style={[styles.bar, { height, backgroundColor: index < 2 ? theme.sell : theme.buy }]} />
            </View>
          ))}
        </View>
        <View style={styles.chartLegend}>
          <Pill label={`BUY ${buyPct}%`} tone="buy" />
          <Pill label={`SELL ${sellPct}%`} tone="sell" />
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
