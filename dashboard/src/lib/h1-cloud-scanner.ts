export const H1_CLOUD_STATE_VERSION = 2;
export const H1_PUBLIC_SCHEMA = 2;
export const H1_PUBLIC_LATEST_KEY = "robot-sltp:public:h1-signals:latest";
export const H1_CLOUD_STATE_KEY = "robot-sltp:cloud:h1-scanner:state:v2";
export const H1_CLOUD_LOCK_KEY = "robot-sltp:cloud:h1-scanner:lock";
export const H1_CLOUD_PROFILE = "cTrader IcMarkets";

export const H1_TARGET_BASES = ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;
export const H1_ALL_BASES = ["GBPUSD", ...H1_TARGET_BASES] as const;
export type H1TargetBase = typeof H1_TARGET_BASES[number];
export type H1Base = typeof H1_ALL_BASES[number];
export type H1Direction = "T" | "G";
export type H1Signal = "BUY" | "SELL";
export type H1PatternKind = "sw2" | "sw3Pure" | "sw3Alternating" | "sw6CombinedPure";

export type H1DirectionBar = {
  hour: number;
  brokerDate: string;
  brokerTime: string;
  direction: H1Direction;
};

export type H1PatternMatch = {
  slotHour: number;
  pattern: H1Direction[];
  patternKind: H1PatternKind;
  bars: H1DirectionBar[];
};

export type H1StoredAlert = {
  slotHour: number;
  pattern: string;
  patternKind: H1PatternKind;
  bars: string[];
  symbol: string;
  profile: string;
  symbolH1Signal: H1Signal;
  gbpusdH1Signal: H1Signal;
  gbpusdBaseHour: number;
  gbpusdBaseDirection: H1Direction;
};

export type H1CloudState = {
  version: 2;
  days: Record<string, {
    symbols: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[] }>>;
  }>;
};

export type H1PublicFeed = {
  schemaVersion: 2;
  profile: string;
  publishedAt: string;
  hours: number[];
  symbols: H1TargetBase[];
  days: Record<string, {
    symbols: Partial<Record<H1TargetBase, { alerts: Array<{
      slotHour: number;
      pattern: string;
      patternKind: H1PatternKind;
      bars: string[];
      symbol: string;
      profile: string;
      signal: H1Signal;
      gbpusdSignal: H1Signal | "";
      gbpusdBaseHour: number | null;
      gbpusdBaseDirection: H1Direction | "";
    }> }>>;
  }>;
};

const PURE_SW_3 = new Set(["TGG", "GTT"]);
const TWO_CANDLE_SW = new Set(["TG", "GT"]);
const ALTERNATING_SW_3 = new Set(["TGT", "GTG"]);
const ALTERNATING_SW_4 = new Set(["TGTG", "GTGT"]);
const REVERSE_KINDS = new Set<H1PatternKind>(["sw2", "sw3Alternating", "sw6CombinedPure"]);
const PATTERN_LABELS: Record<H1PatternKind, string> = {
  sw2: "SW 2 cây",
  sw3Pure: "SW 3 cây thuần",
  sw3Alternating: "SW 3 cây xen kẽ",
  sw6CombinedPure: "SW ghép 2×3 cây thuần",
};

export function signalFromDirection(direction: H1Direction): H1Signal {
  return direction === "T" ? "BUY" : "SELL";
}

export function signalFromGbpPattern(gbpSignal: H1Signal, patternKind: H1PatternKind): H1Signal {
  if (patternKind === "sw3Pure") return gbpSignal;
  if (REVERSE_KINDS.has(patternKind)) return gbpSignal === "BUY" ? "SELL" : "BUY";
  throw new Error(`Unknown H1 pattern kind: ${patternKind}`);
}

function rowsForHours(byHour: Map<number, H1DirectionBar>, hours: number[]): H1DirectionBar[] | null {
  const rows = hours.map((hour) => byHour.get(hour));
  return rows.every(Boolean) ? rows as H1DirectionBar[] : null;
}

