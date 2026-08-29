import { LinearGradient } from "expo-linear-gradient";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { RefreshControl, StyleSheet, Text, View, Pressable } from "react-native";
import { Beacon, GlassCard, Metric, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { latestH1Date, recentAlerts, reportSummary } from "@/lib/h1";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useOakData } from "@/state/data";

export default function DashboardScreen() {
  const theme = useOakTheme();
  const router = useRouter();
  const { h1, accounts, refreshing, error, refresh } = useOakData();
  const date = latestH1Date(h1);
  const rows = recentAlerts(h1).slice(0, 5);
  const summary = reportSummary(h1);
  const onlineAccounts = accounts?.accounts.filter((item) => item.enabled).length || 0;
  const totalAccounts = accounts?.accounts.length || 0;

  return (
    <OakScreen
      eyebrow="OAK SLTP"
      title="Dashboard"
      subtitle="Robot trading system · H1 block calendar · BUY/SELL signal monitor."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <GlassCard glow="warning">
        <LinearGradient colors={[`${theme.vip}22`, "transparent"]} style={styles.vipGlow} pointerEvents="none" />
        <View style={styles.vipRow}>
          <View style={[styles.crown, { borderColor: `${theme.vip}55`, backgroundColor: `${theme.vip}18` }]}>
            <Text style={[styles.crownText, { color: theme.vip }]}>♛</Text>
          </View>
          <View style={styles.vipCopy}>
            <Text style={[styles.vipTitle, { color: theme.vip }]}>VIP UNLOCKED</Text>
            <Text style={[styles.vipSub, { color: theme.muted }]}>Đã mở BUY/SELL XAUUSD</Text>
          </View>
          <Pill label="VIP" tone="warning" />
        </View>
      </GlassCard>

      <GlassCard>
        <View style={styles.onlineHead}>
          <View style={styles.statusTitle}><Text style={[styles.cardLabel, { color: theme.muted }]}>HỆ THỐNG ONLINE</Text><Beacon /></View>
          <Pill label={error ? "DEGRADED" : "ACTIVE"} tone={error ? "warning" : "online"} />
        </View>
        <View style={styles.metricGrid3}>
          <Metric label="LATENCY" value="12ms" tone="text" />
          <Metric label="UPTIME" value="99.9%" tone="text" />
          <Metric label="STATUS" value={error ? "SYNC" : "ACTIVE"} tone={error ? "warning" : "buy"} />
        </View>
      </GlassCard>

      {error ? <View style={[styles.errorBox, { borderColor: `${theme.warning}66`, backgroundColor: `${theme.warning}12` }]}><Text style={{ color: theme.warning }}>{error}</Text></View> : null}

      <SectionTitle title="Tín hiệu hôm nay" meta="Xem tất cả" />
      <GlassCard glow="muted">
        <View style={styles.signalList}>
          {rows.map(({ symbol, alert }) => {
            const tone = alert.signal === "SELL" ? "sell" : "buy";
            return (
              <Pressable
                key={`${symbol}:${alert.slotHour}`}
                onPress={() => {
                  Haptics.selectionAsync();
                  router.push({ pathname: "/signal/[symbol]/[hour]", params: { symbol, hour: String(alert.slotHour) } } as never);
                }}
                style={styles.signalLine}
              >
                <Text style={[styles.signalSymbol, { color: theme.text }]}>{symbol}</Text>
                <Text style={[styles.signalHour, { color: theme.muted }]}>H{String(alert.slotHour).padStart(2, "0")}</Text>
                <Pill label={alert.signal || "—"} tone={tone} />
                <Text style={[styles.signalTime, { color: theme.muted }]}>{String(alert.baseHour ?? alert.slotHour).padStart(2, "0")}:00</Text>
              </Pressable>
            );
          })}
          {!rows.length ? <Text style={[styles.empty, { color: theme.muted }]}>Đang chờ feed H1 live.</Text> : null}
        </View>
      </GlassCard>

      <SectionTitle title="Thống kê ngày" meta={date || "—"} />
      <GlassCard glow="purple">
        <View style={styles.statsRow}>
          <View style={[styles.ring, { borderColor: theme.cyan }]}>
            <Text style={[styles.ringValue, { color: theme.text }]}>{summary.total}</Text>
            <Text style={[styles.ringLabel, { color: theme.muted }]}>Tín hiệu</Text>
          </View>
          <View style={styles.statsList}>
            <Metric label="BUY" value={`${summary.buy}`} tone="buy" />
            <Metric label="SELL" value={`${summary.sell}`} tone="sell" />
            <Metric label="BRIDGE" value={`${onlineAccounts}/${totalAccounts}`} tone="accent" />
          </View>
        </View>
      </GlassCard>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  vipGlow: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0 },
  vipRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  crown: { width: 48, height: 48, borderRadius: radius.md, borderWidth: StyleSheet.hairlineWidth, alignItems: "center", justifyContent: "center" },
  crownText: { fontSize: 28, fontWeight: "900" },
  vipCopy: { flex: 1, gap: 4 },
  vipTitle: { fontSize: 18, fontWeight: "900", letterSpacing: 0.2 },
  vipSub: { fontSize: 12, fontWeight: "700" },
  onlineHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  statusTitle: { flexDirection: "row", alignItems: "center", gap: 7 },
  cardLabel: { fontSize: 10, fontWeight: "900", letterSpacing: 1.2 },
  metricGrid3: { flexDirection: "row", gap: spacing.md },
  errorBox: { padding: spacing.md, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  signalList: { gap: spacing.sm },
  signalLine: { minHeight: 42, flexDirection: "row", alignItems: "center", gap: spacing.sm },
  signalSymbol: { width: 78, fontSize: 13, fontWeight: "900" },
  signalHour: { width: 38, fontSize: 11, fontWeight: "900" },
  signalTime: { marginLeft: "auto", fontSize: 11, fontWeight: "800" },
  empty: { fontSize: 12, fontWeight: "700" },
  statsRow: { flexDirection: "row", alignItems: "center", gap: spacing.lg },
  ring: { width: 92, height: 92, borderRadius: 999, borderWidth: 5, alignItems: "center", justifyContent: "center" },
  ringValue: { fontSize: 22, fontWeight: "900" },
  ringLabel: { fontSize: 10, fontWeight: "800" },
  statsList: { flex: 1, gap: spacing.sm },
});
