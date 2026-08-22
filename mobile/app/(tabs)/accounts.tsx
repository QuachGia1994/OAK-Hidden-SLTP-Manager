import * as Haptics from "expo-haptics";
import { useMemo, useState } from "react";
import { Linking, Pressable, RefreshControl, StyleSheet, Switch, Text, View } from "react-native";
import Animated, { FadeIn } from "react-native-reanimated";
import { GlassCard, Metric, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { API_BASE } from "@/lib/api";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import type { Provider, ProviderAccount } from "@/lib/types";
import { useOakData } from "@/state/data";

function ProviderTabs({ value, onChange, counts }: { value: Provider; onChange: (value: Provider) => void; counts: Record<Provider, number> }) {
  const theme = useOakTheme();
  return (
    <View style={[styles.tabs, { borderColor: theme.border, backgroundColor: theme.raised }]}>
      {(["ctrader", "mt5"] as const).map((provider) => {
        const active = value === provider;
        return (
          <Pressable
            key={provider}
            onPress={() => {
              Haptics.selectionAsync();
              onChange(provider);
            }}
            style={[styles.tab, { backgroundColor: active ? theme.surface : "transparent", borderColor: active ? `${theme.accent}66` : "transparent" }]}
          >
            <Text style={[styles.tabText, { color: active ? theme.text : theme.muted }]}>{provider === "ctrader" ? "cTrader" : "MT5"}</Text>
            <View style={[styles.count, { backgroundColor: active ? theme.accent : theme.surface }]}>
              <Text style={[styles.countText, { color: active ? "#fff" : theme.muted }]}>{counts[provider]}</Text>
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

function AccountCard({ account, busy, onToggle }: { account: ProviderAccount; busy: boolean; onToggle: (next: boolean) => void }) {
  const theme = useOakTheme();
  const bridgeOnline = account.provider === "mt5" && Boolean(account.bridgeOnline);
  const statusTone = account.provider === "mt5" ? (bridgeOnline ? "online" : "danger") : (account.enabled ? "online" : "muted");
  const statusLabel = account.provider === "mt5" ? (bridgeOnline ? "BRIDGE ONLINE" : "BRIDGE OFFLINE") : (account.enabled ? "CONTROL ENABLED" : "CONTROL OFF");

  return (
    <Animated.View entering={FadeIn.duration(180)}>
      <GlassCard>
        <View style={styles.cardHead}>
          <View style={styles.cardTitleWrap}>
            <View style={styles.badgeRow}>
              <Pill label={account.provider.toUpperCase()} tone="accent" />
              <Pill label={account.environment.toUpperCase()} />
              <Pill label={statusLabel} tone={statusTone} />
            </View>
            <Text style={[styles.accountTitle, { color: theme.text }]}>{account.label}</Text>
            <Text style={[styles.accountMeta, { color: theme.muted }]}>{account.broker} · #{account.externalAccountId}{account.isDefault ? " · DEFAULT" : ""}</Text>
          </View>
          <Switch
            value={account.enabled}
            disabled={busy}
            onValueChange={onToggle}
            trackColor={{ false: theme.border, true: `${theme.accent}88` }}
            thumbColor={account.enabled ? theme.accent : theme.muted}
          />
        </View>

        <View style={[styles.divider, { backgroundColor: theme.border }]} />
        <View style={styles.metricGrid}>
          <Metric label="FX SL / TP" value={`${account.fxSlPoints} / ${account.fxTpPoints}`} />
          <Metric label="GOLD SL / TP" value={`${account.goldSlPoints} / ${account.goldTpPoints}`} />
        </View>

        {account.provider === "mt5" ? (
          <View style={styles.detailLine}>
            <Text style={[styles.detailLabel, { color: theme.muted }]}>Bridge profile</Text>
            <Text style={[styles.detailValue, { color: theme.text }]}>{account.bridgeProfile || "—"}</Text>
            {account.bridgeVersion ? <Text style={[styles.detailTail, { color: theme.muted }]}>EA {account.bridgeVersion}</Text> : null}
          </View>
        ) : account.manager ? (
          <View style={styles.detailLine}>
            <Text style={[styles.detailLabel, { color: theme.muted }]}>Auto Manager</Text>
            <Text style={[styles.detailValue, { color: account.manager.managerEnabled ? theme.online : theme.muted }]}>{account.manager.managerEnabled ? "ON" : "OFF"}</Text>
            <Text style={[styles.detailTail, { color: theme.muted }]}>BE {account.manager.breakEvenAtR}R · Close {account.manager.closeAtR}R</Text>
          </View>
        ) : null}
      </GlassCard>
    </Animated.View>
  );
}

export default function AccountsScreen() {
  const theme = useOakTheme();
  const { accounts, refreshing, error, refresh, toggleAccount } = useOakData();
  const [provider, setProvider] = useState<Provider>("ctrader");
  const [busyId, setBusyId] = useState("");
  const counts = useMemo(() => ({
    ctrader: accounts?.accounts.filter((item) => item.provider === "ctrader").length || 0,
    mt5: accounts?.accounts.filter((item) => item.provider === "mt5").length || 0,
  }), [accounts]);
  const rows = useMemo(() => accounts?.accounts.filter((item) => item.provider === provider) || [], [accounts, provider]);
  const providerOnline = provider === "ctrader" ? Boolean(accounts?.providers.ctrader.connected) : Boolean(accounts?.providers.mt5.connected);

  async function changeEnabled(account: ProviderAccount, enabled: boolean) {
    setBusyId(account.id);
    try {
      await toggleAccount(account.id, enabled);
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setBusyId("");
    }
  }

  return (
    <OakScreen
      eyebrow="OAK / PROVIDERS"
      title="Accounts"
      subtitle="Native provider control. cTrader and MT5 stay separated while sharing the same Vercel account API."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.accent} />}
    >
      <ProviderTabs value={provider} onChange={setProvider} counts={counts} />

      <GlassCard>
        <View style={styles.providerStatus}>
          <View style={styles.providerStatusCopy}>
            <Pill label={providerOnline ? "ONLINE" : "OFFLINE"} tone={providerOnline ? "online" : "danger"} />
            <Text style={[styles.providerName, { color: theme.text }]}>{provider === "ctrader" ? "cTrader Cloud" : "MT5 OAK EA"}</Text>
            <Text style={[styles.providerCopy, { color: theme.muted }]}>
              {provider === "ctrader"
                ? `OAuth scope: ${accounts?.providers.ctrader.scope || "—"}`
                : "Outbound bridge · heartbeat from OAK_Cloud_Manager_EA"}
            </Text>
          </View>
          <Pressable onPress={() => Linking.openURL(`${API_BASE}/accounts`)} style={[styles.webButton, { borderColor: theme.border, backgroundColor: theme.raised }]}>
            <Text style={[styles.webButtonText, { color: theme.text }]}>WEB MANAGER ↗</Text>
          </Pressable>
        </View>
      </GlassCard>

      {error ? <View style={[styles.errorBox, { borderColor: `${theme.danger}66`, backgroundColor: `${theme.danger}12` }]}><Text style={{ color: theme.danger }}>{error}</Text></View> : null}

      <SectionTitle title={provider === "ctrader" ? "cTrader accounts" : "MT5 accounts"} meta={`${rows.filter((item) => item.enabled).length}/${rows.length} enabled`} />
      <View style={styles.list}>
        {rows.map((account) => (
          <AccountCard key={account.id} account={account} busy={busyId === account.id} onToggle={(next) => changeEnabled(account, next)} />
        ))}
        {!rows.length ? (
          <View style={[styles.emptyBox, { borderColor: theme.border, backgroundColor: theme.surface }]}>
            <Text style={[styles.emptyTitle, { color: theme.text }]}>No {provider === "ctrader" ? "cTrader" : "MT5"} accounts</Text>
            <Text style={[styles.emptyCopy, { color: theme.muted }]}>Use the web manager for OAuth connect, sync, or MT5 account registration.</Text>
          </View>
        ) : null}
      </View>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  tabs: { flexDirection: "row", padding: 4, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, gap: 4 },
  tab: { flex: 1, minHeight: 44, borderRadius: radius.sm, borderWidth: StyleSheet.hairlineWidth, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  tabText: { fontSize: 13, fontWeight: "900" },
  count: { minWidth: 22, height: 22, paddingHorizontal: 6, borderRadius: 999, alignItems: "center", justifyContent: "center" },
  countText: { fontSize: 10, fontWeight: "900" },
  providerStatus: { gap: spacing.md },
  providerStatusCopy: { gap: 8 },
  providerName: { fontSize: 22, fontWeight: "900", letterSpacing: -0.6 },
  providerCopy: { fontSize: 12, lineHeight: 18 },
  webButton: { alignSelf: "flex-start", minHeight: 40, paddingHorizontal: 12, borderRadius: radius.sm, borderWidth: StyleSheet.hairlineWidth, alignItems: "center", justifyContent: "center" },
  webButtonText: { fontSize: 10, fontWeight: "900", letterSpacing: 0.8 },
  errorBox: { padding: spacing.md, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  list: { gap: spacing.sm },
  cardHead: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: spacing.md },
  cardTitleWrap: { flex: 1, gap: 7 },
  badgeRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  accountTitle: { fontSize: 19, fontWeight: "900", letterSpacing: -0.4 },
  accountMeta: { fontSize: 11, fontWeight: "700" },
  divider: { height: StyleSheet.hairlineWidth, marginVertical: spacing.md },
  metricGrid: { flexDirection: "row", gap: spacing.md },
  detailLine: { marginTop: spacing.md, flexDirection: "row", alignItems: "center", gap: 8 },
  detailLabel: { fontSize: 11, fontWeight: "800" },
  detailValue: { fontSize: 11, fontWeight: "900" },
  detailTail: { flex: 1, textAlign: "right", fontSize: 10, fontWeight: "700" },
  emptyBox: { padding: spacing.lg, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, gap: 6 },
  emptyTitle: { fontSize: 16, fontWeight: "900" },
  emptyCopy: { fontSize: 12, lineHeight: 18 },
});
