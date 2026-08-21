export const H1_CLOUD_STATE_VERSION = 6;
export const H1_PUBLIC_SCHEMA = 6;
export const H1_PUBLIC_LATEST_KEY = "robot-sltp:public:h1-signals:latest";
export const H1_CLOUD_STATE_KEY = "robot-sltp:cloud:h1-scanner:state:v6";
export const H1_CLOUD_LOCK_KEY = "robot-sltp:cloud:h1-scanner:lock";
export const H1_CLOUD_PROFILE = "cTrader IcMarkets";

export const H1_TARGET_BASES = ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;
export const H1_ALL_BASES = ["GBPUSD", ...H1_TARGET_BASES] as const;
export const H1_SCANNER_BASES = ["AUDUSD", "GBPUSD"] as const;
export type H1TargetBase = typeof H1_TARGET_BASES[number];
export type H1Base = typeof H1_ALL_BASES[number];
export type H1ScannerBase = typeof H1_SCANNER_BASES[number];
export type H1Direction = "T" | "G";
export type H1Signal = "BUY" | "SELL";
export type H1PatternKind = "sw2" | "sw3Pure" | "sw3Alternating" | "sw4Alternating";

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
  scannerBase: H1ScannerBase;
  scannerSymbol: string;
  baseSymbol: string;
  baseH1Signal: H1Signal;
  baseHour: number;
  baseDirection: H1Direction;
  symbolH1Signal: H1Signal;
};

export type H1CloudState = {
  version: 6;
  days: Record<string, {
    suppressedThroughHour?: number;
    symbols: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[] }>>;
  }>;
};

export type H1PublicFeed = {
  schemaVersion: 6;
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
      scannerBase: H1ScannerBase;
      scannerSymbol: string;
      baseSymbol: string;
      baseSignal: H1Signal | "";
      baseHour: number | null;
      baseDirection: H1Direction | "";
      signal: H1Signal;
    }> }>>;
  }>;
};

const TWO_CANDLE_SW = new Set(["TG", "GT"]);
const PURE_SW_3 = new Set(["TGG", "GTT"]);
const ALTERNATING_SW_3 = new Set(["TGT", "GTG"]);
const ALTERNATING_SW_4 = new Set(["TGTG", "GTGT"]);
const PATTERN_LABELS: Record<H1PatternKind, string> = {
  sw2: "SW 2 cây",
  sw3Pure: "SW 3 cây thuần",
  sw3Alternating: "SW 3 cây xen kẽ",
  sw4Alternating: "SW 4 cây xen kẽ",
};

export function signalFromDirection(direction: H1Direction): H1Signal {
  return direction === "T" ? "BUY" : "SELL";
}

export function scannerBaseForTarget(base: H1TargetBase): H1ScannerBase {
  return base === "XAUUSD" ? "AUDUSD" : "GBPUSD";
}

export function baseSymbolForTarget(base: H1TargetBase): H1Base {
  return base === "XAUUSD" ? "GBPUSD" : base;
}

export function patternFollowsBase(patternKind: H1PatternKind): boolean {
  return patternKind !== "sw3Pure";
}

export function signalFromPatternBase(baseSignal: H1Signal, patternKind: H1PatternKind): H1Signal {
  if (patternFollowsBase(patternKind)) return baseSignal;
  return baseSignal === "BUY" ? "SELL" : "BUY";
}

function rowsForHours(byHour: Map<number, H1DirectionBar>, hours: number[]): H1DirectionBar[] | null {
  const rows = hours.map((hour) => byHour.get(hour));
  return rows.every(Boolean) ? rows as H1DirectionBar[] : null;
}

