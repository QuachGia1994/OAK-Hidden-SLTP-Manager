import * as Haptics from "expo-haptics";
import Constants from "expo-constants";
import { Linking, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { GlassCard, Metric, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { API_BASE } from "@/lib/api";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useAuth } from "@/state/auth";
import { useOakData } from "@/state/data";

const MENU = [
  ["Tài khoản", "user"],
  ["Quản lý VIP", "crown"],
  ["Cài đặt cảnh báo", "bell"],
  ["Kết nối Telegram", "send"],
  ["Ngôn ngữ", "Tiếng Việt"],
  ["Giao diện", "Dark"],
  ["Trợ giúp & Hướng dẫn", "?"],
] as const;

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
      eyebrow="OAK / MORE"
      title="More"
      subtitle="Thiết lập native shell, cảnh báo, Telegram và trạng thái backend."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <GlassCard glow="purple">
        <View style={styles.profileRow}>
          <View style={[styles.avatar, { backgroundColor: `${theme.purple}32`, borderColor: `${theme.purple}66` }]}><Text style={[styles.avatarText, { color: theme.text }]}>◉</Text></View>
          <View style={styles.profileCopy}>
            <Text style={[styles.profileTitle, { color: theme.text }]}>OAK SLTP VIP</Text>
            <Text style={[styles.profileMeta, { color: theme.muted }]}>VIP UNLOCKED · v{version}</Text>
          </View>
          <Pill label="♛" tone="warning" />
        </View>
      </GlassCard>

      <View style={styles.menuList}>
        {MENU.map(([label, right]) => (
          <GlassCard key={label} glow="muted">
            <View style={styles.menuItem}>
              <Text style={[styles.menuIcon, { color: theme.muted }]}>{right.length === 1 ? right : "○"}</Text>
              <Text style={[styles.menuLabel, { color: theme.text }]}>{label}</Text>
              <Text style={[styles.menuRight, { color: theme.muted }]}>{right.length > 1 ? right : "›"}</Text>
            </View>
          </GlassCard>
        ))}
      </View>

      <SectionTitle title="System" meta={online ? "online" : "offline"} />
      <GlassCard glow={online ? "buy" : "warning"}>
        <View style={styles.metrics}>
          <Metric label="H1 FEED" value={h1 ? "READY" : "WAIT"} tone={h1 ? "buy" : "warning"} />
          <Metric label="ACCOUNTS" value={String(accounts?.accounts.length || 0)} tone="accent" />
        </View>
        <Text selectable style={[styles.endpoint, { color: theme.muted }]}>{API_BASE}</Text>
      </GlassCard>

      {error ? <View style={[styles.errorBox, { borderColor: `${theme.danger}66`, backgroundColor: `${theme.danger}12` }]}><Text style={{ color: theme.danger }}>{error}</Text></View> : null}

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
  profileRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  avatar: { width: 54, height: 54, borderRadius: 18, borderWidth: StyleSheet.hairlineWidth, alignItems: "center", justifyContent: "center" },
  avatarText: { fontSize: 24, fontWeight: "900" },
  profileCopy: { flex: 1, gap: 4 },
  profileTitle: { fontSize: 17, fontWeight: "900" },
  profileMeta: { fontSize: 11, fontWeight: "800" },
  menuList: { gap: spacing.sm },
  menuItem: { flexDirection: "row", alignItems: "center", gap: spacing.md, minHeight: 30 },
  menuIcon: { width: 22, fontSize: 14, fontWeight: "900" },
  menuLabel: { flex: 1, fontSize: 13, fontWeight: "800" },
  menuRight: { fontSize: 12, fontWeight: "900" },
  metrics: { flexDirection: "row", gap: spacing.md },
  endpoint: { marginTop: spacing.md, fontSize: 11, fontWeight: "700" },
  errorBox: { padding: spacing.md, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  actions: { gap: spacing.sm },
  action: { minHeight: 50, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  actionText: { fontSize: 11, fontWeight: "900", letterSpacing: 1 },
});