export function findH1PatternMatches(
  bars: H1DirectionBar[],
  brokerHour: number,
  firstScanHour: 3 | 4,
): H1PatternMatch[] {
  if (brokerHour < firstScanHour || brokerHour > 23) return [];
  const byHour = new Map<number, H1DirectionBar>();
  for (const bar of bars) byHour.set(bar.hour, bar);
  const matches: H1PatternMatch[] = [];
  const lastSlot = Math.min(brokerHour, 17);

  for (let slotHour = firstScanHour; slotHour <= lastSlot; slotHour += 1) {
    if (slotHour === firstScanHour) {
      const rows = rowsForHours(byHour, [slotHour - 1, slotHour - 2]);
      if (!rows) continue;
      const pattern = rows.map((row) => row.direction) as H1Direction[];
      if (TWO_CANDLE_SW.has(pattern.join(""))) {
        matches.push({ slotHour, pattern, bars: rows, patternKind: "sw2" });
      }
      continue;
    }

    if (slotHour >= firstScanHour + 4) {
      const rows = rowsForHours(byHour, Array.from({ length: 6 }, (_, index) => slotHour - 1 - index));
      if (rows) {
        const pattern = rows.map((row) => row.direction) as H1Direction[];
        const text = pattern.join("");
        if (PURE_SW_3.has(text.slice(0, 3)) && PURE_SW_3.has(text.slice(3, 6))) {
          matches.push({ slotHour, pattern, bars: rows, patternKind: "sw6CombinedPure" });
          continue;
        }
      }
    }

    const rows = rowsForHours(byHour, [slotHour - 1, slotHour - 2, slotHour - 3]);
    if (!rows) continue;
    const pattern = rows.map((row) => row.direction) as H1Direction[];
    const text = pattern.join("");
    if (PURE_SW_3.has(text)) {
      matches.push({ slotHour, pattern, bars: rows, patternKind: "sw3Pure" });
      continue;
    }
    if (!ALTERNATING_SW_3.has(text)) continue;
    const older = byHour.get(slotHour - 4);
    if (older && ALTERNATING_SW_4.has(`${text}${older.direction}`)) continue;
    matches.push({ slotHour, pattern, bars: rows, patternKind: "sw3Alternating" });
  }
  return matches;
}

export function buildStoredAlert(args: {
  base: H1TargetBase;
  brokerSymbol: string;
  match: H1PatternMatch;
  gbpBase: H1DirectionBar;
}): H1StoredAlert {
  const gbpSignal = signalFromDirection(args.gbpBase.direction);
  const symbolSignal = signalFromGbpPattern(gbpSignal, args.match.patternKind);
  return {
    slotHour: args.match.slotHour,
    pattern: args.match.pattern.join(" "),
    patternKind: args.match.patternKind,
    bars: args.match.bars.map((bar) => bar.brokerTime),
    symbol: args.brokerSymbol,
    profile: H1_CLOUD_PROFILE,
    symbolH1Signal: symbolSignal,
    gbpusdH1Signal: gbpSignal,
    gbpusdBaseHour: args.gbpBase.hour,
    gbpusdBaseDirection: args.gbpBase.direction,
  };
}

export function buildTelegramMessage(base: H1TargetBase, brokerDate: string, alert: H1StoredAlert): string {
  const behavior = alert.patternKind === "sw3Pure" ? "giữ nguyên GBPUSD H1" : "đảo GBPUSD H1";
  const barHours = alert.bars.map((value) => {
    const match = value.match(/T(\d{2}):/);
    return match ? `H${match[1]}` : value;
  }).join("→");
  return [
    `🔔 ${base} H1 PATTERN`,
    `• Symbol: ${alert.symbol}`,
    `• Profile: ${H1_CLOUD_PROFILE}`,
    `• Ngày broker: ${brokerDate}`,
    `• Mốc scan: H${String(alert.slotHour).padStart(2, "0")}`,
    `• Nến xét (mới→cũ): ${barHours}`,
    `• Pattern: ${alert.pattern}`,
    `• Nhóm pattern: ${PATTERN_LABELS[alert.patternKind]}`,
    `• Signal GBPUSD H1: ${alert.gbpusdH1Signal} | Base H${String(alert.gbpusdBaseHour).padStart(2, "0")}=${alert.gbpusdBaseDirection}`,
    `• Logic Signal ${base}: ${behavior}`,
    `• Signal ${base} H1: ${alert.symbolH1Signal}`,
  ].join("\n");
}

export function emptyCloudState(): H1CloudState {
  return { version: H1_CLOUD_STATE_VERSION, days: {} };
}

function isTargetBase(value: string): value is H1TargetBase {
  return (H1_TARGET_BASES as readonly string[]).includes(value);
}

function isPatternKind(value: unknown): value is H1PatternKind {
  return value === "sw2" || value === "sw3Pure" || value === "sw3Alternating" || value === "sw6CombinedPure";
}

function isSignal(value: unknown): value is H1Signal {
  return value === "BUY" || value === "SELL";
}

function isDirection(value: unknown): value is H1Direction {
  return value === "T" || value === "G";
}

