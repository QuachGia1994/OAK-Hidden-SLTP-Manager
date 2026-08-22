import { useRouter } from "expo-router";
import { TabList, TabSlot, TabTrigger, Tabs } from "expo-router/ui";
import {
  GlassTabBar,
  GlassTabButton,
  TabBarMinimizeProvider,
  renderFadingTabScreen,
  type GlassTabItem,
} from "expo-glass-tabs";
import { useOakTheme } from "@/lib/theme";

const ITEMS: (GlassTabItem & { href: "/" | "/accounts" | "/alerts" | "/more" })[] = [
  { name: "index", href: "/", label: "Engine", icon: "waveform.path.ecg" },
  { name: "accounts", href: "/accounts", label: "Accounts", icon: "person.2.fill" },
  { name: "alerts", href: "/alerts", label: "Alerts", icon: "bell.fill" },
  { name: "more", href: "/more", label: "More", icon: "ellipsis.circle.fill" },
];

export default function TabLayout() {
  const router = useRouter();
  const theme = useOakTheme();

  return (
    <TabBarMinimizeProvider>
      <Tabs>
        <TabSlot style={{ height: "100%" }} renderFn={renderFadingTabScreen} />
        <TabList asChild>
          <GlassTabBar
            onIndexSelected={(index) => router.navigate(ITEMS[index].href as never)}
            theme={{
              activeTint: theme.text,
              inactiveTint: theme.muted,
              highlight: `${theme.accent}28`,
              glassTint: theme.glass,
              solidFallback: theme.surface,
            }}
            haptics
          >
            {ITEMS.map(({ href, ...item }, index) => (
              <TabTrigger key={item.name} name={item.name} href={href as never} asChild>
                <GlassTabButton item={item} index={index} />
              </TabTrigger>
            ))}
          </GlassTabBar>
        </TabList>
      </Tabs>
    </TabBarMinimizeProvider>
  );
}
