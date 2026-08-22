import "react-native-reanimated";

import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useColorScheme, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { UnlockScreen } from "@/components/UnlockScreen";
import { useOakTheme } from "@/lib/theme";
import { AuthProvider, useAuth } from "@/state/auth";
import { DataProvider } from "@/state/data";

function AppNavigator() {
  const scheme = useColorScheme();
  const theme = useOakTheme();
  const { ready, apiKey } = useAuth();

  if (!ready) return <View style={{ flex: 1, backgroundColor: theme.canvas }} />;
  if (!apiKey) return <UnlockScreen />;

  return (
    <DataProvider>
      <ThemeProvider value={scheme === "light" ? DefaultTheme : DarkTheme}>
        <StatusBar style={scheme === "light" ? "dark" : "light"} />
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.canvas } }}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="signal/[symbol]/[hour]" options={{ presentation: "formSheet", headerShown: false }} />
        </Stack>
      </ThemeProvider>
    </DataProvider>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <AuthProvider>
        <AppNavigator />
      </AuthProvider>
    </GestureHandlerRootView>
  );
}