export function parseCloudState(raw: unknown): H1CloudState {
  const value = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (!value || typeof value !== "object") throw new Error("Invalid H1 cloud state");
  const state = value as Partial<H1CloudState>;
  if (state.version !== H1_CLOUD_STATE_VERSION || !state.days || typeof state.days !== "object") {
    throw new Error("Invalid H1 cloud state schema");
  }
  for (const day of Object.values(state.days)) {
    if (!day || typeof day !== "object" || !day.symbols || typeof day.symbols !== "object") {
      throw new Error("Invalid H1 cloud day state");
    }
    for (const [base, symbolState] of Object.entries(day.symbols)) {
      if (!isTargetBase(base) || !symbolState || !Array.isArray(symbolState.alerts)) {
        throw new Error("Invalid H1 cloud symbol state");
      }
      for (const alert of symbolState.alerts) {
        if (!Number.isInteger(alert.slotHour) || !isPatternKind(alert.patternKind) || !isSignal(alert.symbolH1Signal)) {
          throw new Error("Invalid H1 cloud alert state");
        }
      }
    }
  }
  return state as H1CloudState;
}

export function seedCloudStateFromPublic(raw: unknown): H1CloudState {
  if (!raw) throw new Error("H1 public feed is unavailable for cloud state seeding");
  const value = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (!value || typeof value !== "object") throw new Error("Invalid H1 public feed seed");
  const feed = value as Partial<H1PublicFeed>;
  if (feed.schemaVersion !== H1_PUBLIC_SCHEMA || !feed.days || typeof feed.days !== "object") {
    throw new Error("Invalid H1 public feed seed schema");
  }
  const state = emptyCloudState();
  for (const [dateKey, day] of Object.entries(feed.days)) {
    if (!day || typeof day !== "object" || !day.symbols || typeof day.symbols !== "object") continue;
    const symbolStates: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[] }>> = {};
    for (const [base, source] of Object.entries(day.symbols)) {
      if (!isTargetBase(base) || !source || !Array.isArray(source.alerts)) continue;
      const alerts: H1StoredAlert[] = [];
      for (const row of source.alerts) {
        const gbpBaseHour = row?.gbpusdBaseHour;
        const gbpBaseDirection = row?.gbpusdBaseDirection;
        if (
          !row || !Number.isInteger(row.slotHour) || !isPatternKind(row.patternKind)
          || !isSignal(row.signal) || !isSignal(row.gbpusdSignal)
          || typeof gbpBaseHour !== "number" || !Number.isInteger(gbpBaseHour)
          || !isDirection(gbpBaseDirection)
        ) continue;
        alerts.push({
          slotHour: row.slotHour,
          pattern: String(row.pattern || ""),
          patternKind: row.patternKind,
          bars: Array.isArray(row.bars) ? row.bars.map(String) : [],
          symbol: String(row.symbol || base),
          profile: H1_CLOUD_PROFILE,
          symbolH1Signal: row.signal,
          gbpusdH1Signal: row.gbpusdSignal,
          gbpusdBaseHour: gbpBaseHour,
          gbpusdBaseDirection: gbpBaseDirection,
        });
      }
      alerts.sort((left, right) => left.slotHour - right.slotHour);
      symbolStates[base] = { alerts };
    }
    state.days[dateKey] = { symbols: symbolStates };
  }
  return state;
}

export function trimCloudState(state: H1CloudState, keepDays = 14): H1CloudState {
  const keys = Object.keys(state.days).sort();
  if (keys.length <= keepDays) return state;
  const keep = new Set(keys.slice(-keepDays));
  state.days = Object.fromEntries(Object.entries(state.days).filter(([key]) => keep.has(key)));
  return state;
}

export function buildPublicFeed(state: H1CloudState, publishedAt = new Date().toISOString()): H1PublicFeed {
  const days: H1PublicFeed["days"] = {};
  for (const dateKey of Object.keys(state.days).sort()) {
    const sourceDay = state.days[dateKey];
    const symbols: H1PublicFeed["days"][string]["symbols"] = {};
    for (const base of H1_TARGET_BASES) {
      const source = sourceDay.symbols[base];
      if (!source) continue;
      symbols[base] = {
        alerts: [...source.alerts]
          .sort((left, right) => left.slotHour - right.slotHour)
          .map((alert) => ({
            slotHour: alert.slotHour,
            pattern: alert.pattern,
            patternKind: alert.patternKind,
            bars: alert.bars,
            symbol: alert.symbol,
            profile: H1_CLOUD_PROFILE,
            signal: alert.symbolH1Signal,
            gbpusdSignal: alert.gbpusdH1Signal,
            gbpusdBaseHour: alert.gbpusdBaseHour,
            gbpusdBaseDirection: alert.gbpusdBaseDirection,
          })),
      };
    }
    days[dateKey] = { symbols };
  }
  return {
    schemaVersion: H1_PUBLIC_SCHEMA,
    profile: H1_CLOUD_PROFILE,
    publishedAt,
    hours: Array.from({ length: 15 }, (_, index) => index + 3),
    symbols: [...H1_TARGET_BASES],
    days,
  };
}

export function ensureSymbolDay(state: H1CloudState, brokerDate: string, base: H1TargetBase) {
  const day = state.days[brokerDate] ||= { symbols: {} };
  const symbol = day.symbols[base] ||= { alerts: [] };
  return symbol;
}
