import { useLocalSearchParams, useRouter } from "expo-router";
import { LinearGradient } from "expo-linear-gradient";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { GlassCard, Pill } from "@/components/ui";
import { findAlert, latestH1Date } from "@/lib/h1";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useOakData } from "@/state/data";

function Row({ label, value, tone }: { label: string; value: string; tone?: "warning" | "buy" | "sell" }) {
  const theme = useOakTheme();
  const color = tone === "warning" ? theme.warning : tone === "buy" ? theme.buy : tone === "sell" ? theme.sell : theme.text;
  return (
    <View style={[styles.detailRow, { borderBottomColor: theme.border }]}>
      <Text style={[styles.detailLabel, { color: theme.muted }]}>{label}</Text>
      <Text style={[styles.detailValue, { color }]}>{value}</Text>
    </View>
  );
}

export default function SignalDetailScreen() {
  const theme = useOakTheme();
  const router = useRouter();
  const params = useLocalSearchParams<{ symbol: string; hour: string }>();
  const { h1 } = useOakData();
  const symbol = String(params.symbol || "");
  const hour = Number(params.hour || 0);
  const alert = findAlert(h1, symbol, hour);
  const date = latestH1Date(h1);

  return (
    <LinearGradient colors={[theme.canvas, theme.raised]} style={styles.flex}>
      <SafeAreaView style={styles.flex} edges={["top", "bottom"]}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <View style={styles.handleWrap}><View style={[styles.handle, { backgroundColor: theme.border }]} /></View>
          <View style={styles.head}>
            <View style={styles.headCopy}>
              <Text style={[styles.eyebrow, { color: theme.accent }]}>H1 SIGNAL DETAIL</Text>
              <Text style={[styles.title, { color: theme.text }]}>{symbol || "Signal"} · H{String(hour).padStart(2, "0")}</Text>
              <Text style={[styles.subtitle, { color: theme.muted }]}>{date || "Current broker day"}</Text>
            </View>
            <Pressable onPress={() => router.back()} style={[styles.close, { borderColor: theme.border, backgroundColor: theme.surface }]}>
              <Text style={[styles.closeText, { color: theme.text }]}>×</Text>
            </Pressable>
          </View>

          {!alert ? (
            <GlassCard>
              <Text style={[styles.missing, { color: theme.muted }]}>This signal is no longer present in the current feed.</Text>
            </GlassCard>
          ) : (
            <>
              <GlassCard>
                <View style={styles.heroState}>
                  <View style={styles.badges}>
                    {alert.baseDirection ? <Pill label={`BASE ${alert.baseDirection}`} /> : null}
                  </View>
                  <Text style={[styles.heroSignal, { color: alert.signal === "SELL" ? theme.sell : theme.buy }]}>
                    {alert.signal}
                  </Text>
                </View>
              </GlassCard>

              <GlassCard>
                <Row label="Entry H1 base" value={`${alert.baseSymbol} · H${String(alert.baseHour || 0).padStart(2, "0")}:00 · ${alert.baseDirection || "—"}`} />
                <Row label="Base signal" value={alert.baseSignal || "—"} tone={alert.baseSignal === "SELL" ? "sell" : "buy"} />
                <Row label="Final signal" value={alert.signal || "—"} tone={alert.signal === "SELL" ? "sell" : "buy"} />
              </GlassCard>

              <GlassCard>
                <Text style={[styles.sectionLabel, { color: theme.muted }]}>GIỜ VÀO/ĐÓNG LỆNH</Text>
                <Text style={[styles.bars, { color: theme.text }]}>Do bạn tự đặt qua lệnh Telegram (hẹn giờ).</Text>
              </GlassCard>
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { padding: spacing.lg, gap: spacing.md },
  handleWrap: { alignItems: "center", paddingBottom: 4 },
  handle: { width: 44, height: 5, borderRadius: 999 },
  head: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: spacing.md },
  headCopy: { flex: 1, gap: 5 },
  eyebrow: { fontSize: 10, fontWeight: "900", letterSpacing: 1.6 },
  title: { fontSize: 27, fontWeight: "900", letterSpacing: -1 },
  subtitle: { fontSize: 12, fontWeight: "700" },
  close: { width: 42, height: 42, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  closeText: { fontSize: 25, lineHeight: 27, fontWeight: "700" },
  heroState: { gap: spacing.sm },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  heroSignal: { fontSize: 34, fontWeight: "900", letterSpacing: -1.2 },
  detailRow: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md, borderBottomWidth: StyleSheet.hairlineWidth },
  detailLabel: { fontSize: 11, fontWeight: "800" },
  detailValue: { flex: 1, textAlign: "right", fontSize: 12, fontWeight: "900" },
  sectionLabel: { fontSize: 10, fontWeight: "900", letterSpacing: 1 },
  bars: { marginTop: 8, fontSize: 12, lineHeight: 20, fontWeight: "800" },
  missing: { fontSize: 13, lineHeight: 20 },
});
