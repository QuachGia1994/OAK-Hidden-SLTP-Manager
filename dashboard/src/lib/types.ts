export interface Signal {
  date: string;
  hour: number;
  ts: number;
  signal: "BUY" | "SELL" | "WAIT";
  entry_time: string | null;
  pair_dirs: Record<string, string>;
  entry_prices: Record<string, number>;
  hour_note: string | null;
  missed: boolean;
}

export interface BotState {
  date: string;
  day_signals: Record<string, { signal: string; m30_dir: string }>;
  sent_today: [string, number][];
  d_direction: string | null;
  d_direction_date: string | null;
  d_matched_hour: number | null;
}

export interface NewsItem {
  time: string;
  currency: string;
  title: string;
  impact: "high" | "medium" | "low";
}

export interface RuleReminder {
  day: string;
  notes: string[];
}
