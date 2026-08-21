import { useEffect, useMemo, useRef, useState } from 'react';
import { Activity as ActivityIcon, Bot, CalendarClock, Check, CircleDot, Clock3, Eye, EyeOff, Home, Languages, Palette, Paperclip, Plus, Radio, Save, Send, Settings2, Target, Trash2, TrendingUp, UserRound, Wifi, X } from 'lucide-react';
import { desktopBackend, type ProfileDraft } from './backend-client';
import type { Activity, NavKey, PendingTask, Position, Profile, RuntimeHealth } from './types';

const fallbackProfiles: Profile[] = [];

const initialActivity: Activity[] = [];
const emptyProfileDraft: ProfileDraft = { name: '', path: '', server: '', sl: '', tp: '', autoBeR: '', partialR: '', partialPct: '', teleChat: '' };

type AppLanguage = 'vi' | 'en';
type AppTheme = 'dark' | 'deep-sea' | 'light' | 'amber';

const navItems: Array<{ key: NavKey; icon: typeof Home }> = [
  { key: 'overview', icon: Home }, { key: 'profiles', icon: UserRound }, { key: 'sltp', icon: Target },
  { key: 'telegram', icon: Send }, { key: 'netting', icon: CalendarClock }
];

const UI_COPY = {
  vi: {
    nav: { overview: 'Tổng quan', profiles: 'Theo dõi Profile', sltp: 'SLTP Tự động', telegram: 'Telegram Order', netting: 'Hẹn giờ Netting' },
    center: 'Giám sát trung tâm', settings: 'Cài đặt', language: 'Ngôn ngữ', appearance: 'Giao diện', vietnamese: 'Tiếng Việt', english: 'English',
    themeNames: { dark: 'Dark', 'deep-sea': 'Deep-Sea', light: 'Light', amber: 'Amber Contrast' },
    themeHints: { dark: 'Đen xanh tiêu chuẩn', 'deep-sea': 'Xanh biển sâu, cyan lạnh', light: 'Sáng sạch, tương phản dịu', amber: 'Đen + vàng hổ phách tương phản cao' },
    connected: 'Đã kết nối', offline: 'Ngoại tuyến', version: 'Phiên bản', hideEquity: 'Ẩn Equity', showEquity: 'Hiện Equity',
    remoteReady: 'Điều khiển từ xa sẵn sàng', remoteOffline: 'Điều khiển từ xa chưa sẵn sàng', startRuntime: 'Khởi động Runtime', startingRuntime: 'Đang khởi động…', telegramReceiver: 'Telegram Receiver', worker: 'Worker', pid: 'PID',
    heading: 'Profile · SL/TP tự động · Telegram Order · Netting.', loadingBackend: 'Đang kết nối backend…', loadingBackendHint: 'Đọc profiles.json và kiểm tra MT5 runtime.',
    sltpTitle: 'SLTP TỰ ĐỘNG', engine: 'Động cơ SL/TP', beTrigger: 'R:R kích hoạt BE', takeProfit: 'Chốt lời theo R:R', watching: 'Đang theo dõi và tự động xử lý SL/TP theo R:R...', appliedSltp: 'CẤU HÌNH ĐANG ÁP DỤNG', slPoints: 'SL points', tpPoints: 'TP points', tpRatio: 'TP theo R:R',
    profileTitle: 'THEO DÕI PROFILE', stable: 'Ổn định', profileDetail: 'Xem chi tiết profile', openTradesMetric: 'Lệnh đang mở', openPositions: 'VỊ THẾ ĐANG MỞ', noPositions: 'Không có vị thế đang mở.', positionsUnavailable: 'Chưa có snapshot MT5 hợp lệ.', totalPL: 'Tổng P/L', activity: 'NHẬT KÝ HOẠT ĐỘNG',
    telegramTitle: 'ĐẶT LỆNH QUA TELEGRAM', telegramPlaceholder: 'Mỗi dòng một lệnh Telegram', sendReal: 'Gửi lệnh thật',
    nettingTitle: 'HẸN GIỜ ĐÓNG LỆNH NETTING', autoClose: 'Đóng tự động', time: 'Thời gian', mode: 'Chế độ', allPositions: 'Tất cả vị thế', perSymbol: 'Đóng từng symbol', chooseSymbol: 'Chọn symbol…', scheduleClose: 'Đặt lịch đóng lệnh',
    pendingTelegram: 'LỆNH CHỜ XỬ LÝ', pendingNetting: 'LỊCH ĐÓNG ĐANG CHỜ', loading: 'Đang tải…', noPending: 'Không có lệnh chờ.', deletePending: 'Xoá lệnh chờ', executing: 'Task đang thực thi',
    profileMonitoring: 'Theo dõi Profile', profileMonitoringHint: 'Chọn profile MT5 để xem equity, balance, drawdown và vị thế đang mở theo thời gian thực.', addProfile: 'Thêm Profile MT5', openTradesLabel: 'lệnh mở',
    addProfileHint: 'Chỉ lưu cấu hình profile. Telegram token không nhập tại đây.', profileName: 'Tên Profile', terminalPath: 'Đường dẫn terminal64.exe', saveProfileHint: 'Sau khi lưu, chọn profile để app tự đọc MT5 snapshot. Token Telegram tiếp tục lấy từ vault hiện hữu.', cancel: 'Hủy', saveProfile: 'Lưu Profile', close: 'Đóng',
    saveSltp: 'Lưu cấu hình SLTP vào backend', enabled: 'Bật tự động', footerTagline: 'an toàn hơn, thông minh hơn'
  },
  en: {
    nav: { overview: 'Overview', profiles: 'Profile Monitor', sltp: 'Auto SLTP', telegram: 'Telegram Order', netting: 'Netting Scheduler' },
    center: 'Central monitoring', settings: 'Settings', language: 'Language', appearance: 'Appearance', vietnamese: 'Vietnamese', english: 'English',
    themeNames: { dark: 'Dark', 'deep-sea': 'Deep-Sea', light: 'Light', amber: 'Amber Contrast' },
    themeHints: { dark: 'Standard dark teal', 'deep-sea': 'Deep navy with cool cyan', light: 'Clean light, softer contrast', amber: 'Black + high-contrast amber' },
    connected: 'Connected', offline: 'Offline', version: 'Version', hideEquity: 'Hide Equity', showEquity: 'Show Equity',
    remoteReady: 'Remote control ready', remoteOffline: 'Remote control not ready', startRuntime: 'Start Runtime', startingRuntime: 'Starting…', telegramReceiver: 'Telegram Receiver', worker: 'Worker', pid: 'PID',
    heading: 'Profile · Automatic SL/TP · Telegram Order · Netting.', loadingBackend: 'Connecting to backend…', loadingBackendHint: 'Reading profiles.json and checking MT5 runtime.',
    sltpTitle: 'AUTOMATIC SLTP', engine: 'SL/TP engine', beTrigger: 'BE activation R:R', takeProfit: 'Take profit R:R', watching: 'Monitoring and automatically handling SL/TP by R:R...', appliedSltp: 'APPLIED CONFIGURATION', slPoints: 'SL points', tpPoints: 'TP points', tpRatio: 'TP R:R',
    profileTitle: 'PROFILE MONITOR', stable: 'Stable', profileDetail: 'View profile details', openTradesMetric: 'Open Trades', openPositions: 'OPEN POSITIONS', noPositions: 'No open positions.', positionsUnavailable: 'No valid MT5 snapshot is available.', totalPL: 'Total P/L', activity: 'ACTIVITY LOG',
    telegramTitle: 'TELEGRAM ORDER', telegramPlaceholder: 'One Telegram command per line', sendReal: 'Send live order',
    nettingTitle: 'NETTING CLOSE SCHEDULER', autoClose: 'Automatic close', time: 'Time', mode: 'Mode', allPositions: 'All positions', perSymbol: 'Close by symbol', chooseSymbol: 'Choose symbol…', scheduleClose: 'Schedule close',
    pendingTelegram: 'PENDING ORDERS', pendingNetting: 'PENDING CLOSE SCHEDULE', loading: 'Loading…', noPending: 'No pending tasks.', deletePending: 'Delete pending task', executing: 'Task is executing',
    profileMonitoring: 'Profile monitoring', profileMonitoringHint: 'Select an MT5 profile to inspect equity, balance, drawdown and open positions in real time.', addProfile: 'Add MT5 Profile', openTradesLabel: 'open trades',
    addProfileHint: 'Save profile configuration only. Telegram token is not entered here.', profileName: 'Profile name', terminalPath: 'terminal64.exe path', saveProfileHint: 'After saving, select the profile and the app will read its MT5 snapshot. Telegram token remains in the existing vault.', cancel: 'Cancel', saveProfile: 'Save Profile', close: 'Close',
    saveSltp: 'Save SLTP configuration', enabled: 'Enable automation', footerTagline: 'safer, smarter'
  }
} as const;