export function findH1PatternMatches(bars: H1DirectionBar[], brokerHour: number): H1PatternMatch[] {
  if (brokerHour < 3 || brokerHour > 23) return [];
  const byHour = new Map<number, H1DirectionBar>();
  for (const bar of bars) byHour.set(bar.hour, bar);
  const matches: H1PatternMatch[] = [];
  const lastSlot = Math.min(brokerHour, 17);

  for (let slotHour = 3; slotHour <= lastSlot; slotHour += 1) {
    if (slotHour >= 5) {
      const rows4 = rowsForHours(byHour, [slotHour - 1, slotHour - 2, slotHour - 3, slotHour - 4]);
      if (rows4) {
        const pattern = rows4.map((row) => row.direction) as H1Direction[];
        if (ALTERNATING_SW_4.has(pattern.join(""))) {
          matches.push({ slotHour, pattern, bars: rows4, patternKind: "sw4Alternating" });
          continue;
        }
      }
    }

    if (slotHour >= 4) {
      const rows3 = rowsForHours(byHour, [slotHour - 1, slotHour - 2, slotHour - 3]);
      if (rows3) {
        const pattern = rows3.map((row) => row.direction) as H1Direction[];
        const text = pattern.join("");
        if (PURE_SW_3.has(text)) {
          matches.push({ slotHour, pattern, bars: rows3, patternKind: "sw3Pure" });
          continue;
        }
        if (ALTERNATING_SW_3.has(text)) {
          matches.push({ slotHour, pattern, bars: rows3, patternKind: "sw3Alternating" });
          continue;
        }
      }
    }

    if (slotHour !== 3) continue;
    const rows2 = rowsForHours(byHour, [2, 1]);
    if (!rows2) continue;
    const pattern = rows2.map((row) => row.direction) as H1Direction[];
    if (TWO_CANDLE_SW.has(pattern.join(""))) {
      matches.push({ slotHour, pattern, bars: rows2, patternKind: "sw2" });
    }
  }
  return matches;
}

export function buildStoredAlert(args: {
  base: H1TargetBase;
  brokerSymbol: string;
  scannerBase: H1ScannerBase;
  scannerSymbol: string;
  match: H1PatternMatch;
  baseSymbol: H1Base;
  baseBar: H1DirectionBar;
}): H1StoredAlert {
  const baseSignal = signalFromDirection(args.baseBar.direction);
  const finalSignal = signalFromPatternBase(baseSignal, args.match.patternKind);
  return {
    slotHour: args.match.slotHour,
    pattern: args.match.pattern.join(" "),
    patternKind: args.match.patternKind,
    bars: args.match.bars.map((bar) => bar.brokerTime),
    symbol: args.brokerSymbol,
    profile: H1_CLOUD_PROFILE,
    scannerBase: args.scannerBase,
    scannerSymbol: args.scannerSymbol,
    baseSymbol: args.baseSymbol,
    baseH1Signal: baseSignal,
    baseHour: args.baseBar.hour,
    baseDirection: args.baseBar.direction,
    symbolH1Signal: finalSignal,
  };
}

export function buildTelegramMessage(base: H1TargetBase, brokerDate: string, alert: H1StoredAlert): string {
  const behavior = patternFollowsBase(alert.patternKind) ? `giữ nguyên ${alert.baseSymbol} H1` : `đảo ${alert.baseSymbol} H1`;
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
    `• Scanner pattern: ${alert.scannerBase} (${alert.scannerSymbol})`,
    `• Nến xét (mới→cũ): ${barHours}`,
    `• Pattern scanner: ${alert.pattern}`,
    `• Nhóm scanner: ${PATTERN_LABELS[alert.patternKind]}`,
    `• Base H1: ${alert.baseSymbol} H${String(alert.baseHour).padStart(2, "0")}=${alert.baseDirection} → ${alert.baseH1Signal}`,
    `• Logic: ${behavior}`,
    `• Signal ${base} H1: ${alert.symbolH1Signal}`,
  ].join("\n");
}

export function emptyCloudState(): H1CloudState {
  return { version: H1_CLOUD_STATE_VERSION, days: {} };
}

function isTargetBase(value: string): value is H1TargetBase {
  return (H1_TARGET_BASES as readonly string[]).includes(value);
}

function isScannerBase(value: unknown): value is H1ScannerBase {
  return value === "AUDUSD" || value === "GBPUSD";
}

