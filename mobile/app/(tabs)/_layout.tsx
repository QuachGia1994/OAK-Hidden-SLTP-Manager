import { Tabs } from "expo-router";
import { Text } from "react-native";
import { useOakTheme } from "@/lib/theme";

const ITEMS = [
  { name: "index", title: "Home", icon: "⌂" },
  { name: "calendar", title: "H1", icon: "▦" },
  { name: "signals", title: "Signals", icon: "≋" },
  { name: "reports", title: "Reports", icon: "⌁" },
  { name: "bridge", title: "Bridge", icon: "⌬" },
  { name: "more", title: "More", icon: "▣" },
] as const;

export default function TabLayout() {
  const theme = useOakTheme();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarHideOnKeyboard: false,
        tabBarActiveTintColor: theme.cyan,
        tabBarInactiveTintColor: theme.muted,
        tabBarLabelPosition: "below-icon",
        tabBarStyle: {
          position: "absolute",
          left: 14,
          right: 14,
          bottom: 14,
          height: 76,
          paddingTop: 8,
          paddingBottom: 10,
          paddingHorizontal: 4,
          borderTopWidth: 0,
          borderRadius: 28,
          backgroundColor: "#07101D",
          borderWidth: 1,
          borderColor: "rgba(88,166,255,0.22)",
          shadowColor: theme.cyan,
          shadowOpacity: 0.18,
          shadowRadius: 18,
          shadowOffset: { width: 0, height: 0 },
          elevation: 16,
        },
        tabBarItemStyle: {
          minHeight: 58,
          borderRadius: 22,
          paddingVertical: 2,
        },
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: "800",
          marginTop: 0,
        },
      }}
    >
      {ITEMS.map((item) => (
        <Tabs.Screen
          key={item.name}
          name={item.name}
          options={{
            title: item.title,
            tabBarIcon: ({ color, focused }) => (
              <Text
                style={{
                  color,
                  width: 26,
                  height: 24,
                  textAlign: "center",
                  fontSize: focused ? 20 : 18,
                  lineHeight: 23,
                  fontWeight: "900",
                }}
              >
                {item.icon}
              </Text>
            ),
          }}
        />
      ))}
    </Tabs>
  );
}
