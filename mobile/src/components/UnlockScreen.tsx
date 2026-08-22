import * as Haptics from "expo-haptics";
import { LinearGradient } from "expo-linear-gradient";
import { useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { radius, spacing, useOakTheme } from "@/lib/theme";
import { useAuth } from "@/state/auth";

export function UnlockScreen() {
  const theme = useOakTheme();
  const { ready, error, unlock } = useAuth();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (busy) return;
    setBusy(true);
    try {
      await unlock(value);
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <LinearGradient colors={[theme.canvas, theme.raised, theme.canvas]} style={styles.flex}>
      <SafeAreaView style={styles.flex}>
        <KeyboardAvoidingView style={styles.wrap} behavior={Platform.OS === "ios" ? "padding" : undefined}>
          <View style={styles.brandBlock}>
            <View style={[styles.mark, { borderColor: theme.accent, backgroundColor: `${theme.accent}18` }]}>
              <Text style={[styles.markText, { color: theme.accent }]}>OAK</Text>
            </View>
            <Text style={[styles.eyebrow, { color: theme.accent }]}>MOBILE COMMAND CENTER</Text>
            <Text style={[styles.title, { color: theme.text }]}>Gatekeeper</Text>
            <Text style={[styles.copy, { color: theme.muted }]}>Native shell for H1 signals, provider accounts and cloud control. Server secrets stay on Vercel.</Text>
          </View>

          <View style={[styles.panel, { borderColor: theme.border, backgroundColor: theme.surface }]}>
            <Text style={[styles.panelTitle, { color: theme.text }]}>Unlock admin session</Text>
            <Text style={[styles.panelCopy, { color: theme.muted }]}>Enter the same Dashboard API key used by the web account manager. It is stored in device SecureStore only.</Text>
            <TextInput
              value={value}
              onChangeText={setValue}
              placeholder="Dashboard API key"
              placeholderTextColor={theme.muted}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              editable={!busy}
              onSubmitEditing={submit}
              style={[styles.input, { color: theme.text, borderColor: error ? theme.danger : theme.border, backgroundColor: theme.raised }]}
            />
            {error ? <Text style={[styles.error, { color: theme.danger }]}>{error}</Text> : null}
            <Pressable
              disabled={!ready || busy || !value.trim()}
              onPress={submit}
              style={({ pressed }) => [
                styles.button,
                { backgroundColor: theme.accent, opacity: !ready || busy || !value.trim() ? 0.45 : pressed ? 0.78 : 1 },
              ]}
            >
              {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>UNLOCK OAK</Text>}
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  wrap: { flex: 1, justifyContent: "center", paddingHorizontal: spacing.xl, gap: spacing.xl },
  brandBlock: { gap: 8 },
  mark: { width: 64, height: 64, borderRadius: 20, borderWidth: 1, alignItems: "center", justifyContent: "center", marginBottom: 8 },
  markText: { fontSize: 16, fontWeight: "900", letterSpacing: 1.5 },
  eyebrow: { fontSize: 10, fontWeight: "900", letterSpacing: 2 },
  title: { fontSize: 44, lineHeight: 48, fontWeight: "900", letterSpacing: -2 },
  copy: { fontSize: 14, lineHeight: 21, maxWidth: 480 },
  panel: { padding: spacing.lg, borderRadius: radius.lg, borderWidth: StyleSheet.hairlineWidth, gap: spacing.md },
  panelTitle: { fontSize: 20, fontWeight: "900", letterSpacing: -0.5 },
  panelCopy: { fontSize: 13, lineHeight: 19 },
  input: { minHeight: 52, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: 14, fontSize: 15, fontWeight: "700" },
  error: { fontSize: 12, lineHeight: 17, fontWeight: "700" },
  button: { minHeight: 52, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  buttonText: { color: "#fff", fontSize: 12, fontWeight: "900", letterSpacing: 1.2 },
});
