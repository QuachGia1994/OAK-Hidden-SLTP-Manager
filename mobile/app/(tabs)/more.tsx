import * as Haptics from "expo-haptics";
import Constants from "expo-constants";
import { Linking, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { GlassCard, Metric, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { API_BASE } from "@/lib/api";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useAuth } from "@/state/auth";
import { useOakData } from "@/state/data";

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

export default function MoreScreen() {
  const theme = useOakTheme();
  const { signOut } = useAuth();
  const { app, h1, accounts, refreshing, error, refresh } = useOakData();
  const system = app?.system;
  const version = Constants.expoConfig?.version || "0.1.0";
  const backendMode = system ? "ONLINE" : h1 || accounts ? "FALLBACK" : "OFFLINE";
  const backendTone = system ? "online" : h1 || accounts ? "warning" : "danger";

  async function exit() {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    await signOut();
  }

  return (
    <OakScreen
      eyebrow="OAK / SYSTEM"
      title="More"
      subtitle="Trạng thái thật của app backend, H1 feed và provider connections."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <GlassCard glow={system ? "buy" : "warning"}>
        <View style={styles.statusHead}>
          <View style={styles.statusCopy}>
            <Text style={[styles.statusTitle, { color: theme.text }]}>OAK Gatekeeper Mobile</Text>
            <Text style={[styles.statusMeta, { color: theme.muted }]}>App v{version} · payload v{system?.payloadVersion ?? "—"}</Text>
          </View>
          <Pill label={backendMode} tone={backendTone} />
        </View>
        <View style={styles.metrics}>
          <Metric label="API LATENCY" value={system ? `${system.latencyMs}ms` : "—"} tone={system ? "buy" : "warning"} />
          <Metric label="H1 FEED" value={system?.h1.ready ? "READY" : "WAIT"} tone={system?.h1.ready ? "buy" : "warning"} />
        </View>
      </GlassCard>

      <SectionTitle title="Backend" meta={system?.apiStatus || backendMode} />
      <GlassCard glow="accent">
        <View style={styles.detailList}>
          <Detail label="SERVER TIME" value={formatTimestamp(system?.serverTime)} />
          <Detail label="ENDPOINT" value={API_BASE} selectable />
        </View>
      </GlassCard>

      <SectionTitle title="H1 feed" meta={system?.h1.brokerDate || "—"} />
      <GlassCard glow={system?.h1.ready ? "buy" : "warning"}>
        <View style={styles.metricGrid}>
          <Metric label="SCHEMA" value={system?.h1.schemaVersion ? `v${system.h1.schemaVersion}` : "—"} />
          <Metric label="RULE" value={system?.h1.signalRuleVersion ? `v${system.h1.signalRuleVersion}` : "—"} />
          <Metric label="HISTORY" value={`${system?.h1.historyDays ?? 0} days`} tone="accent" />
          <Metric label="SYMBOLS / BLOCKS" value={`${system?.h1.symbolCount ?? 0} / ${system?.h1.blockCount ?? 0}`} />
        </View>
        <View style={styles.detailList}>
          <Detail label="PROFILE" value={system?.h1.profile || "—"} />
          <Detail label="PUBLISHED" value={formatTimestamp(system?.h1.publishedAt)} />
        </View>
      </GlassCard>

      <SectionTitle title="Providers" meta={`${system?.accounts.enabled ?? 0}/${system?.accounts.total ?? 0} enabled`} />
      <GlassCard glow={system?.providers.ctrader.connected || system?.providers.mt5.connected ? "buy" : "warning"}>
        <View style={styles.providerRow}>
          <View style={styles.providerCopy}>
            <Text style={[styles.providerName, { color: theme.text }]}>cTrader</Text>
            <Text style={[styles.providerMeta, { color: theme.muted }]}>Scope: {system?.providers.ctrader.scope || "none"}</Text>
          </View>
          <Pill label={system?.providers.ctrader.connected ? "CONNECTED" : "OFFLINE"} tone={system?.providers.ctrader.connected ? "online" : "warning"} />
        </View>
        <View style={[styles.divider, { backgroundColor: theme.border }]} />
        <View style={styles.providerRow}>
          <View style={styles.providerCopy}>
            <Text style={[styles.providerName, { color: theme.text }]}>MT5</Text>
            <Text style={[styles.providerMeta, { color: theme.muted }]}>{system?.providers.mt5.onlineAccounts ?? 0}/{system?.providers.mt5.totalAccounts ?? 0} bridge online</Text>
          </View>
          <Pill label={system?.providers.mt5.connected ? "CONNECTED" : "OFFLINE"} tone={system?.providers.mt5.connected ? "online" : "warning"} />
        </View>
      </GlassCard>

      <SectionTitle title="Accounts" meta={`${system?.accounts.total ?? accounts?.accounts.length ?? 0} total`} />
      <GlassCard glow="muted">
        <View style={styles.metrics}>
          <Metric label="ENABLED" value={String(system?.accounts.enabled ?? accounts?.accounts.filter((item) => item.enabled).length ?? 0)} tone="accent" />
          <Metric label="DEFAULT" value={system?.accounts.defaultAccountId ? "SET" : "NONE"} />
        </View>
        <Detail label="DEFAULT ID" value={system?.accounts.defaultAccountId || "—"} selectable />
      </GlassCard>

      {error ? (
        <View style={[styles.errorBox, { borderColor: `${theme.danger}66`, backgroundColor: `${theme.danger}12` }]}>
          <Text style={{ color: theme.danger }}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.actions}>
        <Pressable onPress={refresh} style={({ pressed }) => [styles.action, { borderColor: theme.border, backgroundColor: theme.surface, opacity: pressed ? 0.72 : 1 }]}>
          <Text style={[styles.actionText, { color: theme.text }]}>REFRESH BACKEND</Text>
        </Pressable>
        <Pressable onPress={() => Linking.openURL(API_BASE)} style={({ pressed }) => [styles.action, { borderColor: theme.border, backgroundColor: theme.surface, opacity: pressed ? 0.72 : 1 }]}>
          <Text style={[styles.actionText, { color: theme.text }]}>OPEN WEB ↗</Text>
        </Pressable>
        <Pressable onPress={exit} style={({ pressed }) => [styles.action, { borderColor: `${theme.danger}66`, backgroundColor: `${theme.danger}10`, opacity: pressed ? 0.72 : 1 }]}>
          <Text style={[styles.actionText, { color: theme.danger }]}>SIGN OUT DEVICE</Text>
        </Pressable>
      </View>
    </OakScreen>
  );
}

function Detail({ label, value, selectable = false }: { label: string; value: string; selectable?: boolean }) {
  const theme = useOakTheme();
  return (
    <View style={styles.detailRow}>
      <Text style={[styles.detailLabel, { color: theme.muted }]}>{label}</Text>
      <Text selectable={selectable} style={[styles.detailValue, { color: theme.text }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  statusHead: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginBottom: spacing.md },
  statusCopy: { flex: 1, gap: 4 },
  statusTitle: { fontSize: 18, fontWeight: "900" },
  statusMeta: { fontSize: 11, fontWeight: "800" },
  metrics: { flexDirection: "row", gap: spacing.md },
  metricGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginBottom: spacing.md },
  detailList: { gap: spacing.sm, marginTop: spacing.md },
  detailRow: { gap: 4 },
  detailLabel: { fontSize: 9, fontWeight: "900", letterSpacing: 1 },
  detailValue: { fontSize: 12, lineHeight: 18, fontWeight: "800" },
  providerRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  providerCopy: { flex: 1, gap: 4 },
  providerName: { fontSize: 15, fontWeight: "900" },
  providerMeta: { fontSize: 11, fontWeight: "700" },
  divider: { height: StyleSheet.hairlineWidth, marginVertical: spacing.md },
  errorBox: { padding: spacing.md, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  actions: { gap: spacing.sm },
  action: { minHeight: 50, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  actionText: { fontSize: 11, fontWeight: "900", letterSpacing: 1 },
});
