import { useEffect, useMemo, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Activity as ActivityIcon, Bot, CalendarClock, Check, CircleDot, Clock3, Eye, EyeOff, Home, Languages, Palette, Paperclip, Plus, Radio, Save, Send, Settings2, Target, Trash2, TrendingUp, UserRound, Wifi, X } from 'lucide-react';
import type { Activity, NavKey, Pattern5Payload, PatternCandle, PatternCell, PendingTask, Position, Profile, RuntimeHealth } from './types';

const fallbackProfiles: Profile[] = [];

const initialActivity: Activity[] = [];

type AppLanguage = 'vi' | 'en';
type AppTheme = 'dark' | 'deep-sea' | 'light' | 'amber';

const navItems: Array<{ key: NavKey; icon: typeof Home }> = [
  { key: 'overview', icon: Home }, { key: 'profiles', icon: UserRound }, { key: 'sltp', icon: Target },
  { key: 'telegram', icon: Send }, { key: 'netting', icon: CalendarClock }, { key: 'pattern5', icon: ActivityIcon }
];

const UI_COPY = {
  vi: {
    nav: { overview: 'Tổng quan', profiles: 'Theo dõi Profile', sltp: 'SLTP Tự động', telegram: 'Telegram Order', netting: 'Hẹn giờ Netting', pattern5: 'Pattern5 Engine' },
    center: 'Giám sát trung tâm', settings: 'Cài đặt', language: 'Ngôn ngữ', appearance: 'Giao diện', vietnamese: 'Tiếng Việt', english: 'English',
    themeNames: { dark: 'Dark', 'deep-sea': 'Deep-Sea', light: 'Light', amber: 'Amber Contrast' },
    themeHints: { dark: 'Đen xanh tiêu chuẩn', 'deep-sea': 'Xanh biển sâu, cyan lạnh', light: 'Sáng sạch, tương phản dịu', amber: 'Đen + vàng hổ phách tương phản cao' },
    connected: 'Connected', offline: 'Offline', version: 'Phiên bản', hideEquity: 'Ẩn Equity', showEquity: 'Hiện Equity',
    remoteReady: 'Điều khiển từ xa sẵn sàng', remoteOffline: 'Điều khiển từ xa chưa sẵn sàng', telegramReceiver: 'Telegram Receiver', worker: 'Worker', pid: 'PID',
    heading: 'Profile · SL/TP tự động · Telegram Order · Netting · Pattern5.', loadingBackend: 'Đang kết nối backend…', loadingBackendHint: 'Đọc profiles.json và kiểm tra MT5 runtime.',
    sltpTitle: 'SLTP TỰ ĐỘNG', engine: 'Động cơ SL/TP', beTrigger: 'R:R kích hoạt BE', takeProfit: 'Chốt lời theo R:R', watching: 'Đang theo dõi và tự động xử lý SL/TP theo R:R...', appliedSltp: 'CẤU HÌNH ĐANG ÁP DỤNG', slPoints: 'SL points', tpPoints: 'TP points', tpRatio: 'TP theo R:R',
    profileTitle: 'THEO DÕI PROFILE', stable: 'Ổn định', profileDetail: 'Xem chi tiết profile', openTradesMetric: 'Lệnh đang mở', openPositions: 'VỊ THẾ ĐANG MỞ', noPositions: 'Không có vị thế đang mở.', totalPL: 'Tổng P/L', activity: 'NHẬT KÝ HOẠT ĐỘNG',
    telegramTitle: 'ĐẶT LỆNH QUA TELEGRAM', telegramPlaceholder: 'Mỗi dòng một lệnh Telegram', sendReal: 'Gửi lệnh thật',
    nettingTitle: 'HẸN GIỜ ĐÓNG LỆNH NETTING', autoClose: 'Đóng tự động', time: 'Thời gian', mode: 'Chế độ', allPositions: 'Tất cả vị thế', perSymbol: 'Đóng từng symbol', chooseSymbol: 'Chọn symbol…', scheduleClose: 'Đặt lịch đóng lệnh',
    pendingTelegram: 'LỆNH CHỜ XỬ LÝ', pendingNetting: 'LỊCH ĐÓNG ĐANG CHỜ', loading: 'Đang tải…', noPending: 'Không có lệnh chờ.', deletePending: 'Xoá lệnh chờ', executing: 'Task đang thực thi',
    profileMonitoring: 'Theo dõi Profile', profileMonitoringHint: 'Chọn profile MT5 để xem equity, balance, drawdown và vị thế đang mở theo thời gian thực.', addProfile: 'Thêm Profile MT5', openTradesLabel: 'lệnh mở',
    addProfileHint: 'Chỉ lưu cấu hình profile. Telegram token không nhập tại đây.', profileName: 'Tên Profile', terminalPath: 'Đường dẫn terminal64.exe', saveProfileHint: 'Sau khi lưu, chọn profile để app tự đọc MT5 snapshot. Token Telegram tiếp tục lấy từ vault hiện hữu.', cancel: 'Hủy', saveProfile: 'Lưu Profile', close: 'Đóng',
    saveSltp: 'Lưu cấu hình SLTP vào backend', enabled: 'Bật tự động', footerTagline: 'an toàn hơn, thông minh hơn', weekLabel: 'Tuần', weekdayNames: ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6'],
    patternHint: 'ngày giao dịch trước · lookback 4 nến H4 mới → cũ · base = cây #4: Sw đảo chiều base, Bt giữ chiều base.', reverseHint: 'Reverse cuối: H3 T2/T5 + T6 theo chu kỳ tháng · H7 T3/T6 · H9 T5/T6 · H12 trừ T4 · H14 tất cả.', evidenceClickHint: 'Mẹo: Click trực tiếp vào dòng Pattern (dòng 4) trong từng ô để xem chart 4 nến và dữ liệu OHLC làm bằng chứng.', evidenceTitle: 'Bằng chứng 4 nến H4', evidenceHint: 'Chart trái → phải = cũ → mới · OHLC lấy trực tiếp từ 4 nến lookback.', refresh: 'Làm mới MT5', refreshing: 'Đang tính…', patternEmpty: 'Chưa có dữ liệu Pattern5. Nhấn Làm mới MT5.', patternLoading: 'Đang đọc H4/D1 broker-time, phân nhóm Sw/Bt và tính Reverse Signal…'
  },
  en: {
    nav: { overview: 'Overview', profiles: 'Profile Monitor', sltp: 'Auto SLTP', telegram: 'Telegram Order', netting: 'Netting Scheduler', pattern5: 'Pattern5 Engine' },
    center: 'Central monitoring', settings: 'Settings', language: 'Language', appearance: 'Appearance', vietnamese: 'Vietnamese', english: 'English',
    themeNames: { dark: 'Dark', 'deep-sea': 'Deep-Sea', light: 'Light', amber: 'Amber Contrast' },
    themeHints: { dark: 'Standard dark teal', 'deep-sea': 'Deep navy with cool cyan', light: 'Clean light, softer contrast', amber: 'Black + high-contrast amber' },
    connected: 'Connected', offline: 'Offline', version: 'Version', hideEquity: 'Hide Equity', showEquity: 'Show Equity',
    remoteReady: 'Remote control ready', remoteOffline: 'Remote control not ready', telegramReceiver: 'Telegram Receiver', worker: 'Worker', pid: 'PID',
    heading: 'Profile · Automatic SL/TP · Telegram Order · Netting · Pattern5.', loadingBackend: 'Connecting to backend…', loadingBackendHint: 'Reading profiles.json and checking MT5 runtime.',
    sltpTitle: 'AUTOMATIC SLTP', engine: 'SL/TP engine', beTrigger: 'BE activation R:R', takeProfit: 'Take profit R:R', watching: 'Monitoring and automatically handling SL/TP by R:R...', appliedSltp: 'APPLIED CONFIGURATION', slPoints: 'SL points', tpPoints: 'TP points', tpRatio: 'TP R:R',
    profileTitle: 'PROFILE MONITOR', stable: 'Stable', profileDetail: 'View profile details', openTradesMetric: 'Open Trades', openPositions: 'OPEN POSITIONS', noPositions: 'No open positions.', totalPL: 'Total P/L', activity: 'ACTIVITY LOG',
    telegramTitle: 'TELEGRAM ORDER', telegramPlaceholder: 'One Telegram command per line', sendReal: 'Send live order',
    nettingTitle: 'NETTING CLOSE SCHEDULER', autoClose: 'Automatic close', time: 'Time', mode: 'Mode', allPositions: 'All positions', perSymbol: 'Close by symbol', chooseSymbol: 'Choose symbol…', scheduleClose: 'Schedule close',
    pendingTelegram: 'PENDING ORDERS', pendingNetting: 'PENDING CLOSE SCHEDULE', loading: 'Loading…', noPending: 'No pending tasks.', deletePending: 'Delete pending task', executing: 'Task is executing',
    profileMonitoring: 'Profile monitoring', profileMonitoringHint: 'Select an MT5 profile to inspect equity, balance, drawdown and open positions in real time.', addProfile: 'Add MT5 Profile', openTradesLabel: 'open trades',
    addProfileHint: 'Save profile configuration only. Telegram token is not entered here.', profileName: 'Profile name', terminalPath: 'terminal64.exe path', saveProfileHint: 'After saving, select the profile and the app will read its MT5 snapshot. Telegram token remains in the existing vault.', cancel: 'Cancel', saveProfile: 'Save Profile', close: 'Close',
    saveSltp: 'Save SLTP configuration', enabled: 'Enable automation', footerTagline: 'safer, smarter', weekLabel: 'Week', weekdayNames: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
    patternHint: 'previous trading day · look back 4 H4 candles newest → oldest · base = candle #4: Sw reverses base, Bt follows base.', reverseHint: 'Final Reverse: H3 Mon/Thu + monthly Fri cycle · H7 Tue/Fri · H9 Thu/Fri · H12 except Wed · H14 all days.', evidenceClickHint: 'Tip: Click the Pattern line inside any populated cell to view the 4-candle chart and OHLC evidence.', evidenceTitle: '4-candle H4 evidence', evidenceHint: 'Chart left → right = oldest → newest · OHLC comes directly from the four lookback candles.', refresh: 'Refresh MT5', refreshing: 'Calculating…', patternEmpty: 'No Pattern5 data yet. Press Refresh MT5.', patternLoading: 'Reading broker-time H4/D1, grouping Sw/Bt and calculating Reverse Signal…'
  }
} as const;

