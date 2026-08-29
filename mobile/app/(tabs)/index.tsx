import { RefreshControl, StyleSheet, Text, View } from "react-native";
import { GlassCard, Metric, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { recentAlerts } from "@/lib/h1";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useOakData } from "@/state/data";

export default function DashboardScreen() {
  const theme = useOakTheme();
  const { app, h1, refreshing, error, refresh } = useOakData();
  const summary = app?.dashboard;
  const fallbackRows = recentAlerts(h1).filter((row) => row.alert.signal).slice(0, 5);
  const rows = summary?.today.length ? summary.today : fallbackRows.map(({ symbol, alert }) => ({
    symbol,
    slotHour: alert.slotHour,
    signal: alert.signal,
    baseSignal: alert.baseSignal,
    baseDirection: alert.baseDirection,
    postSignalInverted: Boolean(alert.postSignalInverted),
    postSignalRule: alert.postSignalRule || "none" as const,
  }));

  return (
    <OakScreen
      eyebrow="OAK SLTP"
      title="Dashboard"
      subtitle="Robot trading system · H1 block calendar · BUY/SELL signal monitor."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <GlassCard glow="warning">
        <View style={styles.vipRow}>
          <View style={[styles.crown, { borderColor: `${theme.vip}55`, backgroundColor: `${theme.vip}14` }]}><Text style={[styles.crownText, { color: theme.vip }]}>♛</Text></View>
          <View style={styles.vipCopy}>
            <Text style={[styles.vipTitle, { color: theme.vip }]}>VIP UNLOCKED</Text>
            <Text style={[styles.vipSub, { color: theme.muted }]}>Đã mở BUY/SELL XAUUSD</Text>
          </View>
          <Pill label="VIP" tone="warning" />
        </View>
      </GlassCard>

      <GlassCard glow={summary?.status === "ACTIVE" ? "buy" : "warning"}>
        <View style={styles.systemHead}>
          <View style={styles.systemTitleRow}>
            <Text style={[styles.cardLabel, { color: theme.muted }]}>HỆ THỐNG ONLINE</Text>
            <View style={[styles.dot, { backgroundColor: summary?.providerOnline ? theme.online : theme.warning }]} />
          </View>
          <Pill label={summary?.status || "WAITING"} tone={summary?.status === "ACTIVE" ? "online" : "warning"} />
        </View>
        <View style={styles.metricRow}>
          <Metric label="LATENCY" value={`${summary?.latencyMs || 0}ms`} />
          <Metric label="UPTIME" value={`${summary?.uptimePct || 0}%`} />
          <Metric label="STATUS" value={summary?.status || "WAIT"} tone={summary?.status === "ACTIVE" ? "buy" : "warning"} />
        </View>
      </GlassCard>

      {error ? <View style={[styles.errorBox, { borderColor: `${theme.warning}66`, backgroundColor: `${theme.warning}12` }]}><Text style={{ color: theme.warning }}>{error}</Text></View> : null}

      <SectionTitle title="Tín hiệu hôm nay" meta={summary?.brokerDate || "—"} />
      <View style={styles.list}>
        {rows.length ? rows.map((row) => {
          const tone = row.signal === "SELL" ? "sell" : "buy";
          const color = row.signal === "SELL" ? theme.sell : theme.buy;
          return (
            <GlassCard key={`${row.symbol}:${row.slotHour}`} glow={tone}>
              <View style={styles.signalLine}>
                <View style={styles.signalName}>
                  <Text style={[styles.symbol, { color: theme.text }]}>{row.symbol}</Text>
                  <Text style={[styles.signalMeta, { color: theme.muted }]}>H{String(row.slotHour).padStart(2, "0")} · Base {row.baseDirection || "—"}</Text>
                </View>
                <Text style={[styles.signal, { color }]}>{row.signal || "—"}</Text>
              </View>
            </GlassCard>
          );
        }) : (
          <GlassCard glow="muted"><Text style={[styles.emptyText, { color: theme.muted }]}>Đang chờ feed H1 live.</Text></GlassCard>
        )}
      </View>

      <SectionTitle title="Thống kê ngày" meta={summary ? `${summary.totalSignals} signals` : "—"} />
      <GlassCard glow="accent">
        <View style={styles.summaryCard}>
          <View style={[styles.ring, { borderColor: theme.accent }]}>
            <Text style={[styles.ringValue, { color: theme.text }]}>{summary?.totalSignals || 0}</Text>
            <Text style={[styles.ringLabel, { color: theme.muted }]}>Tín hiệu</Text>
          </View>
          <View style={styles.summaryStats}>
            <Metric label="BUY" value={`${summary?.buySignals || 0}`} tone="buy" />
            <Metric label="SELL" value={`${summary?.sellSignals || 0}`} tone="sell" />
          </View>
        </View>
      </GlassCard>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  vipRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  crown: { width: 48, height: 48, borderRadius: radius.md, borderWidth: StyleSheet.hairlineWidth, alignItems: "center", justifyContent: "center" },
  crownText: { fontSize: 28, fontWeight: "900" },
  vipCopy: { flex: 1, gap: 4 },
  vipTitle: { fontSize: 25, fontWeight: "900", letterSpacing: -0.6 },
  vipSub: { fontSize: 14, fontWeight: "800" },
  systemHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  systemTitleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  cardLabel: { fontSize: 11, fontWeight: "900", letterSpacing: 1.4 },
  dot: { width: 8, height: 8, borderRadius: 999 },
  metricRow: { flexDirection: "row", gap: spacing.md },
  errorBox: { padding: spacing.md, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  list: { gap: spacing.sm },
  signalLine: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  signalName: { flex: 1, gap: 3 },
  symbol: { fontSize: 16, fontWeight: "900" },
  signalMeta: { fontSize: 11, fontWeight: "800" },
  signal: { fontSize: 16, fontWeight: "900", minWidth: 44, textAlign: "right" },
  emptyText: { fontSize: 14, fontWeight: "800" },
  summaryCard: { flexDirection: "row", alignItems: "center", gap: spacing.xl },
  ring: { width: 110, height: 110, borderRadius: 999, borderWidth: 7, alignItems: "center", justifyContent: "center" },
  ringValue: { fontSize: 34, fontWeight: "900" },
  ringLabel: { fontSize: 13, fontWeight: "800" },
  summaryStats: { flex: 1, gap: spacing.md },
});
