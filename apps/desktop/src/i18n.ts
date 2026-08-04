// Lightweight i18n for the desktop app — mirrors the Native Qt VN catalog.
// Locale comes from settings.json (`lang`) via the sidecar; EN is default.

export type Locale = "EN" | "VN";

export interface LocaleText {
  navStatus: string;
  navProfiles: string;
  navAccounts: string;
  navPerformance: string;
  navSltpCopy: string;
  navSettings: string;
  navScreener: string;
  statusTitle: string;
  handshake: string;
  health: string;
  sidecarLogs: string;
  noLogLines: string;
  profilesTitle: string;
  noProfiles: string;
  running: string;
  stopped: string;
  start: string;
  stop: string;
  accountsTitle: string;
  profile: string;
  refresh: string;
  noAuditData: string;
  overview: string;
  livePositions: string;
  checkpointTimeline: string;
  performanceTitle: string;
  equityCurve: string;
  drawdown: string;
  noEquitySamples: string;
  sltpTitle: string;
  hiddenSltp: string;
  copyTrading: string;
  save: string;
  reload: string;
  settingsTitle: string;
  language: string;
  theme: string;
  ghostMode: string;
  services: string;
  noServices: string;
  error: string;
  saved: string;
  empty: string;
}

export const LOCALES: Record<Locale, LocaleText> = {
  EN: {
    navStatus: "Status",
    navProfiles: "Profiles",
    navAccounts: "Accounts",
    navPerformance: "Performance",
    navSltpCopy: "SL/TP · Copy",
    navSettings: "Settings",
    navScreener: "Screener",
    statusTitle: "Sidecar Status",
    handshake: "Handshake",
    health: "Health",
    sidecarLogs: "Sidecar Logs",
    noLogLines: "No log lines yet.",
    profilesTitle: "Profiles",
    noProfiles: "No profiles configured (profiles.json empty).",
    running: "Running",
    stopped: "Stopped",
    start: "Start",
    stop: "Stop",
    accountsTitle: "Account Tracking",
    profile: "Profile",
    refresh: "Refresh",
    noAuditData:
      "No audit data for this profile yet — start the profile (Profiles tab) so the checkpoint/equity sampler can record account state.",
    overview: "Account Overview",
    livePositions: "Live Positions",
    checkpointTimeline: "Checkpoint Timeline",
    performanceTitle: "Performance & Risk",
    equityCurve: "Equity Curve",
    drawdown: "Drawdown",
    noEquitySamples:
      "No equity samples yet — start the profile so the equity sampler records account state.",
    sltpTitle: "Hidden SL/TP & Copy Trading",
    hiddenSltp: "Hidden SL/TP",
    copyTrading: "Copy Trading",
    save: "Save",
    reload: "Reload",
    settingsTitle: "Settings",
    language: "Language",
    theme: "Theme",
    ghostMode: "Ghost mode",
    services: "Services",
    noServices: "No services reported.",
    error: "ERROR",
    saved: "Saved (whitelisted fields only).",
    empty: "—",
  },
  VN: {
    navStatus: "Trạng thái",
    navProfiles: "Hồ sơ",
    navAccounts: "Tài khoản",
    navPerformance: "Hiệu suất",
    navSltpCopy: "SL/TP · Copy",
    navSettings: "Cài đặt",
    navScreener: "Bộ lọc CP",
    statusTitle: "Trạng thái Sidecar",
    handshake: "Bắt tay",
    health: "Sức khỏe",
    sidecarLogs: "Nhật ký Sidecar",
    noLogLines: "Chưa có dòng nhật ký.",
    profilesTitle: "Hồ sơ",
    noProfiles: "Chưa cấu hình hồ sơ (profiles.json trống).",
    running: "Đang chạy",
    stopped: "Đã dừng",
    start: "Chạy",
    stop: "Dừng",
    accountsTitle: "Theo dõi tài khoản",
    profile: "Hồ sơ",
    refresh: "Làm mới",
    noAuditData:
      "Chưa có dữ liệu kiểm toán cho hồ sơ này — hãy chạy hồ sơ (tab Hồ sơ) để checkpoint/equity sampler ghi nhận trạng thái tài khoản.",
    overview: "Tổng quan tài khoản",
    livePositions: "Vị thế đang mở",
    checkpointTimeline: "Dòng thời gian Checkpoint",
    performanceTitle: "Hiệu suất & Rủi ro",
    equityCurve: "Đường Equity",
    drawdown: "Drawdown",
    noEquitySamples:
      "Chưa có mẫu equity — hãy chạy hồ sơ để equity sampler ghi nhận trạng thái tài khoản.",
    sltpTitle: "SL/TP Ẩn & Copy Trading",
    hiddenSltp: "SL/TP Ẩn",
    copyTrading: "Copy Trading",
    save: "Lưu",
    reload: "Tải lại",
    settingsTitle: "Cài đặt",
    language: "Ngôn ngữ",
    theme: "Giao diện",
    ghostMode: "Chế độ ẩn",
    services: "Dịch vụ",
    noServices: "Chưa có dịch vụ nào.",
    error: "LỖI",
    saved: "Đã lưu (chỉ các trường cho phép).",
    empty: "—",
  },
};