type UiCopy = (typeof UI_COPY)[AppLanguage];
const THEME_OPTIONS: AppTheme[] = ['dark', 'deep-sea', 'light', 'amber'];
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

function localizedPatternDayName(dateValue: string, fallback: string, ui: UiCopy) {
  const parsed = new Date(`${dateValue}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return fallback;
  const weekday = parsed.getUTCDay();
  return weekday >= 1 && weekday <= 5 ? ui.weekdayNames[weekday - 1] : fallback;
}

function App() {
  const [active, setActive] = useState<NavKey>('overview');
  const [profiles, setProfiles] = useState<Profile[]>(fallbackProfiles);
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [backendError, setBackendError] = useState('');
  const [autoSltp, setAutoSltp] = useState(true);
  const [beR, setBeR] = useState('1.0');
  const [tpR, setTpR] = useState('2.4');
  const [telegramCommand, setTelegramCommand] = useState('/buy EURUSD 0.10');
  const [nettingTime, setNettingTime] = useState('22:00');
  const [nettingMode, setNettingMode] = useState<'all' | 'symbol'>('all');
  const [nettingSymbol, setNettingSymbol] = useState('');
  const [nettingEnabled, setNettingEnabled] = useState(true);
  const [activity, setActivity] = useState<Activity[]>(initialActivity);
  const [runtimeHealth, setRuntimeHealth] = useState<RuntimeHealth | null>(null);
  const [pattern5, setPattern5] = useState<Pattern5Payload | null>(null);
  const [pattern5Loading, setPattern5Loading] = useState(false);
  const [showAddProfile, setShowAddProfile] = useState(false);
  const [newProfile, setNewProfile] = useState({ name: '', path: '', server: '', sl: '500', tp: '10000', autoBeR: '2', partialR: '2', partialPct: '50', teleChat: '' });
  const [showEquity, setShowEquity] = useState(() => localStorage.getItem('robot-sltp-show-equity') !== '0');
  const [mt5Connected, setMt5Connected] = useState(false);
  const [pendingTasks, setPendingTasks] = useState<PendingTask[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsPopoverRef = useRef<HTMLDivElement>(null);
  const [language, setLanguage] = useState<AppLanguage>(() => localStorage.getItem('robot-sltp-language') === 'en' ? 'en' : 'vi');
  const [theme, setTheme] = useState<AppTheme>(() => {
    const saved = localStorage.getItem('robot-sltp-theme') as AppTheme | null;
    return saved && THEME_OPTIONS.includes(saved) ? saved : 'dark';
  });
  const ui = UI_COPY[language];

  useEffect(() => {
    if (!settingsOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const focusFrame = window.requestAnimationFrame(() => settingsPopoverRef.current?.querySelector<HTMLElement>('button')?.focus());
    const closeSettings = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSettingsOpen(false);
    };
    window.addEventListener('keydown', closeSettings);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      window.removeEventListener('keydown', closeSettings);
      previous?.focus();
    };
  }, [settingsOpen]);

  const uniqueProfiles = useMemo(() => {
    const map = new Map<string, Profile>();
    for (const profile of profiles) {
      const key = profile.name.trim().toLowerCase();
      if (key && !map.has(key)) map.set(key, profile);
    }
    return Array.from(map.values());
  }, [profiles]);

  const totalProfit = useMemo(() => positions.reduce((sum, item) => sum + item.profit, 0), [positions]);

  useEffect(() => {
    void refreshProfiles();
  }, []);

  useEffect(() => {
    if (!selectedProfile) return;
    void refreshSnapshot(selectedProfile.name);
    const timer = window.setInterval(() => void refreshSnapshot(selectedProfile.name), 5000);
    return () => window.clearInterval(timer);
  }, [selectedProfile?.name]);

  useEffect(() => {
    if (!selectedProfile) return;
    void ensureRuntime(selectedProfile.name);
    const timer = window.setInterval(() => void refreshRuntimeHealth(selectedProfile.name), 5000);
    return () => window.clearInterval(timer);
  }, [selectedProfile?.name]);

  useEffect(() => {
    if (!selectedProfile) return;
    void refreshPendingTasks(selectedProfile.name, true);
    const timer = window.setInterval(() => void refreshPendingTasks(selectedProfile.name), 4000);
    return () => window.clearInterval(timer);
  }, [selectedProfile?.name]);

  useEffect(() => {
    if (!selectedProfile || !mt5Connected) return;
    void publishPattern5(selectedProfile.name);
    const timer = window.setInterval(() => void publishPattern5(selectedProfile.name), 60000);
    return () => window.clearInterval(timer);
  }, [selectedProfile?.name, mt5Connected]);

  useEffect(() => {
    if (!selectedProfile || !mt5Connected) return;
    void refreshPattern5(selectedProfile.name, false);
    return undefined;
  }, [selectedProfile?.name, mt5Connected]);

  useEffect(() => {
    localStorage.setItem('robot-sltp-show-equity', showEquity ? '1' : '0');
  }, [showEquity]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('robot-sltp-theme', theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = language;
    localStorage.setItem('robot-sltp-language', language);
  }, [language]);

  const refreshRuntimeHealth = async (profileName: string) => {
    try {
      const raw = await invoke<string>('backend_call', { command: 'runtime_health', payload: JSON.stringify({ profile: profileName }) });
      setRuntimeHealth(JSON.parse(raw) as RuntimeHealth);
    } catch (error) {
      setRuntimeHealth(null);
      setBackendError(`Runtime health failed: ${String(error)}`);
    }
  };

  const ensureRuntime = async (profileName: string) => {
    setRuntimeHealth(null);
    try {
      const raw = await invoke<string>('backend_call', { command: 'runtime_ensure', payload: JSON.stringify({ profile: profileName }) });
      const health = JSON.parse(raw) as RuntimeHealth;
      setRuntimeHealth(health);
      if (health.started?.length) addActivity(`Runtime started · ${profileName} · ${health.started.join(' + ')}`, 'green');
      if (health.issues?.length) setBackendError(health.issues.join(' · '));
    } catch (error) {
      setRuntimeHealth(null);
      setBackendError(`Runtime start failed: ${String(error)}`);
    }
  };

  const publishPattern5 = async (profileName: string) => {
    try {
      await invoke('backend_call', { command: 'pattern5_publish', payload: JSON.stringify({ profile: profileName }) });
      setBackendError('');
    } catch (error) {
      setBackendError(`Pattern5 public publish failed: ${String(error)}`);
    }
  };

  const addProfile = async () => {
    try {
      const raw = await invoke<string>('backend_call', { command: 'profile_add', payload: JSON.stringify(newProfile) });
      const data = JSON.parse(raw) as { profile: Profile };
      const profile = { ...data.profile, equity: 0, balance: 0, drawdown: 0, openTrades: 0, status: 'OFFLINE' as const };
      setProfiles((items) => [...items, profile]);
      setMt5Connected(false);
      setPositions([]);
      setPattern5(null);
      setSelectedProfile(profile);
      setShowAddProfile(false);
      setNewProfile({ name: '', path: '', server: '', sl: '500', tp: '10000', autoBeR: '2', partialR: '2', partialPct: '50', teleChat: '' });
      addActivity(`Profile added · ${profile.name}`, 'cyan');
      setBackendError('');
    } catch (error) {
      setBackendError(String(error));
    }
  };

  const refreshProfiles = async () => {
    try {
      const raw = await invoke<string>('backend_call', { command: 'profiles', payload: '{}' });
      const data = JSON.parse(raw) as { profiles: Profile[] };
      const uniqueProfiles = Array.from(new Map(data.profiles.map((profile) => [profile.name.trim().toLowerCase(), profile])).values());
      const normalized = uniqueProfiles.map((profile) => ({ ...profile, equity: 0, balance: 0, drawdown: 0, openTrades: 0, status: 'OFFLINE' as const }));
      setProfiles(normalized);
      if (!selectedProfile && normalized.length) setSelectedProfile(normalized[0]);
    } catch (error) {
      setBackendError(String(error));
    }
  };

  const refreshSnapshot = async (profileName: string) => {
    try {
      const raw = await invoke<string>('backend_call', { command: 'snapshot', payload: JSON.stringify({ profile: profileName }) });
      const data = JSON.parse(raw) as Partial<{ profile: Profile; account: { balance: number; equity: number; profit: number; server?: string }; positions: Position[]; error: string }>;
      if (data.error) throw new Error(data.error);
      if (!data.profile || typeof data.profile !== 'object') throw new Error(`Snapshot missing profile for ${profileName}`);
      if (!data.account || typeof data.account !== 'object') throw new Error(`Snapshot missing account for ${profileName}`);
      if (!Array.isArray(data.positions)) throw new Error(`Snapshot missing positions for ${profileName}`);
      const server = data.account.server || data.profile.server || '';
      const next: Profile = {
        ...data.profile,
        server,
        balance: data.account.balance,
        equity: data.account.equity,
        openTrades: data.positions.length,
        drawdown: data.account.balance > 0 ? Math.max(0, ((data.account.balance - data.account.equity) / data.account.balance) * 100) : 0,
        status: server.toLowerCase().includes('demo') ? 'DEMO' : 'LIVE'
      };
      setMt5Connected(true);
      setProfiles((items) => items.map((item) => item.name === profileName ? next : item));
      setSelectedProfile((current) => current && current.name === profileName ? next : current);
      setAutoSltp(Boolean(data.profile.visibleSltp));
      setBeR(String(data.profile.autoBeR ?? 0));
      if ((data.profile.slPoints ?? 0) > 0 && (data.profile.tpPoints ?? 0) > 0) {
        setTpR(String(Number((data.profile.tpPoints! / data.profile.slPoints!).toFixed(3))));
      }
      setPositions(data.positions);
      setBackendError('');
    } catch (error) {
      setBackendError(String(error));
      setMt5Connected(false);
      setPositions([]);
      setProfiles((items) => items.map((item) => item.name === profileName ? { ...item, status: 'OFFLINE' } : item));
    }
  };

  const addActivity = (text: string, tone: Activity['tone'] = 'green') => {
    setActivity((items) => [{ time: new Date().toLocaleTimeString('vi-VN', { hour12: false }), text, tone }, ...items].slice(0, 7));
  };

  const refreshPendingTasks = async (profileName: string, showLoading = false) => {
    if (showLoading) setPendingLoading(true);
    try {
      const raw = await invoke<string>('backend_call', { command: 'pending_tasks', payload: JSON.stringify({ profile: profileName }) });
      const data = JSON.parse(raw) as { tasks: PendingTask[] };
      setPendingTasks(Array.isArray(data.tasks) ? data.tasks : []);
    } catch (error) {
      setBackendError(`Pending tasks failed: ${String(error)}`);
    } finally {
      if (showLoading) setPendingLoading(false);
    }
  };

  const deletePendingTask = async (task: PendingTask) => {
    if (!selectedProfile || !task.canDelete) return;
    try {
      await invoke('backend_call', { command: 'pending_delete', payload: JSON.stringify({ profile: selectedProfile.name, kind: task.kind, id: task.id }) });
      addActivity(`Đã xoá lệnh chờ #${task.id} · ${selectedProfile.name}`, 'amber');
      await refreshPendingTasks(selectedProfile.name);
      setBackendError('');
    } catch (error) {
      setBackendError(String(error));
    }
  };

  const sendTelegram = async (overrideCommand?: string) => {
    const command = (overrideCommand ?? telegramCommand).trim();
    if (!command || !selectedProfile) return;
    try {
      await invoke('backend_call', { command: 'telegram_send', payload: JSON.stringify({ profile: selectedProfile.name, text: command }) });
      addActivity(`Telegram Order queued · ${selectedProfile.name}: ${command}`, 'cyan');
      window.setTimeout(() => void refreshPendingTasks(selectedProfile.name), 750);
      setBackendError('');
    } catch (error) {
      setBackendError(String(error));
      addActivity(`Telegram Order failed · ${selectedProfile.name}`, 'red');
    }
  };

  const scheduleNetting = async () => {
    if (!selectedProfile) return;
    try {
      const raw = await invoke<string>('backend_call', { command: 'schedule_netting', payload: JSON.stringify({ profile: selectedProfile.name, time: nettingTime, mode: nettingMode, symbol: nettingMode === 'symbol' ? nettingSymbol : '' }) });
      const data = JSON.parse(raw) as { task: { id: number; date: string; time: string } };
      addActivity(`Scheduled Netting · ${selectedProfile.name} · ${data.task.date} ${data.task.time}`, 'amber');
      await refreshPendingTasks(selectedProfile.name);
      setBackendError('');
    } catch (error) {
      setBackendError(String(error));
      addActivity(`Scheduled Netting failed · ${selectedProfile.name}`, 'red');
    }
  };

  const refreshPattern5 = async (profileName: string, force = false) => {
    setPattern5Loading(true);
    try {
      const raw = await invoke<string>('backend_call', { command: 'pattern5', payload: JSON.stringify({ profile: profileName, force }) });
      setPattern5(JSON.parse(raw) as Pattern5Payload);
      setBackendError('');
    } catch (error) {
      setBackendError(String(error));
    } finally {
      setPattern5Loading(false);
    }
  };

  const saveSltp = async () => {
    if (!selectedProfile) return;
    try {
      const raw = await invoke<string>('backend_call', { command: 'sltp_save', payload: JSON.stringify({ profile: selectedProfile.name, enabled: autoSltp, beR: beR, tpR: tpR }) });
      const data = JSON.parse(raw) as { profile: Profile };
      setProfiles((items) => items.map((item) => item.name === selectedProfile.name ? { ...item, ...data.profile } : item));
      setSelectedProfile((current) => current?.name === selectedProfile.name ? { ...current, ...data.profile } : current);
      addActivity(`SLTP saved · ${selectedProfile.name} · SL ${data.profile.slPoints ?? 0} · TP ${data.profile.tpPoints ?? 0} · BE ${beR}R`, 'cyan');
      setBackendError('');
    } catch (error) {
      setBackendError(String(error));
      addActivity(`SLTP save failed · ${selectedProfile.name}`, 'red');
    }
  };

  const shellTitle = active === 'overview' ? ui.center : ui.nav[active];
  const cycleTheme = () => {
    const currentIndex = THEME_OPTIONS.indexOf(theme);
    setTheme(THEME_OPTIONS[(currentIndex + 1) % THEME_OPTIONS.length]);
  };

  if (!selectedProfile) {
    return <div className="app-shell"><main className="main-content"><div className="feature-layout single"><section className="panel"><div className="feature-title">{ui.loadingBackend}</div><p>{ui.loadingBackendHint}</p>{backendError && <p className="error-banner">{backendError}</p>}</section></div></main></div>;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block"><div className="brand-mark"><Bot size={23} strokeWidth={1.8} /></div><div><div className="brand-title">OAK Gatekeeper</div><div className="brand-subtitle">ROBOT SLTP PRO · DESKTOP COMMAND</div></div></div>
        <div className="top-status"><span className="live-pill"><span className="dot cyan" /> OAK COMMAND</span><span className={`connection-pill ${mt5Connected ? 'connected' : 'disconnected'}`}><Wifi size={16} /> MT5 <b>{mt5Connected ? ui.connected : ui.offline}</b></span><div className="settings-wrap"><button className={`settings-button ${settingsOpen ? 'active' : ''}`} onClick={() => setSettingsOpen((open) => !open)} aria-label={ui.settings} aria-expanded={settingsOpen}><Settings2 size={18} /></button>{settingsOpen && <div ref={settingsPopoverRef} className="settings-popover" role="dialog" aria-label={ui.settings}><div className="settings-head"><div><b>{ui.settings}</b><small>ROBOT SLTP Pro</small></div><button onClick={() => setSettingsOpen(false)} aria-label={ui.close}><X size={16} /></button></div><div className="settings-section"><div className="settings-section-title"><Languages size={16} /> {ui.language}</div><div className="language-switch"><button className={language === 'vi' ? 'active' : ''} onClick={() => setLanguage('vi')}>{ui.vietnamese}</button><button className={language === 'en' ? 'active' : ''} onClick={() => setLanguage('en')}>{ui.english}</button></div></div><div className="settings-section"><div className="settings-section-title"><Palette size={16} /> {ui.appearance}</div><div className="theme-grid">{THEME_OPTIONS.map((item) => <button key={item} className={`theme-option ${theme === item ? 'active' : ''}`} onClick={() => setTheme(item)} aria-pressed={theme === item}><span className={`theme-preview theme-preview-${item}`}><i /><i /><i /></span><span className="theme-copy"><b>{ui.themeNames[item]}</b><small>{ui.themeHints[item]}</small></span>{theme === item && <Check size={15} className="theme-check" />}</button>)}</div></div></div>}</div><button className="quick-theme-button" onClick={cycleTheme} title={`Theme: ${ui.themeNames[theme]}`} aria-label={`Quick theme: ${ui.themeNames[theme]}`}><CircleDot size={18} /></button></div>
      </header>

      <aside className="sidebar">
        <nav className="nav-stack">{navItems.map(({ key, icon: Icon }) => <button key={key} className={`nav-item ${active === key ? 'active' : ''}`} onClick={() => setActive(key)}><Icon size={20} strokeWidth={1.8} /><span>{ui.nav[key]}</span></button>)}</nav>
        <div className="sidebar-status" aria-label={ui.profileMonitoring}><div className="status-line"><span className={`dot ${mt5Connected ? 'green' : 'red'}`} /> MT5: <b>{mt5Connected ? ui.connected : ui.offline}</b></div><div className="status-line"><span className={`dot ${runtimeHealth?.telegram.running ? 'green' : 'red'}`} /> Telegram: <b>{runtimeHealth?.telegram.running ? ui.connected : ui.offline}</b></div><div className="status-line"><span className={`dot ${runtimeHealth?.worker.running ? 'green' : 'red'}`} /> {ui.worker}: <b>{runtimeHealth?.worker.running ? ui.connected : ui.offline}</b></div><div className={`remote-status ${runtimeHealth?.remoteReady ? 'ready' : 'offline'}`}>{runtimeHealth?.remoteReady ? ui.remoteReady : ui.remoteOffline}</div><div className="status-version">{ui.version}: 4.0.0</div></div>
      </aside>

      <main className="main-content">
        <div className="page-heading"><div><div className="eyebrow">{shellTitle}</div><h1>{selectedProfile.name}</h1><p>{selectedProfile.server || 'MT5 terminal'} · {ui.heading}</p></div><div className="heading-actions"><label className="profile-quick"><UserRound size={15} /><select value={selectedProfile.name} onChange={(event) => { const next = uniqueProfiles.find((profile) => profile.name === event.target.value); if (next) { setMt5Connected(false); setPositions([]); setPattern5(null); setSelectedProfile(next); addActivity(`${ui.profileMonitoring}: ${next.name}`, 'cyan'); } }} aria-label={ui.profileMonitoring}>{uniqueProfiles.map((profile) => <option key={profile.name.toLowerCase()} value={profile.name}>{profile.name}</option>)}</select></label><button className="visibility-button" onClick={() => setShowEquity((visible) => !visible)} aria-label={showEquity ? ui.hideEquity : ui.showEquity}>{showEquity ? <EyeOff size={16} /> : <Eye size={16} />} {showEquity ? ui.hideEquity : ui.showEquity}</button></div></div>

        {backendError && <div className="error-banner" role="alert">{backendError}</div>}
        {active === 'overview' && <Overview {...{ positions, autoSltp, setAutoSltp, beR, setBeR, tpR, setTpR, selectedProfile, telegramCommand, setTelegramCommand, sendTelegram, runtimeHealth, nettingTime, setNettingTime, nettingMode, setNettingMode, nettingSymbol, setNettingSymbol, nettingEnabled, setNettingEnabled, scheduleNetting, activity, totalProfit, addActivity, showEquity, pendingTasks, pendingLoading, deletePendingTask, ui }} openProfileDetails={() => setActive('profiles')} />}
        {active === 'profiles' && <Profiles profiles={uniqueProfiles} selectedProfile={selectedProfile} runtimeHealth={runtimeHealth} setSelectedProfile={(profile) => { setMt5Connected(false); setPositions([]); setPattern5(null); setSelectedProfile(profile); addActivity(`${ui.profileMonitoring}: ${profile.name}`, 'cyan'); }} onAdd={() => setShowAddProfile(true)} ui={ui} />}
        {showAddProfile && <AddProfileModal value={newProfile} setValue={setNewProfile} onClose={() => setShowAddProfile(false)} onSave={addProfile} ui={ui} />}
        {active === 'sltp' && <SltpSettings {...{ selectedProfile, autoSltp, setAutoSltp, beR, setBeR, tpR, setTpR, addActivity, saveSltp, ui }} />}
        {active === 'telegram' && <TelegramPanel {...{ telegramCommand, setTelegramCommand, sendTelegram, runtimeHealth, addActivity, pendingTasks, pendingLoading, deletePendingTask, ui }} />}
        {active === 'netting' && <NettingPanel {...{ positions, nettingTime, setNettingTime, nettingMode, setNettingMode, nettingSymbol, setNettingSymbol, nettingEnabled, setNettingEnabled, scheduleNetting, addActivity, pendingTasks, pendingLoading, deletePendingTask, ui }} />}
        {active === 'pattern5' && <Pattern5Panel data={pattern5} loading={pattern5Loading} mt5Connected={mt5Connected} onRefresh={() => selectedProfile && refreshPattern5(selectedProfile.name, true)} ui={ui} />}

        <footer className="footer-bar"><div><Wifi size={17} /><span>MT5</span><b className={mt5Connected ? 'status-ok' : 'status-bad'}>{mt5Connected ? ui.connected : ui.offline}</b></div><div><Radio size={17} /><span>Server</span><b>{selectedProfile.server || '—'}</b></div><div><ActivityIcon size={17} /><span>{ui.worker}</span><b className={runtimeHealth?.worker.running ? 'status-ok' : 'status-bad'}>{runtimeHealth?.worker.running ? ui.connected : ui.offline}</b></div><div><Send size={17} /><span>Telegram</span><b className={runtimeHealth?.telegram.running ? 'status-ok' : 'status-bad'}>{runtimeHealth?.telegram.running ? ui.connected : ui.offline}</b></div><div className="footer-copy">OAK Gatekeeper · <strong>ROBOT SLTP PRO</strong></div></footer>
      </main>
    </div>
  );
}

