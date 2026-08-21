export type NavKey = 'overview' | 'profiles' | 'sltp' | 'telegram' | 'netting';
export type PositionSide = 'BUY' | 'SELL';
export type Profile = { name: string; server: string; equity: number; balance: number; drawdown: number; openTrades: number; status: 'LIVE' | 'DEMO' | 'OFFLINE'; pathConfigured?: boolean; telegramConfigured?: boolean; autoBeR?: number; partialR?: string; visibleSltp?: boolean; slPoints?: number; tpPoints?: number; copyRole?: string };
export type Position = { ticket: number; symbol: string; side: PositionSide; lots: number; profit: number; openPrice?: number; currentPrice?: number; sl?: number; tp?: number };
export type Activity = { time: string; text: string; tone: 'green' | 'cyan' | 'amber' | 'red' };
export type PendingTask = { id: number; kind: 'telegram' | 'netting'; status: string; symbol?: string; side?: string; lot?: number; date?: string; time?: string; scope?: string; canDelete: boolean };
export type RuntimeHealth = { profile: string; telegram: { configured: boolean; running: boolean; pid: number }; worker: { running: boolean; pid: number }; remoteReady: boolean; started?: string[]; issues?: string[] };