function isPatternKind(value: unknown): value is H1PatternKind {
  return value === "sw2" || value === "sw3Pure" || value === "sw3Alternating" || value === "sw4Alternating";
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
    if (day.suppressedThroughHour !== undefined && !Number.isInteger(day.suppressedThroughHour)) {
      throw new Error("Invalid H1 cloud suppression state");
    }
    for (const [base, symbolState] of Object.entries(day.symbols)) {
      if (!isTargetBase(base) || !symbolState || !Array.isArray(symbolState.alerts)) {
        throw new Error("Invalid H1 cloud symbol state");
      }
      for (const alert of symbolState.alerts) {
        if (
          !Number.isInteger(alert.slotHour) || !isPatternKind(alert.patternKind) || !isSignal(alert.symbolH1Signal)
          || !isScannerBase(alert.scannerBase) || !isSignal(alert.baseH1Signal) || !isDirection(alert.baseDirection)
          || !Number.isInteger(alert.baseHour)
        ) {
          throw new Error("Invalid H1 cloud alert state");
        }
      }
    }
  }
  return state as H1CloudState;
}

function parseV6PublicFeed(raw: unknown): H1CloudState | null {
  if (!raw) return null;
  const value = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (!value || typeof value !== "object") return null;
  const feed = value as Partial<H1PublicFeed>;
  if (feed.schemaVersion !== H1_PUBLIC_SCHEMA || !feed.days || typeof feed.days !== "object") return null;
  const state = emptyCloudState();
  for (const [dateKey, day] of Object.entries(feed.days)) {
    if (!day || typeof day !== "object" || !day.symbols || typeof day.symbols !== "object") continue;
    const symbolStates: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[] }>> = {};
    for (const [base, source] of Object.entries(day.symbols)) {
      if (!isTargetBase(base) || !source || !Array.isArray(source.alerts)) continue;
      const alerts: H1StoredAlert[] = [];
      for (const row of source.alerts) {
        if (
          !row || !Number.isInteger(row.slotHour) || !isPatternKind(row.patternKind) || !isSignal(row.signal)
          || !isScannerBase(row.scannerBase) || !isSignal(row.baseSignal) || !isDirection(row.baseDirection)
          || !Number.isInteger(row.baseHour)
        ) continue;
        alerts.push({
          slotHour: row.slotHour,
          pattern: String(row.pattern || ""),
          patternKind: row.patternKind,
          bars: Array.isArray(row.bars) ? row.bars.map(String) : [],
          symbol: String(row.symbol || base),
          profile: H1_CLOUD_PROFILE,
          scannerBase: row.scannerBase,
          scannerSymbol: String(row.scannerSymbol || row.scannerBase),
          baseSymbol: String(row.baseSymbol || baseSymbolForTarget(base)),
          baseH1Signal: row.baseSignal,
          baseHour: row.baseHour,
          baseDirection: row.baseDirection,
          symbolH1Signal: row.signal,
        });
      }
      alerts.sort((left, right) => left.slotHour - right.slotHour);
      symbolStates[base] = { alerts };
    }
    state.days[dateKey] = { symbols: symbolStates };
  }
  return state;
}

export function seedCloudStateFromPublic(raw: unknown, brokerDate: string, suppressThroughHour: number): H1CloudState {
  const v6 = parseV6PublicFeed(raw);
  if (v6) return v6;

  const state = emptyCloudState();
  state.days[brokerDate] = {
    suppressedThroughHour: Math.max(2, Math.min(17, Math.trunc(suppressThroughHour))),
    symbols: Object.fromEntries(H1_TARGET_BASES.map((base) => [base, { alerts: [] }])) as H1CloudState["days"][string]["symbols"],
  };
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
            scannerBase: alert.scannerBase,
            scannerSymbol: alert.scannerSymbol,
            baseSymbol: alert.baseSymbol,
            baseSignal: alert.baseH1Signal,
            baseHour: alert.baseHour,
            baseDirection: alert.baseDirection,
            signal: alert.symbolH1Signal,
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
  return { day, symbol };
}