function Panel({ title, icon, children, className = '' }: { title: string; icon: React.ReactNode; children: React.ReactNode; className?: string }) { return <section className={`panel ${className}`}><div className="panel-head"><div className="panel-title"><span className="panel-icon">{icon}</span>{title}</div></div>{children}</section>; }
function SettingRow({ label, suffix, children }: { label: string; suffix?: string; children: React.ReactNode }) { return <div className="setting-row"><span>{label}</span><div className="setting-control">{children}{suffix && <em>{suffix}</em>}</div></div>; }
function MetricRow({ label, value }: { label: string; value: string }) { return <div className="metric-row"><span>{label}</span><b>{value}</b></div>; }
function SltpSummary({ profile, ui }: { profile: Profile; ui: UiCopy }) { const sl = profile.slPoints ?? 0; const tp = profile.tpPoints ?? 0; const ratio = sl > 0 ? Number((tp / sl).toFixed(3)) : 0; return <div className="sltp-summary"><div className="sltp-summary-title">{ui.appliedSltp}<span className={`status-tag ${profile.visibleSltp ? '' : 'off'}`}>{profile.visibleSltp ? 'ON' : 'OFF'}</span></div><div className="sltp-summary-grid"><span><small>{ui.slPoints}</small><b>{sl} pt</b></span><span><small>{ui.tpPoints}</small><b>{tp} pt</b></span><span><small>{ui.beTrigger}</small><b>{profile.autoBeR ?? 0}R</b></span><span><small>{ui.tpRatio}</small><b>{ratio}R</b></span></div></div>; }
function ActivityList({ activity }: { activity: Activity[] }) { return <div className="activity-list">{activity.length ? activity.map((item, index) => <div className="activity-item" key={`${item.time}-${index}`}><span className={`dot ${item.tone}`} /><span className="activity-time">{item.time}</span><span>{item.text}</span></div>) : <div className="pending-empty">—</div>}</div>; }
function PendingQueue({ tasks, kind, loading, compact, onDelete, ui }: { tasks: PendingTask[]; kind: PendingTask['kind']; loading?: boolean; compact?: boolean; onDelete: (task: PendingTask) => void; ui: UiCopy }) {
  const visible = tasks.filter((task) => task.kind === kind);
  const title = kind === 'telegram' ? ui.pendingTelegram : ui.pendingNetting;
  return <div className={`pending-queue ${compact ? 'compact' : ''}`}><div className="pending-queue-head"><span>{title}</span><b>{visible.length}</b></div>{loading && !visible.length ? <div className="pending-empty">{ui.loading}</div> : !visible.length ? <div className="pending-empty">{ui.noPending}</div> : <div className="pending-list">{visible.map((task) => <div className="pending-item" key={`${task.kind}-${task.id}`}><div className="pending-copy"><b>#{task.id}</b><span>{task.kind === 'telegram' ? `${task.symbol || '—'} ${task.side || ''} ${task.lot ? task.lot.toFixed(2) : ''}`.trim() : (task.scope || ui.allPositions)}</span><small>{[task.date, task.time].filter(Boolean).join(' · ')} · {task.status}</small></div><button className="pending-delete" disabled={!task.canDelete} onClick={() => onDelete(task)} title={task.canDelete ? ui.deletePending : ui.executing} aria-label={`${ui.deletePending} ${task.id}`}><Trash2 size={15} /></button></div>)}</div>}</div>;
}

function Overview(props: any) {
  const ui: UiCopy = props.ui;
  return <div className="overview-grid">
    <Panel title={ui.sltpTitle} icon={<Target size={20} />} className="sltp-panel"><div className="panel-toggle-row"><span>{ui.engine}</span><button className={`switch ${props.autoSltp ? 'on' : ''}`} onClick={() => props.setAutoSltp(!props.autoSltp)}>{props.autoSltp ? 'ON' : 'OFF'}<span /></button></div><SltpSummary profile={props.selectedProfile} ui={ui} /><SettingRow label={ui.beTrigger}><input value={props.beR} onChange={(e) => props.setBeR(e.target.value)} /></SettingRow><SettingRow label={ui.takeProfit}><input value={props.tpR} onChange={(e) => props.setTpR(e.target.value)} /></SettingRow><div className="panel-note"><TrendingUp size={18} /> {ui.watching}</div></Panel>
    <Panel title={ui.profileTitle} icon={<UserRound size={20} />} className="profile-panel"><div className="profile-title">{props.selectedProfile.name}<span className="status-tag">{props.selectedProfile.status}</span></div><MetricRow label="Equity" value={props.showEquity ? money.format(props.selectedProfile.equity) : '••••••'} /><MetricRow label="Balance" value={props.showEquity ? money.format(props.selectedProfile.balance) : '••••••'} /><MetricRow label="Drawdown" value={`${props.selectedProfile.drawdown.toFixed(2)}%`} /><MetricRow label={ui.openTradesMetric} value={String(props.selectedProfile.openTrades)} /><div className="health-bar"><div style={{ width: `${Math.max(20, 100 - props.selectedProfile.drawdown * 20)}%` }} /></div><div className="health-caption"><span>{ui.stable}</span><button onClick={props.openProfileDetails}>{ui.profileDetail}</button></div></Panel>
    <Panel title={ui.openPositions} icon={<TrendingUp size={20} />} className="positions-panel"><div className="table-head"><span>Symbol</span><span>Side</span><span>Lots</span><span>P/L</span><span>SL</span><span>TP</span></div><div className="positions-scroll">{props.positions.length ? props.positions.map((position: Position) => <div className="table-row" key={position.ticket}><b>{position.symbol}</b><span className={position.side === 'BUY' ? 'buy' : 'sell'}>{position.side}</span><span>{position.lots.toFixed(2)}</span><span className={position.profit >= 0 ? 'profit' : 'loss'}>{position.profit >= 0 ? '+' : ''}{position.profit.toFixed(2)}</span><span className="risk-value">{position.sl && position.sl > 0 ? position.sl : '—'}</span><span className="risk-value">{position.tp && position.tp > 0 ? position.tp : '—'}</span></div>) : <div className="positions-empty">{ui.noPositions}</div>}</div><div className="table-total"><span>{ui.totalPL}</span><b className={props.totalProfit >= 0 ? 'profit' : 'loss'}>{props.totalProfit >= 0 ? '+' : ''}{props.totalProfit.toFixed(2)} USD</b></div></Panel>
    <TelegramPanel {...props} compact /><NettingPanel {...props} compact />
    <Panel title={ui.activity} icon={<ActivityIcon size={20} />} className="activity-panel"><ActivityList activity={props.activity} /></Panel>
  </div>;
}

function Profiles({ profiles, selectedProfile, runtimeHealth, setSelectedProfile, onAdd, ui }: { profiles: Profile[]; selectedProfile: Profile; runtimeHealth: RuntimeHealth | null; setSelectedProfile: (profile: Profile) => void; onAdd: () => void; ui: UiCopy }) { return <div className="feature-layout"><div className="feature-copy"><div className="feature-title">{selectedProfile.name}</div><p>{selectedProfile.server || 'MT5 terminal'} · {selectedProfile.status}</p><div className="profile-detail-card"><MetricRow label="Equity" value={money.format(selectedProfile.equity)} /><MetricRow label="Balance" value={money.format(selectedProfile.balance)} /><MetricRow label="Drawdown" value={`${selectedProfile.drawdown.toFixed(2)}%`} /><MetricRow label={ui.openTradesMetric} value={String(selectedProfile.openTrades)} /><MetricRow label={ui.telegramReceiver} value={runtimeHealth?.telegram.running ? `${ui.connected} · ${ui.pid} ${runtimeHealth.telegram.pid}` : ui.offline} /><MetricRow label={ui.worker} value={runtimeHealth?.worker.running ? `${ui.connected} · ${ui.pid} ${runtimeHealth.worker.pid}` : ui.offline} /><SltpSummary profile={selectedProfile} ui={ui} /></div><button className="primary-button add-profile-button" onClick={onAdd}><Plus size={17} /> {ui.addProfile}</button></div><div className="profile-list">{profiles.map((profile) => <button className={`profile-choice ${selectedProfile.name === profile.name ? 'selected' : ''}`} key={profile.name} onClick={() => setSelectedProfile(profile)}><span className="choice-icon"><UserRound size={20} /></span><span><b>{profile.name}</b><small>{profile.server || 'MT5 terminal'} · {profile.openTrades} {ui.openTradesLabel} · {profile.status}</small></span><span className="status-tag">{profile.status}</span></button>)}</div></div>; }

function useDialogFocusTrap(open: boolean, onClose: () => void) {
  const dialogRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    if (!open || !dialogRef.current) return;
    const dialog = dialogRef.current;
    const previous = document.activeElement as HTMLElement | null;
    const getFocusable = () => Array.from(dialog.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"));
    const focusFrame = window.requestAnimationFrame(() => getFocusable()[0]?.focus());
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab') return;
      const items = getFocusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    dialog.addEventListener('keydown', handleKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      dialog.removeEventListener('keydown', handleKeyDown);
      previous?.focus();
    };
  }, [open]);
  return dialogRef;
}

function AddProfileModal({ value, setValue, onClose, onSave, ui }: { value: { name: string; path: string; server: string; sl: string; tp: string; autoBeR: string; partialR: string; partialPct: string; teleChat: string }; setValue: React.Dispatch<React.SetStateAction<typeof value>>; onClose: () => void; onSave: () => void; ui: UiCopy }) {
  const dialogRef = useDialogFocusTrap(true, onClose);
  const field = (key: keyof typeof value, label: string, placeholder = '') => <label className="modal-field"><span>{label}</span><input value={value[key]} placeholder={placeholder} onChange={(event) => setValue((current) => ({ ...current, [key]: event.target.value }))} /></label>;
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section ref={dialogRef} className="profile-modal" role="dialog" aria-modal="true" aria-label={ui.addProfile}><div className="modal-head"><div><b>{ui.addProfile}</b><small>{ui.addProfileHint}</small></div><button onClick={onClose} aria-label={ui.close}><X size={18} /></button></div><div className="modal-grid">{field('name', ui.profileName, 'VantageNew')}{field('server', 'Broker / Server', 'Broker-Demo')}{field('path', ui.terminalPath, 'D:\\Program Files\\...\\terminal64.exe')}{field('sl', 'SL points', '500')}{field('tp', 'TP points', '10000')}{field('autoBeR', ui.beTrigger, '2')}{field('partialR', 'Partial R', '2')}{field('partialPct', 'Partial %', '50')}{field('teleChat', 'Telegram Chat ID', '-100...')}</div><div className="modal-note">{ui.saveProfileHint}</div><div className="modal-actions"><button className="secondary-button" onClick={onClose}>{ui.cancel}</button><button className="primary-button" onClick={onSave}><Save size={17} /> {ui.saveProfile}</button></div></section></div>;
}
function SltpSettings(props: any) { const ui: UiCopy = props.ui; return <div className="feature-layout single"><Panel title={ui.sltpTitle} icon={<Target size={20} />}><SltpSummary profile={props.selectedProfile} ui={ui} /><SettingRow label={ui.enabled}><button className={`switch ${props.autoSltp ? 'on' : ''}`} onClick={() => props.setAutoSltp(!props.autoSltp)}>{props.autoSltp ? 'ON' : 'OFF'}<span /></button></SettingRow><SettingRow label={ui.beTrigger}><input value={props.beR} onChange={(e) => props.setBeR(e.target.value)} /></SettingRow><SettingRow label={ui.takeProfit}><input value={props.tpR} onChange={(e) => props.setTpR(e.target.value)} /></SettingRow><button className="primary-button" onClick={props.saveSltp}><Save size={18} /> {ui.saveSltp}</button></Panel></div>; }
function TelegramPanel(props: any) { const ui: UiCopy = props.ui; const ready = Boolean(props.runtimeHealth?.remoteReady); const runQuick = (command: string) => { props.setTelegramCommand(command); void props.sendTelegram(command); }; return <Panel title={ui.telegramTitle} icon={<Send size={20} />} className={props.compact ? 'telegram-panel telegram-panel-compact' : 'telegram-panel'}><div className="telegram-status"><span className={`dot ${ready ? 'green' : 'red'}`} /><span>{ready ? ui.remoteReady : ui.remoteOffline}</span><small>{ui.telegramReceiver}: {props.runtimeHealth?.telegram.running ? `${ui.pid} ${props.runtimeHealth.telegram.pid}` : ui.offline} · {ui.worker}: {props.runtimeHealth?.worker.running ? `${ui.pid} ${props.runtimeHealth.worker.pid}` : ui.offline}</small></div><div className="telegram-input-wrap"><Paperclip size={16} /><textarea rows={props.compact ? 5 : 8} value={props.telegramCommand} onChange={(e) => props.setTelegramCommand(e.target.value)} aria-label="Telegram command" placeholder={ui.telegramPlaceholder} /></div><div className="quick-actions"><button onClick={() => runQuick('/buy EURUSD 0.10')}>BUY 0.10</button><button onClick={() => runQuick('/sell EURUSD 0.10')}>SELL 0.10</button><button onClick={() => runQuick('/closeall')}>CLOSE ALL</button></div><button className="primary-button" onClick={() => void props.sendTelegram()}><Send size={17} /> {ui.sendReal}</button>{!props.compact && <PendingQueue tasks={props.pendingTasks || []} kind="telegram" loading={props.pendingLoading} onDelete={props.deletePendingTask} ui={ui} />}</Panel>; }
function NettingPanel(props: any) {
  const ui: UiCopy = props.ui;
  const symbols = Array.from(new Set((props.positions || []).map((position: Position) => position.symbol))) as string[];
  return <Panel title={ui.nettingTitle} icon={<CalendarClock size={20} />} className={props.compact ? 'netting-panel netting-panel-compact' : 'netting-panel'}><div className="netting-row"><span>{ui.autoClose}</span><button className={`switch ${props.nettingEnabled ? 'on' : ''}`} onClick={() => props.setNettingEnabled(!props.nettingEnabled)}>{props.nettingEnabled ? 'ON' : 'OFF'}<span /></button></div><SettingRow label={ui.time}><span className="time-input-wrap"><input type="time" value={props.nettingTime} onChange={(e) => props.setNettingTime(e.target.value)} /><Clock3 size={18} aria-hidden="true" /></span></SettingRow><SettingRow label={ui.mode}><select value={props.nettingMode} onChange={(e) => props.setNettingMode(e.target.value)}><option value="all">{ui.allPositions}</option><option value="symbol">{ui.perSymbol}</option></select></SettingRow>{props.nettingMode === 'symbol' && <SettingRow label="Symbol"><select value={props.nettingSymbol} onChange={(e) => props.setNettingSymbol(e.target.value)}><option value="">{ui.chooseSymbol}</option>{symbols.map((symbol) => <option key={symbol} value={symbol}>{symbol}</option>)}</select></SettingRow>}<button className="primary-button" disabled={props.nettingMode === 'symbol' && !props.nettingSymbol} onClick={props.scheduleNetting}><CalendarClock size={17} /> {ui.scheduleClose}</button>{!props.compact && <PendingQueue tasks={props.pendingTasks || []} kind="netting" loading={props.pendingLoading} onDelete={props.deletePendingTask} ui={ui} />}</Panel>;
}

type FilledPatternCell = Exclude<PatternCell, ''>;
type PatternEvidenceSelection = { title: string; detail: string; cell: FilledPatternCell };

function candleDecimals(value: number) { return Math.abs(value) >= 100 ? 3 : 5; }
function CandleEvidenceChart({ candles }: { candles: PatternCandle[] }) {
  if (!candles.length) return null;
  const high = Math.max(...candles.map((item) => item.high));
  const low = Math.min(...candles.map((item) => item.low));
  const span = high - low || 1;
  const y = (price: number) => 16 + ((high - price) / span) * 128;
  return <svg className="pattern5-candle-chart" viewBox="0 0 360 180" role="img" aria-label="4 H4 candles oldest to newest">{candles.map((candle, index) => { const x = 48 + index * 88; const openY = y(candle.open); const closeY = y(candle.close); const bodyY = Math.min(openY, closeY); const bodyHeight = Math.max(3, Math.abs(openY - closeY)); const side = candle.close >= candle.open ? 'up' : 'down'; return <g key={`${candle.time}-${index}`} className={`pattern5-candle ${side}`}><line x1={x} x2={x} y1={y(candle.high)} y2={y(candle.low)} /><rect x={x - 13} y={bodyY} width="26" height={bodyHeight} rx="2" /><text x={x} y="168" textAnchor="middle">#{index + 1}</text></g>; })}</svg>;
}

function PatternEvidenceModal({ selection, onClose, ui }: { selection: PatternEvidenceSelection; onClose: () => void; ui: UiCopy }) {
  const dialogRef = useDialogFocusTrap(true, onClose);
  return <div className="modal-backdrop pattern5-evidence-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section ref={dialogRef} className="pattern5-evidence-modal" role="dialog" aria-modal="true" aria-label={`${ui.evidenceTitle} · ${selection.title}`}><div className="modal-head"><div><b>{ui.evidenceTitle} · {selection.title}</b><small>{ui.evidenceHint}</small></div><button onClick={onClose} aria-label={ui.close}><X size={18} /></button></div><div className="pattern5-evidence-summary"><span>Base <b>{selection.cell.baseSignal}</b></span><span className={selection.cell.reversed ? 'reverse-on' : ''}>{selection.cell.reversed ? 'REVERSE' : 'NORMAL'} → <b>{selection.cell.signal}</b></span><span>{selection.cell.group} · {selection.cell.pattern}</span></div><CandleEvidenceChart candles={selection.cell.evidence} /><div className="pattern5-ohlc-grid"><div className="pattern5-ohlc-head"><span>Candle</span><span>Open</span><span>High</span><span>Low</span><span>Close</span></div>{selection.cell.evidence.map((candle, index) => { const digits = candleDecimals(candle.close); return <div className="pattern5-ohlc-row" key={`${candle.time}-${index}`}><b>#{index + 1}</b><span>{candle.open.toFixed(digits)}</span><span>{candle.high.toFixed(digits)}</span><span>{candle.low.toFixed(digits)}</span><span>{candle.close.toFixed(digits)}</span></div>; })}</div><div className="pattern5-evidence-detail">{selection.detail}</div></section></div>;
}

function Pattern5Panel({ data, loading, mt5Connected, onRefresh, ui }: { data: Pattern5Payload | null; loading: boolean; mt5Connected: boolean; onRefresh: () => void; ui: UiCopy }) {
  return <div className="feature-layout single pattern5-layout"><Panel title="ENGINE 5 · PATTERN MATRIX" icon={<ActivityIcon size={20} />} className="pattern5-panel"><div className="pattern5-toolbar"><div className="pattern5-command-copy"><b>H4 BROKER-TIME</b><span>GBPUSD · EURUSD · Base #4 / Sw-Bt / Reverse</span></div><span className={`pattern5-status ${mt5Connected ? 'connected' : 'offline'}`}><span className="dot" /> MT5 {mt5Connected ? ui.connected : ui.offline}</span><button className="primary-button pattern5-refresh" onClick={onRefresh} disabled={loading}><Radio size={17} /> {loading ? ui.refreshing : ui.refresh}</button></div><details className="pattern5-rules"><summary>{ui.evidenceClickHint}</summary><div className="pattern5-rule-stack"><div><b>Lookback:</b> {ui.patternHint}</div><div><b>Reverse:</b> {ui.reverseHint}</div></div></details><div className="pattern5-content">{!data && !loading && <div className="pattern5-empty">{ui.patternEmpty}</div>}{loading && <div className="pattern5-empty">{ui.patternLoading}</div>}{data?.tables.map((table) => <Pattern5TableView key={table.base} table={table} blocks={data.blocks} ui={ui} />)}</div></Panel></div>;
}

function Pattern5TableView({ table, blocks, ui }: { table: Pattern5Payload['tables'][number]; blocks: number[]; ui: UiCopy }) {
  const [selection, setSelection] = useState<PatternEvidenceSelection | null>(null);
  if (table.error) return <div className="pattern5-error"><b>{table.base}</b> · {table.error}</div>;
  return <div className="pattern5-card"><div className="pattern5-heading"><strong>{table.base}</strong><span>{table.symbol && table.symbol !== table.base ? `→ ${table.symbol}` : table.symbol}</span><em>{ui.weekLabel} {table.days?.[0]?.date.slice(0, 7)}</em></div><div className="pattern5-scroll"><table className="pattern5-table"><thead><tr><th>Block</th>{table.days?.map((day) => <th key={day.date}>{localizedPatternDayName(day.date, day.name, ui)}<small>{day.display}</small></th>)}</tr></thead><tbody>{blocks.map((block) => <tr key={block}><th>H{block}</th>{table.rows?.[String(block)]?.map((cell, index) => { const detail = table.detail?.[String(block)]?.[index] || ''; const day = table.days?.[index]; return <td key={`${block}-${index}`} className={typeof cell !== 'string' && cell?.reversed ? 'pattern5-reversed' : ''} title={detail}>{typeof cell === 'string' || !cell ? <span className="pattern5-muted">—</span> : <>{cell.reversed && <span className="pattern5-reverse-badge">REV</span>}<b>{cell.group}</b><small className={cell.signal === 'BUY' ? 'buy' : 'sell'}>{cell.signal}</small><span className="pattern5-base-signal">Base {cell.baseSignal}</span><button className="pattern5-evidence-trigger" onClick={() => setSelection({ title: `${table.base} · H${block} · ${day?.display || ''}`, detail, cell })}>{cell.pattern}</button></>}</td>; })}</tr>)}</tbody></table></div>{selection && <PatternEvidenceModal selection={selection} onClose={() => setSelection(null)} ui={ui} />}</div>;
}

export default App;
