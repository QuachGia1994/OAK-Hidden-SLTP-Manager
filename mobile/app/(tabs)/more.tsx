import * as Haptics from "expo-haptics";
import Constants from "expo-constants";
import { Linking, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { GlassCard, Metric, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { API_BASE } from "@/lib/api";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useAuth } from "@/state/auth";
import { useOakData } from "@/state/data";

export default function MoreScreen() {
  const theme = useOakTheme();
  const { signOut } = useAuth();
  const { h1, accounts, refreshing, error, refresh } = useOakData();
  const version = Constants.expoConfig?.version || "0.1.0";
  const online = Boolean(h1 || accounts);

  async function exit() {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    await signOut();
  }

  return (
    <OakScreen
      eyebrow="OAK / SYSTEM"
      title="More"
      subtitle="Native shell settings and Vercel connection state. Broker and Redis credentials remain server-side."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.accent} />}
    >
      <GlassCard>
        <View style={styles.heroCard}>
          <View style={styles.brandRow}>
            <View style={[styles.logo, { borderColor: `${theme.accent}88`, backgroundColor: `${theme.accent}18` }]}>
              <Text style={[styles.logoText, { color: theme.accent }]}>OAK</Text>
            </View>
            <View style={styles.brandCopy}>
              <Pill label={online ? "VERCEL ONLINE" : "BACKEND OFFLINE"} tone={online ? "online" : "danger"} />
              <Text style={[styles.brandTitle, { color: theme.text }]}>Gatekeeper Mobile</Text>
              <Text style={[styles.brandMeta, { color: theme.muted }]}>Expo native shell · v{version}</Text>
            </View>
          </View>
          <View style={[styles.divider, { backgroundColor: theme.border }]} />
          <View style={styles.metrics}>
            <Metric label="H1 FEED" value={h1 ? "READY" : "WAIT"} />
            <Metric label="ACCOUNTS" value={String(accounts?.accounts.length || 0)} />
          </View>
        </View>
      </GlassCard>

      {error ? <View style={[styles.errorBox, { borderColor: `${theme.danger}66`, backgroundColor: `${theme.danger}12` }]}><Text style={{ color: theme.danger }}>{error}</Text></View> : null}

      <SectionTitle title="Backend" />
      <GlassCard>
        <View style={styles.settingGroup}>
          <Text style={[styles.settingLabel, { color: theme.muted }]}>API BASE</Text>
          <Text selectable style={[styles.endpoint, { color: theme.text }]}>{API_BASE}</Text>
          <Text style={[styles.settingHint, { color: theme.muted }]}>Admin API key is stored in SecureStore on this device and sent only as the `x-api-key` request header.</Text>
        </View>
      </GlassCard>

      <View style={styles.actions}>
        <Pressable onPress={refresh} style={({ pressed }) => [styles.action, { borderColor: theme.border, backgroundColor: theme.surface, opacity: pressed ? 0.72 : 1 }]}>
          <Text style={[styles.actionText, { color: theme.text }]}>REFRESH CLOUD</Text>
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

const styles = StyleSheet.create({
  heroCard: { gap: spacing.md },
  brandRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  logo: { width: 58, height: 58, borderWidth: StyleSheet.hairlineWidth, borderRadius: 18, alignItems: "center", justifyContent: "center" },
  logoText: { fontSize: 14, fontWeight: "900", letterSpacing: 1.4 },
  brandCopy: { flex: 1, gap: 6 },
  brandTitle: { fontSize: 20, fontWeight: "900", letterSpacing: -0.5 },
  brandMeta: { fontSize: 11, fontWeight: "700" },
  divider: { height: StyleSheet.hairlineWidth },
  metrics: { flexDirection: "row", gap: spacing.md },
  errorBox: { padding: spacing.md, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  settingGroup: { gap: 8 },
  settingLabel: { fontSize: 10, fontWeight: "900", letterSpacing: 1 },
  endpoint: { fontSize: 13, fontWeight: "800" },
  settingHint: { fontSize: 12, lineHeight: 18 },
  actions: { gap: spacing.sm },
  action: { minHeight: 50, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  actionText: { fontSize: 11, fontWeight: "900", letterSpacing: 1 },
});
