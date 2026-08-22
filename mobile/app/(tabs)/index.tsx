import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { GlassCard, Metric, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { alertsForSymbol, latestH1Date } from "@/lib/h1";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import type { H1SignalAlert } from "@/lib/types";
import { useOakData } from "@/state/data";

function SignalRow({ symbol, hour, alert }: { symbol: string; hour: number; alert: H1SignalAlert | null }) {
  const theme = useOakTheme();
  const router = useRouter();
  const pure = alert?.patternKind === "sw3Pure";
  const blocked = alert?.tradeAllowed === false;
  const signalColor = alert?.signal === "SELL" ? theme.sell : theme.buy;

  async function open() {
    if (!alert) return;
    await Haptics.selectionAsync();
    router.push({ pathname: "/signal/[symbol]/[hour]", params: { symbol, hour: String(hour) } } as never);
  }

  return (
    <Pressable
      disabled={!alert}
      onPress={open}
      style={({ pressed }) => [
        styles.signalRow,
        {
          borderColor: blocked ? `${theme.warning}AA` : pure ? `${theme.warning}66` : theme.border,
          backgroundColor: blocked ? `${theme.warning}15` : theme.surface,
          opacity: pressed ? 0.72 : 1,
        },
      ]}
    >
      <View style={styles.hourRail}>
        <Text style={[styles.hourLabel, { color: alert ? theme.text : theme.muted }]}>H{String(hour).padStart(2, "0")}</Text>
        <View style={[styles.hourDot, { backgroundColor: blocked ? theme.warning : alert ? signalColor : theme.border }]} />
      </View>
      <View style={styles.signalBody}>
        {!alert ? (
          <Text style={[styles.empty, { color: theme.muted }]}>No pattern</Text>
        ) : (
          <>
            <View style={styles.signalTopline}>
              <View style={styles.badges}>
                {pure ? <Pill label="⚠ PURE" tone="warning" /> : <Pill label={alert.patternKind === "sw2" ? "SW2" : "SW NORMAL"} />}
                {blocked ? <Pill label="BLOCK / NOT TRADE" tone="warning" /> : <Pill label="ACTIVE" tone="online" />}
              </View>
              <Text style={[styles.signal, { color: blocked ? theme.warning : signalColor }]}>{blocked ? "BLOCK" : alert.signal || "—"}</Text>
            </View>
            <Text style={[styles.pattern, { color: theme.muted }]}>{alert.pattern.replaceAll(" ", " · ")} · scanner {alert.scannerBase}</Text>
            {blocked ? <Text style={[styles.cooldown, { color: theme.warning }]}>Cooldown from H{String(alert.blockedByPureSlot || 0).padStart(2, "0")} · calculated {alert.signal}</Text> : null}
          </>
        )}
      </View>
    </Pressable>
  );
}

export default function EngineScreen() {
  const theme = useOakTheme();
  const { h1, refreshing, error, refresh } = useOakData();
  const [symbol, setSymbol] = useState("");
  const date = latestH1Date(h1);

  useEffect(() => {
    if (!h1?.symbols.length) return;
    if (!symbol || !h1.symbols.includes(symbol)) setSymbol(h1.symbols[0]);
  }, [h1, symbol]);

  const byHour = useMemo(() => new Map(alertsForSymbol(h1, symbol).map((alert) => [alert.slotHour, alert])), [h1, symbol]);
  const updated = h1?.publishedAt ? new Date(h1.publishedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

  return (
    <OakScreen
      eyebrow="OAK / H1 CLOUD"
      title="Engine"
      subtitle="Native H1 command view. Pure-pair state and cooldown are normalized by the Vercel backend before rendering."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.accent} />}
    >
      <GlassCard>
        <View style={styles.liveHead}>
          <View style={styles.liveCopy}>
            <Pill label="LIVE · CTRADER ICMARKETS" tone="online" />
            <Text style={[styles.liveTitle, { color: theme.text }]}>H1 scanner feed</Text>
          </View>
          <View style={styles.metrics}>
            <Metric label="BROKER DAY" value={date || "—"} />
            <Metric label="UPDATED" value={updated} />
          </View>
        </View>
      </GlassCard>

      {error ? <View style={[styles.errorBox, { borderColor: `${theme.danger}66`, backgroundColor: `${theme.danger}12` }]}><Text style={{ color: theme.danger }}>{error}</Text></View> : null}

      <SectionTitle title="Symbols" meta={`${h1?.symbols.length || 0} markets`} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.symbolStrip}>
        {(h1?.symbols || []).map((item) => {
          const active = item === symbol;
          return (
            <Pressable
              key={item}
              onPress={() => {
                setSymbol(item);
                Haptics.selectionAsync();
              }}
              style={[styles.symbolChip, { borderColor: active ? theme.accent : theme.border, backgroundColor: active ? `${theme.accent}18` : theme.surface }]}
            >
              <Text style={[styles.symbolText, { color: active ? theme.accent : theme.muted }]}>{item}</Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <SectionTitle title="H1 timeline" meta={symbol || "—"} />
      <View style={styles.timeline}>
        {(h1?.hours || Array.from({ length: 15 }, (_, index) => index + 3)).map((hour) => (
          <SignalRow key={hour} symbol={symbol} hour={hour} alert={byHour.get(hour) || null} />
        ))}
      </View>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  liveHead: { gap: spacing.lg },
  liveCopy: { gap: spacing.sm },
  liveTitle: { fontSize: 22, fontWeight: "900", letterSpacing: -0.6 },
  metrics: { flexDirection: "row", gap: spacing.md },
  errorBox: { padding: spacing.md, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  symbolStrip: { gap: spacing.sm, paddingRight: spacing.lg },
  symbolChip: { minHeight: 40, paddingHorizontal: 14, alignItems: "center", justifyContent: "center", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.pill },
  symbolText: { fontSize: 12, fontWeight: "900", letterSpacing: 0.5 },
  timeline: { gap: spacing.sm },
  signalRow: { minHeight: 86, flexDirection: "row", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, overflow: "hidden" },
  hourRail: { width: 64, alignItems: "center", justifyContent: "center", gap: 8 },
  hourLabel: { fontSize: 14, fontWeight: "900", letterSpacing: 0.4 },
  hourDot: { width: 6, height: 6, borderRadius: 999 },
  signalBody: { flex: 1, justifyContent: "center", gap: 7, paddingVertical: 12, paddingRight: 13 },
  signalTopline: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 6, flex: 1 },
  signal: { fontSize: 20, fontWeight: "900", letterSpacing: -0.4 },
  pattern: { fontSize: 11, fontWeight: "700" },
  cooldown: { fontSize: 11, fontWeight: "800" },
  empty: { fontSize: 12, fontWeight: "700" },
});