type UiCopy = (typeof UI_COPY)[AppLanguage];
const THEME_OPTIONS: AppTheme[] = ['dark', 'deep-sea', 'light', 'amber'];
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

function App() {
  const [active, setActive] = useState<NavKey>('overview');
  const [profiles, setProfiles] = useState<Profile[]>(fallbackProfiles);
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [backendError, setBackendError] = useState('');
  const [autoSltp, setAutoSltp] = useState(false);
  const [beR, setBeR] = useState('');
  const [tpR, setTpR] = useState('');
  const [telegramCommand, setTelegramCommand] = useState('');
  const [nettingTime, setNettingTime] = useState('22:00');
  const [nettingMode, setNettingMode] = useState<'all' | 'symbol'>('all');
  const [nettingSymbol, setNettingSymbol] = useState('');
  const [nettingEnabled, setNettingEnabled] = useState(true);
  const [activity, setActivity] = useState<Activity[]>(initialActivity);
  const [runtimeHealth, setRuntimeHealth] = useState<RuntimeHealth | null>(null);
  const [showAddProfile, setShowAddProfile] = useState(false);
  const [profileDefaults, setProfileDefaults] = useState<ProfileDraft>(emptyProfileDraft);
  const [newProfile, setNewProfile] = useState<ProfileDraft>(emptyProfileDraft);
  const [showEquity, setShowEquity] = useState(() => localStorage.getItem('robot-sltp-show-equity') !== '0');
  const [mt5Connected, setMt5Connected] = useState(false);
  const [pendingTasks, setPendingTasks] = useState<PendingTask[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsPopoverRef = useRef<HTMLDivElement>(null);
  const activeProfileNameRef = useRef('');
  const [appVersion, setAppVersion] = useState('—');
  const [runtimeStarting, setRuntimeStarting] = useState(false);
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

  const activateProfile = (profile: Profile) => {
    activeProfileNameRef.current = profile.name;
    setRuntimeStarting(false);
    setMt5Connected(false);
    setPositions([]);
    setRuntimeHealth(null);
    setPendingTasks([]);
    setAutoSltp(Boolean(profile.visibleSltp));
    setBeR(profile.autoBeR == null ? '' : String(profile.autoBeR));
    const slPoints = Number(profile.slPoints || 0);
    const tpPoints = Number(profile.tpPoints || 0);
    setTpR(slPoints > 0 && tpPoints > 0 ? String(Number((tpPoints / slPoints).toFixed(3))) : '');
    setSelectedProfile(profile);
  };

  useEffect(() => {
    void refreshProfiles();
    void desktopBackend.runtimeStatus()
      .then((status) => setAppVersion(status.version))
      .catch((error) => setBackendError(`Runtime status failed: ${String(error)}`));
  }, []);

  useEffect(() => {
    if (!selectedProfile) return;
    void refreshSnapshot(selectedProfile.name);
    const timer = window.setInterval(() => void refreshSnapshot(selectedProfile.name), 5000);
    return () => window.clearInterval(timer);
  }, [selectedProfile?.name]);

  useEffect(() => {
    if (!selectedProfile) return;
    void refreshRuntimeHealth(selectedProfile.name);
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
      const health = await desktopBackend.runtimeHealth(profileName);
      if (activeProfileNameRef.current !== profileName) return;
      setRuntimeHealth(health);
      if (health.issues?.length) setBackendError(health.issues.join(' · '));
    } catch (error) {
      if (activeProfileNameRef.current !== profileName) return;
      setRuntimeHealth(null);
      setBackendError(`Runtime health failed: ${String(error)}`);
    }
  };

  const startRuntime = async () => {
    if (!selectedProfile || runtimeStarting) return;
    const profileName = selectedProfile.name;
    setRuntimeStarting(true);
    try {
      const health = await desktopBackend.startRuntime(profileName);
      if (activeProfileNameRef.current !== profileName) return;
      setRuntimeHealth(health);
      if (health.started?.length) addActivity(`Runtime started · ${profileName} · ${health.started.join(' + ')}`, 'green');
      setBackendError(health.issues?.length ? health.issues.join(' · ') : '');
    } catch (error) {
      if (activeProfileNameRef.current !== profileName) return;
      setRuntimeHealth(null);
      setBackendError(`Runtime start failed: ${String(error)}`);
    } finally {
      if (activeProfileNameRef.current === profileName) setRuntimeStarting(false);
    }
  };

  const addProfile = async () => {
    try {
      const data = await desktopBackend.addProfile(newProfile);
      const profile = { ...data.profile, equity: 0, balance: 0, drawdown: 0, openTrades: 0, status: 'OFFLINE' as const };
      setProfiles((items) => [...items, profile]);
      activateProfile(profile);
      setShowAddProfile(false);
      setNewProfile({ ...profileDefaults });
      addActivity(`Profile added · ${profile.name}`, 'cyan');
      setBackendError('');
    } catch (error) {
      setBackendError(String(error));
    }
  };

  const refreshProfiles = async () => {
    try {
      const data = await desktopBackend.profiles();
      const uniqueProfiles = Array.from(new Map(data.profiles.map((profile) => [profile.name.trim().toLowerCase(), profile])).values());
      const normalized = uniqueProfiles.map((profile) => ({ ...profile, equity: 0, balance: 0, drawdown: 0, openTrades: 0, status: 'OFFLINE' as const }));
      setProfileDefaults({ ...data.profileDefaults });
      setNewProfile({ ...data.profileDefaults });
      setProfiles(normalized);
      if (!activeProfileNameRef.current && normalized.length) activateProfile(normalized[0]);
    } catch (error) {
      setBackendError(String(error));
    }
  };

  const refreshSnapshot = async (profileName: string) => {
    try {
      const data = await desktopBackend.snapshot(profileName);
      if (activeProfileNameRef.current !== profileName) return;
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
      if (activeProfileNameRef.current !== profileName) return;
      setBackendError(String(error));
      setMt5Connected(false);
      setPositions([]);
      setProfiles((items) => items.map((item) => item.name === profileName ? { ...item, status: 'OFFLINE' } : item));
      setSelectedProfile((current) => current?.name === profileName ? { ...current, status: 'OFFLINE' } : current);
    }
  };

  const addActivity = (text: string, tone: Activity['tone'] = 'green') => {
    setActivity((items) => [{ time: new Date().toLocaleTimeString('vi-VN', { hour12: false }), text, tone }, ...items].slice(0, 7));
  };

  const refreshPendingTasks = async (profileName: string, showLoading = false) => {
    if (showLoading && activeProfileNameRef.current === profileName) setPendingLoading(true);
    try {
      const data = await desktopBackend.pendingTasks(profileName);
      if (activeProfileNameRef.current !== profileName) return;
      setPendingTasks(Array.isArray(data.tasks) ? data.tasks : []);
    } catch (error) {
      if (activeProfileNameRef.current === profileName) setBackendError(`Pending tasks failed: ${String(error)}`);
    } finally {
      if (showLoading && activeProfileNameRef.current === profileName) setPendingLoading(false);
    }
  };

  const deletePendingTask = async (task: PendingTask) => {
    if (!selectedProfile || !task.canDelete) return;
    const profileName = selectedProfile.name;
    try {
      await desktopBackend.deletePendingTask(profileName, task);
      if (activeProfileNameRef.current !== profileName) return;
      addActivity(`Đã xoá lệnh chờ #${task.id} · ${profileName}`, 'amber');
      await refreshPendingTasks(profileName);
      setBackendError('');
    } catch (error) {
      if (activeProfileNameRef.current === profileName) setBackendError(String(error));
    }
  };

  const sendTelegram = async (overrideCommand?: string) => {
    const command = (overrideCommand ?? telegramCommand).trim();
    if (!command || !selectedProfile) return;
    const profileName = selectedProfile.name;
    try {
      await desktopBackend.sendTelegram(profileName, command);
      if (activeProfileNameRef.current !== profileName) return;
      addActivity(`Telegram Order queued · ${profileName}: ${command}`, 'cyan');
      window.setTimeout(() => void refreshPendingTasks(profileName), 750);
      setBackendError('');
    } catch (error) {
      if (activeProfileNameRef.current !== profileName) return;
      setBackendError(String(error));
      addActivity(`Telegram Order failed · ${profileName}`, 'red');
    }
  };

  const scheduleNetting = async () => {
    if (!selectedProfile) return;
    const profileName = selectedProfile.name;
    try {
      const data = await desktopBackend.scheduleNetting(profileName, nettingTime, nettingMode, nettingSymbol);
      if (activeProfileNameRef.current !== profileName) return;
      addActivity(`Scheduled Netting · ${profileName} · ${data.task.date} ${data.task.time}`, 'amber');
      await refreshPendingTasks(profileName);
      setBackendError('');
    } catch (error) {
      if (activeProfileNameRef.current !== profileName) return;
      setBackendError(String(error));
      addActivity(`Scheduled Netting failed · ${profileName}`, 'red');
    }
  };

  const saveSltp = async () => {
    if (!selectedProfile) return;
    const profileName = selectedProfile.name;
    try {
      const data = await desktopBackend.saveSltp(profileName, autoSltp, beR, tpR);
      if (activeProfileNameRef.current !== profileName) return;
      setProfiles((items) => items.map((item) => item.name === profileName ? { ...item, ...data.profile } : item));
      setSelectedProfile((current) => current?.name === profileName ? { ...current, ...data.profile } : current);
      addActivity(`SLTP saved · ${profileName} · SL ${data.profile.slPoints ?? 0} · TP ${data.profile.tpPoints ?? 0} · BE ${beR}R`, 'cyan');
      setBackendError('');
    } catch (error) {
      if (activeProfileNameRef.current !== profileName) return;
      setBackendError(String(error));
      addActivity(`SLTP save failed · ${profileName}`, 'red');
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
        <div className="sidebar-status" aria-label={ui.profileMonitoring}><div className="status-line"><span className={`dot ${mt5Connected ? 'green' : 'red'}`} /> MT5: <b>{mt5Connected ? ui.connected : ui.offline}</b></div><div className="status-line"><span className={`dot ${runtimeHealth?.telegram.running ? 'green' : 'red'}`} /> Telegram: <b>{runtimeHealth?.telegram.running ? ui.connected : ui.offline}</b></div><div className="status-line"><span className={`dot ${runtimeHealth?.worker.running ? 'green' : 'red'}`} /> {ui.worker}: <b>{runtimeHealth?.worker.running ? ui.connected : ui.offline}</b></div><div className={`remote-status ${runtimeHealth?.remoteReady ? 'ready' : 'offline'}`}>{runtimeHealth?.remoteReady ? ui.remoteReady : ui.remoteOffline}</div><div className="status-version">{ui.version}: {appVersion}</div></div>
      </aside>

      <main className="main-content">
        <div className="page-heading"><div><div className="eyebrow">{shellTitle}</div><h1>{selectedProfile.name}</h1><p>{selectedProfile.server || 'MT5 terminal'} · {ui.heading}</p></div><div className="heading-actions"><label className="profile-quick"><UserRound size={15} /><select value={selectedProfile.name} onChange={(event) => { const next = uniqueProfiles.find((profile) => profile.name === event.target.value); if (next) { activateProfile(next); addActivity(`${ui.profileMonitoring}: ${next.name}`, 'cyan'); } }} aria-label={ui.profileMonitoring}>{uniqueProfiles.map((profile) => <option key={profile.name.toLowerCase()} value={profile.name}>{profile.name}</option>)}</select></label><button className="visibility-button" onClick={() => setShowEquity((visible) => !visible)} aria-label={showEquity ? ui.hideEquity : ui.showEquity}>{showEquity ? <EyeOff size={16} /> : <Eye size={16} />} {showEquity ? ui.hideEquity : ui.showEquity}</button></div></div>

        {backendError && <div className="error-banner" role="alert">{backendError}</div>}
        {active === 'overview' && <Overview {...{ positions, autoSltp, setAutoSltp, beR, setBeR, tpR, setTpR, selectedProfile, telegramCommand, setTelegramCommand, sendTelegram, runtimeHealth, runtimeStarting, startRuntime, nettingTime, setNettingTime, nettingMode, setNettingMode, nettingSymbol, setNettingSymbol, nettingEnabled, setNettingEnabled, scheduleNetting, activity, totalProfit, showEquity, pendingTasks, pendingLoading, deletePendingTask, ui }} openProfileDetails={() => setActive('profiles')} />}
        {active === 'profiles' && <Profiles profiles={uniqueProfiles} selectedProfile={selectedProfile} runtimeHealth={runtimeHealth} runtimeStarting={runtimeStarting} onStartRuntime={startRuntime} setSelectedProfile={(profile) => { activateProfile(profile); addActivity(`${ui.profileMonitoring}: ${profile.name}`, 'cyan'); }} onAdd={() => setShowAddProfile(true)} ui={ui} />}
        {showAddProfile && <AddProfileModal value={newProfile} setValue={setNewProfile} onClose={() => setShowAddProfile(false)} onSave={addProfile} ui={ui} />}
        {active === 'sltp' && <SltpSettings {...{ selectedProfile, autoSltp, setAutoSltp, beR, setBeR, tpR, setTpR, saveSltp, ui }} />}
        {active === 'telegram' && <TelegramPanel {...{ telegramCommand, setTelegramCommand, sendTelegram, runtimeHealth, runtimeStarting, startRuntime, pendingTasks, pendingLoading, deletePendingTask, ui }} />}
        {active === 'netting' && <NettingPanel {...{ positions, nettingTime, setNettingTime, nettingMode, setNettingMode, nettingSymbol, setNettingSymbol, nettingEnabled, setNettingEnabled, scheduleNetting, pendingTasks, pendingLoading, deletePendingTask, ui }} />}

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

type SltpSettingsProps = {
  selectedProfile: Profile;
  autoSltp: boolean;
  setAutoSltp: React.Dispatch<React.SetStateAction<boolean>>;
  beR: string;
  setBeR: React.Dispatch<React.SetStateAction<string>>;
  tpR: string;
  setTpR: React.Dispatch<React.SetStateAction<string>>;
  saveSltp: () => Promise<void>;
  ui: UiCopy;
};

type TelegramPanelProps = {
  telegramCommand: string;
  setTelegramCommand: React.Dispatch<React.SetStateAction<string>>;
  sendTelegram: (overrideCommand?: string) => Promise<void>;
  runtimeHealth: RuntimeHealth | null;
  runtimeStarting: boolean;
  startRuntime: () => Promise<void>;
  pendingTasks: PendingTask[];
  pendingLoading: boolean;
  deletePendingTask: (task: PendingTask) => Promise<void>;
  ui: UiCopy;
  compact?: boolean;
};

type NettingPanelProps = {
  positions: Position[];
  nettingTime: string;
  setNettingTime: React.Dispatch<React.SetStateAction<string>>;
  nettingMode: 'all' | 'symbol';
  setNettingMode: React.Dispatch<React.SetStateAction<'all' | 'symbol'>>;
  nettingSymbol: string;
  setNettingSymbol: React.Dispatch<React.SetStateAction<string>>;
  nettingEnabled: boolean;
  setNettingEnabled: React.Dispatch<React.SetStateAction<boolean>>;
  scheduleNetting: () => Promise<void>;
  pendingTasks: PendingTask[];
  pendingLoading: boolean;
  deletePendingTask: (task: PendingTask) => Promise<void>;
  ui: UiCopy;
  compact?: boolean;
};

type OverviewProps = Omit<SltpSettingsProps, 'saveSltp'> & TelegramPanelProps & NettingPanelProps & {
  activity: Activity[];
  totalProfit: number;
  showEquity: boolean;
  openProfileDetails: () => void;
};

function Overview(props: OverviewProps) {
  const ui: UiCopy = props.ui;
  const profileOnline = props.selectedProfile.status !== 'OFFLINE';
  const protectedMetric = (value: string) => props.showEquity ? (profileOnline ? value : '—') : '••••••';
  return <div className="overview-grid">
    <Panel title={ui.sltpTitle} icon={<Target size={20} />} className="sltp-panel"><div className="panel-toggle-row"><span>{ui.engine}</span><button className={`switch ${props.autoSltp ? 'on' : ''}`} onClick={() => props.setAutoSltp(!props.autoSltp)}>{props.autoSltp ? 'ON' : 'OFF'}<span /></button></div><SltpSummary profile={props.selectedProfile} ui={ui} /><SettingRow label={ui.beTrigger}><input value={props.beR} onChange={(e) => props.setBeR(e.target.value)} /></SettingRow><SettingRow label={ui.takeProfit}><input value={props.tpR} onChange={(e) => props.setTpR(e.target.value)} /></SettingRow><div className="panel-note"><TrendingUp size={18} /> {ui.watching}</div></Panel>
    <Panel title={ui.profileTitle} icon={<UserRound size={20} />} className="profile-panel"><div className="profile-title">{props.selectedProfile.name}<span className={`status-tag ${profileOnline ? '' : 'off'}`}>{props.selectedProfile.status}</span></div><MetricRow label="Equity" value={protectedMetric(money.format(props.selectedProfile.equity))} /><MetricRow label="Balance" value={protectedMetric(money.format(props.selectedProfile.balance))} /><MetricRow label="Drawdown" value={profileOnline ? `${props.selectedProfile.drawdown.toFixed(2)}%` : '—'} /><MetricRow label={ui.openTradesMetric} value={profileOnline ? String(props.selectedProfile.openTrades) : '—'} /><div className="health-bar"><div style={{ width: profileOnline ? `${Math.max(20, 100 - props.selectedProfile.drawdown * 20)}%` : '0%' }} /></div><div className="health-caption"><span>{profileOnline ? ui.stable : ui.offline}</span><button onClick={props.openProfileDetails}>{ui.profileDetail}</button></div></Panel>
    <Panel title={ui.openPositions} icon={<TrendingUp size={20} />} className="positions-panel"><div className="table-head"><span>Symbol</span><span>Side</span><span>Lots</span><span>P/L</span><span>SL</span><span>TP</span></div><div className="positions-scroll">{!profileOnline ? <div className="positions-empty">{ui.positionsUnavailable}</div> : props.positions.length ? props.positions.map((position: Position) => <div className="table-row" key={position.ticket}><b>{position.symbol}</b><span className={position.side === 'BUY' ? 'buy' : 'sell'}>{position.side}</span><span>{position.lots.toFixed(2)}</span><span className={position.profit >= 0 ? 'profit' : 'loss'}>{position.profit >= 0 ? '+' : ''}{position.profit.toFixed(2)}</span><span className="risk-value">{position.sl && position.sl > 0 ? position.sl : '—'}</span><span className="risk-value">{position.tp && position.tp > 0 ? position.tp : '—'}</span></div>) : <div className="positions-empty">{ui.noPositions}</div>}</div><div className="table-total"><span>{ui.totalPL}</span>{profileOnline ? <b className={props.totalProfit >= 0 ? 'profit' : 'loss'}>{props.totalProfit >= 0 ? '+' : ''}{props.totalProfit.toFixed(2)} USD</b> : <b>—</b>}</div></Panel>
    <TelegramPanel telegramCommand={props.telegramCommand} setTelegramCommand={props.setTelegramCommand} sendTelegram={props.sendTelegram} runtimeHealth={props.runtimeHealth} runtimeStarting={props.runtimeStarting} startRuntime={props.startRuntime} pendingTasks={props.pendingTasks} pendingLoading={props.pendingLoading} deletePendingTask={props.deletePendingTask} ui={ui} compact />
    <NettingPanel positions={props.positions} nettingTime={props.nettingTime} setNettingTime={props.setNettingTime} nettingMode={props.nettingMode} setNettingMode={props.setNettingMode} nettingSymbol={props.nettingSymbol} setNettingSymbol={props.setNettingSymbol} nettingEnabled={props.nettingEnabled} setNettingEnabled={props.setNettingEnabled} scheduleNetting={props.scheduleNetting} pendingTasks={props.pendingTasks} pendingLoading={props.pendingLoading} deletePendingTask={props.deletePendingTask} ui={ui} compact />
    <Panel title={ui.activity} icon={<ActivityIcon size={20} />} className="activity-panel"><ActivityList activity={props.activity} /></Panel>
  </div>;
}

function Profiles({ profiles, selectedProfile, runtimeHealth, runtimeStarting, setSelectedProfile, onStartRuntime, onAdd, ui }: { profiles: Profile[]; selectedProfile: Profile; runtimeHealth: RuntimeHealth | null; runtimeStarting: boolean; setSelectedProfile: (profile: Profile) => void; onStartRuntime: () => void; onAdd: () => void; ui: UiCopy }) {
  const profileOnline = selectedProfile.status !== 'OFFLINE';
  const runtimeSatisfied = Boolean(runtimeHealth?.worker.running && (!runtimeHealth.telegram.configured || runtimeHealth.telegram.running));
  return <div className="feature-layout">
    <div className="feature-copy">
      <div className="feature-title">{selectedProfile.name}</div>
      <p>{selectedProfile.server || 'MT5 terminal'} · {selectedProfile.status}</p>
      <div className="profile-detail-card">
        <MetricRow label="Equity" value={profileOnline ? money.format(selectedProfile.equity) : '—'} />
        <MetricRow label="Balance" value={profileOnline ? money.format(selectedProfile.balance) : '—'} />
        <MetricRow label="Drawdown" value={profileOnline ? `${selectedProfile.drawdown.toFixed(2)}%` : '—'} />
        <MetricRow label={ui.openTradesMetric} value={profileOnline ? String(selectedProfile.openTrades) : '—'} />
        <MetricRow label={ui.telegramReceiver} value={runtimeHealth?.telegram.running ? `${ui.connected} · ${ui.pid} ${runtimeHealth.telegram.pid}` : ui.offline} />
        <MetricRow label={ui.worker} value={runtimeHealth?.worker.running ? `${ui.connected} · ${ui.pid} ${runtimeHealth.worker.pid}` : ui.offline} />
        <SltpSummary profile={selectedProfile} ui={ui} />
      </div>
      <div className="profile-actions">
        <button className="primary-button" onClick={onStartRuntime} disabled={runtimeStarting || runtimeSatisfied}><Radio size={17} /> {runtimeStarting ? ui.startingRuntime : ui.startRuntime}</button>
        <button className="primary-button add-profile-button" onClick={onAdd}><Plus size={17} /> {ui.addProfile}</button>
      </div>
    </div>
    <div className="profile-list">{profiles.map((profile) => {
      const online = profile.status !== 'OFFLINE';
      return <button className={`profile-choice ${selectedProfile.name === profile.name ? 'selected' : ''}`} key={profile.name} onClick={() => setSelectedProfile(profile)}>
        <span className="choice-icon"><UserRound size={20} /></span>
        <span><b>{profile.name}</b><small>{profile.server || 'MT5 terminal'} · {online ? `${profile.openTrades} ${ui.openTradesLabel}` : ui.offline}</small></span>
        <span className={`status-tag ${online ? '' : 'off'}`}>{profile.status}</span>
      </button>;
    })}</div>
  </div>;
}

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

function AddProfileModal({ value, setValue, onClose, onSave, ui }: { value: ProfileDraft; setValue: React.Dispatch<React.SetStateAction<ProfileDraft>>; onClose: () => void; onSave: () => void; ui: UiCopy }) {
  const dialogRef = useDialogFocusTrap(true, onClose);
  const field = (key: keyof typeof value, label: string, placeholder = '') => <label className="modal-field"><span>{label}</span><input value={value[key]} placeholder={placeholder} onChange={(event) => setValue((current) => ({ ...current, [key]: event.target.value }))} /></label>;
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section ref={dialogRef} className="profile-modal" role="dialog" aria-modal="true" aria-label={ui.addProfile}><div className="modal-head"><div><b>{ui.addProfile}</b><small>{ui.addProfileHint}</small></div><button onClick={onClose} aria-label={ui.close}><X size={18} /></button></div><div className="modal-grid">{field('name', ui.profileName, 'VantageNew')}{field('server', 'Broker / Server', 'Broker-Demo')}{field('path', ui.terminalPath, 'D:\\Program Files\\...\\terminal64.exe')}{field('sl', 'SL points')}{field('tp', 'TP points')}{field('autoBeR', ui.beTrigger)}{field('partialR', 'Partial R')}{field('partialPct', 'Partial %')}{field('teleChat', 'Telegram Chat ID', '-100...')}</div><div className="modal-note">{ui.saveProfileHint}</div><div className="modal-actions"><button className="secondary-button" onClick={onClose}>{ui.cancel}</button><button className="primary-button" onClick={onSave}><Save size={17} /> {ui.saveProfile}</button></div></section></div>;
}
function SltpSettings(props: SltpSettingsProps) { const ui: UiCopy = props.ui; return <div className="feature-layout single"><Panel title={ui.sltpTitle} icon={<Target size={20} />}><SltpSummary profile={props.selectedProfile} ui={ui} /><SettingRow label={ui.enabled}><button className={`switch ${props.autoSltp ? 'on' : ''}`} onClick={() => props.setAutoSltp(!props.autoSltp)}>{props.autoSltp ? 'ON' : 'OFF'}<span /></button></SettingRow><SettingRow label={ui.beTrigger}><input value={props.beR} onChange={(e) => props.setBeR(e.target.value)} /></SettingRow><SettingRow label={ui.takeProfit}><input value={props.tpR} onChange={(e) => props.setTpR(e.target.value)} /></SettingRow><button className="primary-button" onClick={props.saveSltp}><Save size={18} /> {ui.saveSltp}</button></Panel></div>; }
function TelegramPanel(props: TelegramPanelProps) { const ui: UiCopy = props.ui; const ready = Boolean(props.runtimeHealth?.remoteReady); const canStartRuntime = !props.runtimeHealth?.worker.running || Boolean(props.runtimeHealth?.telegram.configured && !props.runtimeHealth.telegram.running); return <Panel title={ui.telegramTitle} icon={<Send size={20} />} className={props.compact ? 'telegram-panel telegram-panel-compact' : 'telegram-panel'}><div className="telegram-status"><span className={`dot ${ready ? 'green' : 'red'}`} /><span>{ready ? ui.remoteReady : ui.remoteOffline}</span><small>{ui.telegramReceiver}: {props.runtimeHealth?.telegram.running ? `${ui.pid} ${props.runtimeHealth.telegram.pid}` : ui.offline} · {ui.worker}: {props.runtimeHealth?.worker.running ? `${ui.pid} ${props.runtimeHealth.worker.pid}` : ui.offline}</small></div>{canStartRuntime && <button className="secondary-button runtime-start-button" onClick={() => void props.startRuntime()} disabled={props.runtimeStarting}><Radio size={16} /> {props.runtimeStarting ? ui.startingRuntime : ui.startRuntime}</button>}<div className="telegram-input-wrap"><Paperclip size={16} /><textarea rows={props.compact ? 5 : 8} value={props.telegramCommand} onChange={(e) => props.setTelegramCommand(e.target.value)} aria-label="Telegram command" placeholder={ui.telegramPlaceholder} /></div><button className="primary-button" disabled={!props.telegramCommand.trim()} onClick={() => void props.sendTelegram()}><Send size={17} /> {ui.sendReal}</button>{!props.compact && <PendingQueue tasks={props.pendingTasks || []} kind="telegram" loading={props.pendingLoading} onDelete={props.deletePendingTask} ui={ui} />}</Panel>; }
function NettingPanel(props: NettingPanelProps) {
  const ui: UiCopy = props.ui;
  const symbols = Array.from(new Set((props.positions || []).map((position: Position) => position.symbol))) as string[];
  return <Panel title={ui.nettingTitle} icon={<CalendarClock size={20} />} className={props.compact ? 'netting-panel netting-panel-compact' : 'netting-panel'}><div className="netting-row"><span>{ui.autoClose}</span><button className={`switch ${props.nettingEnabled ? 'on' : ''}`} onClick={() => props.setNettingEnabled(!props.nettingEnabled)}>{props.nettingEnabled ? 'ON' : 'OFF'}<span /></button></div><SettingRow label={ui.time}><span className="time-input-wrap"><input type="time" value={props.nettingTime} onChange={(e) => props.setNettingTime(e.target.value)} /><Clock3 size={18} aria-hidden="true" /></span></SettingRow><SettingRow label={ui.mode}><select value={props.nettingMode} onChange={(e) => props.setNettingMode(e.target.value as 'all' | 'symbol')}><option value="all">{ui.allPositions}</option><option value="symbol">{ui.perSymbol}</option></select></SettingRow>{props.nettingMode === 'symbol' && <SettingRow label="Symbol"><select value={props.nettingSymbol} onChange={(e) => props.setNettingSymbol(e.target.value)}><option value="">{ui.chooseSymbol}</option>{symbols.map((symbol) => <option key={symbol} value={symbol}>{symbol}</option>)}</select></SettingRow>}<button className="primary-button" disabled={props.nettingMode === 'symbol' && !props.nettingSymbol} onClick={props.scheduleNetting}><CalendarClock size={17} /> {ui.scheduleClose}</button>{!props.compact && <PendingQueue tasks={props.pendingTasks || []} kind="netting" loading={props.pendingLoading} onDelete={props.deletePendingTask} ui={ui} />}</Panel>;
}

export default App;
