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

const ITEMS: (GlassTabItem & { href: "/" | "/calendar" | "/bridge" | "/signals" | "/reports" | "/more" })[] = [
  { name: "index", href: "/", label: "Home", icon: "house.fill" },
  { name: "calendar", href: "/calendar", label: "H1", icon: "calendar" },
  { name: "signals", href: "/signals", label: "Signals", icon: "antenna.radiowaves.left.and.right" },
  { name: "reports", href: "/reports", label: "Reports", icon: "chart.xyaxis.line" },
  { name: "bridge", href: "/bridge", label: "Bridge", icon: "point.3.connected.trianglepath.dotted" },
  { name: "more", href: "/more", label: "More", icon: "square.grid.2x2.fill" },
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
              highlight: `${theme.cyan}30`,
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
