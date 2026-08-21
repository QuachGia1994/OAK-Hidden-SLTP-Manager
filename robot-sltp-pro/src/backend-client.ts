import { invoke } from '@tauri-apps/api/core';
import type { PendingTask, Position, Profile, RuntimeHealth } from './types';

export type ProfileDraft = {
  name: string;
  path: string;
  server: string;
  sl: string;
  tp: string;
  autoBeR: string;
  partialR: string;
  partialPct: string;
  teleChat: string;
};

export type SnapshotResponse = {
  profile: Profile;
  account: {
    balance: number;
    equity: number;
    profit: number;
    server?: string;
  };
  positions: Position[];
  observedAt?: string;
};

export type DesktopRuntimeStatus = {
  app: string;
  version: string;
  engine: string;
};

async function pythonCommand<T>(command: string, payload: Record<string, unknown> = {}): Promise<T> {
  const raw = await invoke<string>('backend_call', {
    command,
    payload: JSON.stringify(payload),
  });
  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new Error(`Backend command ${command} returned invalid JSON`);
  }
}

export const desktopBackend = {
  runtimeStatus: () => invoke<DesktopRuntimeStatus>('runtime_status'),
  profiles: () => pythonCommand<{ profiles: Profile[]; profileDefaults: ProfileDraft }>('profiles'),
  addProfile: (profile: ProfileDraft) => pythonCommand<{ profile: Profile; saved: boolean }>('profile_add', profile),
  snapshot: (profile: string) => pythonCommand<SnapshotResponse>('snapshot', { profile }),
  runtimeHealth: (profile: string) => pythonCommand<RuntimeHealth>('runtime_health', { profile }),
  startRuntime: (profile: string) => pythonCommand<RuntimeHealth>('runtime_ensure', { profile }),
  pendingTasks: (profile: string) => pythonCommand<{ profile: string; tasks: PendingTask[] }>('pending_tasks', { profile }),
  deletePendingTask: (profile: string, task: PendingTask) => pythonCommand<{ deleted: boolean }>('pending_delete', {
    profile,
    kind: task.kind,
    id: task.id,
  }),
  sendTelegram: (profile: string, text: string) => pythonCommand<{ queued: boolean; updateId: number }>('telegram_send', { profile, text }),
  scheduleNetting: (profile: string, time: string, mode: 'all' | 'symbol', symbol: string) => pythonCommand<{ task: { id: number; date: string; time: string } }>('schedule_netting', {
    profile,
    time,
    mode,
    symbol: mode === 'symbol' ? symbol : '',
  }),
  saveSltp: (profile: string, enabled: boolean, beR: string, tpR: string) => pythonCommand<{ profile: Profile; saved: boolean }>('sltp_save', {
    profile,
    enabled,
    beR,
    tpR,
  }),
};
