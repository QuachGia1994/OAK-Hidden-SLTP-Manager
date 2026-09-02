import * as Haptics from "expo-haptics";
import { useEffect, useMemo, useState } from "react";
import { Modal, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { GlassCard, OakScreen, Pill, SectionTitle } from "@/components/ui";
import { h1Hours, latestH1Date, signalFor } from "@/lib/h1";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useOakData } from "@/state/data";

const FALLBACK_SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD", "GBPAUD"];
const TEMP_HIDDEN_H1_ROWS = new Set(["GBPCAD", "GBPJPY"]);

function isoDaysAgo(days: number) {
  const value = new Date();
  value.setDate(value.getDate() - days);
  return value.toISOString().slice(0, 10);
}

function fallbackDates(count = 90) {
  return Array.from({ length: count }, (_, index) => isoDaysAgo(index));
}

export default function CalendarScreen() {
  const theme = useOakTheme();
  const { h1, app, refreshing, refresh } = useOakData();
  const [pickerOpen, setPickerOpen] = useState(false);
  const dates = useMemo(() => {
    const backendDates = app?.calendar?.dates || [];
    if (backendDates.length) return backendDates;
    const feedDates = Object.keys(h1?.days || {}).sort().reverse();
    return feedDates.length ? feedDates : fallbackDates();
  }, [app, h1]);
  const latestDate = app?.calendar?.latestDate || latestH1Date(h1) || dates[0] || isoDaysAgo(0);
  const [selectedDate, setSelectedDate] = useState(latestDate);
  const selectedIndex = Math.max(0, dates.indexOf(selectedDate));
  const manualCloseH16 = Boolean(h1?.days?.[selectedDate]?.symbols?.XAUUSD?.alerts?.some((alert) => alert.slotHour === 3 && alert.entryHour === 5));
  const sourceSymbols = app?.calendar?.symbols?.length ? app.calendar.symbols : h1?.symbols?.length ? h1.symbols : FALLBACK_SYMBOLS;
  const symbols = sourceSymbols.filter((symbol) => !TEMP_HIDDEN_H1_ROWS.has(symbol));
  const hours = app?.calendar?.hours?.length ? app.calendar.hours : h1Hours(h1);
  const hasHistory = Boolean(app?.calendar?.hasHistory || Object.keys(h1?.days || {}).length);

  useEffect(() => {
    if (!selectedDate || !dates.includes(selectedDate)) setSelectedDate(latestDate);
  }, [dates, latestDate, selectedDate]);

  async function chooseDate(date: string) {
    setSelectedDate(date);
    setPickerOpen(false);
    await Haptics.selectionAsync();
  }

  async function move(delta: number) {
    const next = Math.max(0, Math.min(dates.length - 1, selectedIndex + delta));
    await chooseDate(dates[next] || selectedDate);
  }

  return (
    <OakScreen
      eyebrow="OAK / H1 CALENDAR"
      title="H1 Calendar"
      subtitle="Lịch block H1 và tín hiệu BUY/SELL theo từng symbol."
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={theme.cyan} />}
    >
      <GlassCard>
        <View style={styles.dateRail}>
          <Pressable style={[styles.arrow, { borderColor: theme.border }]} onPress={() => move(1)}>
            <Text style={[styles.arrowText, { color: theme.text }]}>‹</Text>
          </Pressable>
          <Pressable
            onPress={() => {
              setPickerOpen(true);
              Haptics.selectionAsync();
            }}
            style={[styles.dateBox, { borderColor: theme.cyan, backgroundColor: theme.raised }]}
          >
            <Text style={[styles.dateText, { color: theme.text }]}>{selectedDate}</Text>
            <Text style={[styles.dateMeta, { color: hasHistory ? theme.cyan : theme.warning }]}>
              {hasHistory ? `${selectedIndex + 1}/${dates.length} ngày · bấm để chọn` : "calendar dự phòng · bấm để chọn"}
            </Text>
          </Pressable>
          <Pressable style={[styles.arrow, { borderColor: theme.border }]} onPress={() => move(-1)}>
            <Text style={[styles.arrowText, { color: theme.text }]}>›</Text>
          </Pressable>
        </View>
      </GlassCard>

      <SectionTitle title="Block matrix" meta="Vuốt ngang" />
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={[styles.table, { borderColor: theme.border }]}>
          <View style={[styles.tr, styles.headerRow, { backgroundColor: theme.raised }]}>
            <Text style={[styles.symbolHead, { color: theme.muted }]}>SYMBOL</Text>
            {hours.map((hour) => <Text key={hour} style={[styles.th, { color: hour === 16 && manualCloseH16 ? theme.warning : theme.muted }]}>H{String(hour).padStart(2, "0")}{hour === 16 && manualCloseH16 ? "\nCLOSE" : ""}</Text>)}
          </View>
          {symbols.map((symbol) => (
            <View key={symbol} style={[styles.tr, { borderTopColor: theme.border }]}>
              <Text style={[styles.symbolCell, { color: theme.text }]}>{symbol}</Text>
              {hours.map((hour) => {
                const alert = signalFor(h1, selectedDate, symbol, hour);
                const signal = alert?.signal;
                const manualCloseCell = hour === 16 && manualCloseH16;
                const tone = manualCloseCell ? "warning" : signal === "SELL" ? "sell" : signal === "BUY" ? "buy" : "muted";
                return (
                  <View key={hour} style={[styles.cell, { borderLeftColor: theme.border, backgroundColor: manualCloseCell ? `${theme.warning}18` : alert?.postSignalInverted ? `${theme.warning}20` : "transparent" }]}>
                    {manualCloseCell ? <Pill label="CLOSE" tone={tone} /> : signal ? <Pill label={signal} tone={tone} /> : <Text style={[styles.empty, { color: theme.muted }]}>–</Text>}
                  </View>
                );
              })}
            </View>
          ))}
        </View>
      </ScrollView>

      <GlassCard glow="warning">
        <View style={styles.legendRow}>
          <Pill label="BUY" tone="buy" />
          <Pill label="SELL" tone="sell" />
          <Text style={[styles.legendCopy, { color: theme.muted }]}>Ô nền vàng là block có đảo signal theo rule H1.</Text>
        </View>
      </GlassCard>

      <Modal visible={pickerOpen} transparent animationType="fade" onRequestClose={() => setPickerOpen(false)}>
        <Pressable style={styles.modalOverlay} onPress={() => setPickerOpen(false)}>
          <Pressable style={[styles.modalCard, { backgroundColor: theme.surface, borderColor: theme.cyan }]}>
            <View style={styles.modalHead}>
              <Text style={[styles.modalTitle, { color: theme.text }]}>Chọn ngày H1</Text>
              <Pressable onPress={() => setPickerOpen(false)} style={[styles.closeButton, { borderColor: theme.border }]}>
                <Text style={[styles.closeText, { color: theme.text }]}>×</Text>
              </Pressable>
            </View>
            <ScrollView style={styles.dateList} showsVerticalScrollIndicator={false}>
              {dates.map((date) => {
                const active = date === selectedDate;
                const hasData = Boolean(h1?.days?.[date]);
                return (
                  <Pressable
                    key={date}
                    onPress={() => chooseDate(date)}
                    style={[styles.dateOption, { borderColor: active ? theme.cyan : theme.border, backgroundColor: active ? `${theme.cyan}18` : theme.raised }]}
                  >
                    <Text style={[styles.dateOptionText, { color: active ? theme.cyan : theme.text }]}>{date}</Text>
                    <Text style={[styles.dateOptionMeta, { color: hasData ? theme.buy : theme.muted }]}>{hasData ? "có feed" : "dự phòng"}</Text>
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </OakScreen>
  );
}

const styles = StyleSheet.create({
  dateRail: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  arrow: { width: 44, height: 50, borderRadius: radius.sm, borderWidth: StyleSheet.hairlineWidth, alignItems: "center", justifyContent: "center" },
  arrowText: { fontSize: 28, fontWeight: "900" },
  dateBox: { flex: 1, minHeight: 58, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, alignItems: "center", justifyContent: "center", gap: 4 },
  dateText: { fontSize: 17, fontWeight: "900", letterSpacing: 0.4 },
  dateMeta: { fontSize: 10, fontWeight: "900" },
  table: { overflow: "hidden", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md },
  tr: { minHeight: 58, flexDirection: "row", alignItems: "stretch", borderTopWidth: StyleSheet.hairlineWidth },
  headerRow: { borderTopWidth: 0 },
  symbolHead: { width: 92, padding: spacing.sm, fontSize: 10, fontWeight: "900", letterSpacing: 0.8 },
  symbolCell: { width: 92, padding: spacing.sm, fontSize: 12, fontWeight: "900" },
  th: { width: 70, padding: spacing.sm, textAlign: "center", fontSize: 10, fontWeight: "900" },
  cell: { width: 70, borderLeftWidth: StyleSheet.hairlineWidth, alignItems: "center", justifyContent: "center" },
  empty: { fontSize: 18, fontWeight: "900" },
  legendRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: spacing.sm },
  legendCopy: { flex: 1, minWidth: 160, fontSize: 12, lineHeight: 18, fontWeight: "700" },
  modalOverlay: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.62)", padding: spacing.lg },
  modalCard: { maxHeight: "72%", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.lg, padding: spacing.md, gap: spacing.md },
  modalHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  modalTitle: { fontSize: 20, fontWeight: "900" },
  closeButton: { width: 38, height: 38, alignItems: "center", justifyContent: "center", borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.pill },
  closeText: { fontSize: 24, fontWeight: "900" },
  dateList: { maxHeight: 420 },
  dateOption: { minHeight: 48, marginBottom: 8, paddingHorizontal: spacing.md, borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  dateOptionText: { fontSize: 15, fontWeight: "900" },
  dateOptionMeta: { fontSize: 11, fontWeight: "800" },
});
