import { RefreshControl, StyleSheet, Text, View } from "react-native";
import { Beacon, GlassCard, Metric, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useOakData } from "@/state/data";

export default function BridgeScreen() {
  const theme = useOakTheme();
  const { app, accounts, refreshing, refresh } = useOakData();
  const bridge = app?.bridge;
  const mt5 = accounts?.accounts.filter((item) => item.provider === "mt5") || [];
  const ctrader = accounts?.accounts.filter((item) => item.provider === "ctrader") || [];
  const onlineMt5 = bridge?.mt5Online ?? mt5.filter((item) => item.bridgeOnline).length;
  const mt5Total = bridge?.mt5Total ?? mt5.length;
  const enabledCtrader = bridge?.ctraderEnabled ?? ctrader.filter((item) => item.enabled).length;
  const ctraderTotal = bridge?.ctraderTotal ?? ctrader.length;
  const brokerOnline = onlineMt5 > 0 || enabledCtrader > 0;

  return (
    <OakScreen
      eyebrow="OAK / BRIDGE"
      title="Bridge"
      subtitle="Backend bridge state: MT5 EA heartbeat, cTrader OAuth và dispatcher cloud cho robot SLTP."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <GlassCard glow="accent">
        <View style={styles.nodeRow}>
          <View style={styles.node}><Beacon /><Text style={[styles.nodeTitle, { color: theme.text }]}>Mobile</Text><Text style={[styles.nodeMeta, { color: theme.muted }]}>Native UI</Text></View>
          <View style={[styles.link, { backgroundColor: theme.cyan }]} />
          <View style={styles.node}><Beacon tone="accent" /><Text style={[styles.nodeTitle, { color: theme.text }]}>Cloud</Text><Text style={[styles.nodeMeta, { color: theme.muted }]}>Vercel</Text></View>
          <View style={[styles.link, { backgroundColor: brokerOnline ? theme.cyan : theme.warning }]} />
          <View style={styles.node}><Beacon tone={brokerOnline ? "online" : "warning"} /><Text style={[styles.nodeTitle, { color: theme.text }]}>Broker</Text><Text style={[styles.nodeMeta, { color: theme.muted }]}>MT5/cT</Text></View>
        </View>
      </GlassCard>

      <SectionTitle title="Connection state" meta={bridge ? "Backend" : "Fallback"} />
      <View style={styles.grid}>
        <GlassCard glow={onlineMt5 ? "buy" : "warning"} style={styles.half}>
          <Metric label="MT5 BRIDGE" value={`${onlineMt5}/${mt5Total}`} tone={onlineMt5 ? "buy" : "warning"} />
        </GlassCard>
        <GlassCard glow={enabledCtrader ? "buy" : "muted"} style={styles.half}>
          <Metric label="CTRADER" value={`${enabledCtrader}/${ctraderTotal}`} tone={enabledCtrader ? "buy" : "muted"} />
        </GlassCard>
      </View>

      <SectionTitle title="Month-end bridge" meta={bridge?.brokerDate || "—"} />
      <GlassCard glow={bridge?.bridgeCells.length ? "warning" : "muted"}>
        <View style={styles.bridgeCopy}>
          <Pill label={`${bridge?.bridgeCells.length || 0} CẦU CELL`} tone={bridge?.bridgeCells.length ? "warning" : "muted"} />
          <Text style={[styles.bridgeTitle, { color: theme.text }]}>Cầu nối cuối tháng</Text>
          <Text style={[styles.bridgeText, { color: theme.muted }]}>H16 thứ 6 cuối tháng và H thứ 2–3–4 sau đó giữ phase tháng cũ; thứ 5 đầu tháng reset tháng mới.</Text>
        </View>
      </GlassCard>

      <SectionTitle title="Accounts" meta={`${accounts?.accounts.length || 0} total`} />
      <View style={styles.list}>
        {(accounts?.accounts || []).map((account) => {
          const online = account.provider === "mt5" ? Boolean(account.bridgeOnline) : account.enabled;
          return (
            <GlassCard key={account.id} glow={online ? "buy" : "muted"}>
              <View style={styles.accountLine}>
                <View style={styles.accountCopy}>
                  <View style={styles.badges}>
                    <Pill label={account.provider.toUpperCase()} tone="accent" />
                    <Pill label={online ? "ONLINE" : "STANDBY"} tone={online ? "online" : "muted"} />
                  </View>
                  <Text style={[styles.accountTitle, { color: theme.text }]}>{account.label}</Text>
                  <Text style={[styles.accountMeta, { color: theme.muted }]}>{account.broker} · #{account.externalAccountId}</Text>
                </View>
                <Text style={[styles.chev, { color: online ? theme.buy : theme.muted }]}>{online ? "●" : "○"}</Text>
              </View>
            </GlassCard>
          );
        })}
        {!accounts?.accounts.length ? (
          <View style={[styles.empty, { borderColor: theme.border, backgroundColor: theme.surface }]}>
            <Text style={[styles.emptyTitle, { color: theme.text }]}>No bridge accounts</Text>
            <Text style={[styles.emptyCopy, { color: theme.muted }]}>Connect providers from the web manager first.</Text>
          </View>
        ) : null}
      </View>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  nodeRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  node: { flex: 1, minHeight: 86, alignItems: "center", justifyContent: "center", gap: 5 },
  nodeTitle: { fontSize: 14, fontWeight: "900" },
  nodeMeta: { fontSize: 10, fontWeight: "800" },
  link: { width: 20, height: 2, opacity: 0.85 },
  grid: { flexDirection: "row", gap: spacing.sm },
  half: { flex: 1 },
  bridgeCopy: { gap: spacing.sm },
  bridgeTitle: { fontSize: 18, fontWeight: "900" },
  bridgeText: { fontSize: 12, lineHeight: 18, fontWeight: "700" },
  list: { gap: spacing.sm },
  accountLine: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  accountCopy: { flex: 1, gap: 7 },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  accountTitle: { fontSize: 17, fontWeight: "900" },
  accountMeta: { fontSize: 11, fontWeight: "700" },
  chev: { fontSize: 18, fontWeight: "900" },
  empty: { padding: spacing.lg, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, gap: 6 },
  emptyTitle: { fontSize: 16, fontWeight: "900" },
  emptyCopy: { fontSize: 12, lineHeight: 18 },
});
