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
  // screener
  screenerTitle: string;
  screenerSubtitle: string;
  screenerLoadEod: string;
  screenerAutoEodHint: string;
  screenerLoadingEod: string;
  screenerRunFilter: string;
  screenerRunningFilter: string;
  screenerSearchPlaceholder: string;
  screenerCount: (n: number) => string;
  screenerLoadingData: string;
  screenerNoData: string;
  screenerEodOk: string;
  screenerEodFailed: string;
  screenerEodProgress: (p: { pct: number; cur: number; total: number }) => string;
  screenerFilterReady: (p: { n: number; buy: number; sell: number; asOf: string }) => string;
  screenerFilterNoTrade: (p: { scanned: number }) => string;
  screenerColSymbol: string;
  screenerColExchange: string;
  screenerColOpen: string;
  screenerColHigh: string;
  screenerColLow: string;
  screenerColClose: string;
  screenerColVolume: string;
  // profiles
  terminal: string;
  visibleSltp: string;
  magic: string;
  sltpPair: string;
  copyRole: string;
  yes: string;
  no: string;
  loadingProfiles: string;
  // add profile
  addProfile: string;
  profileName: string;
  terminalPath: string;
  createProfile: string;
  profileAdded: string;
  profileNameRequired: string;
  profileDuplicate: string;
  profileAddError: string;
  magicInvalid: string;
  profileMap: string;
  profileStoredHint: string;
  profileSavedHint: string;
  profileSaved: string;
  profileDuplicated: string;
  profileDeleted: string;
  deleteConfirm: string;
  deleteAgain: string;
  addNew: string;
  duplicate: string;
  delete: string;
  selected: string;
  use: string;
  noProfileSelected: string;
  unsavedChanges: string;
  maskedSecrets: string;
  secretBoundary: string;
  // telegram routing + write-only bot token
  telegramSection: string;
  teleChat: string;
  teleAdmin: string;
  teleToken: string;
  teleTokenPlaceholder: string;
  teleTokenSave: string;
  teleTokenClear: string;
  teleTokenSaved: string;
  teleTokenCleared: string;
  teleTokenClearFailed: string;
  teleTokenConfigured: string;
  teleTokenMissing: string;
  teleTokenRequired: string;
  teleTokenClearConfirm: string;
  teleTokenWriteOnly: string;
  keyringAvailable: string;
  keyringUnavailable: string;
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
    screenerTitle: "Stock Screener",
    screenerSubtitle: "Local EOD \u00b7 data/market.db \u00b7 read-only via sidecar",
    screenerLoadEod: "Load EOD (15:00+)",
    screenerAutoEodHint: "Auto-update runs once a day, after 15:00 local time.",
    screenerLoadingEod: "Loading EOD\u2026",
    screenerRunFilter: "Run filter",
    screenerRunningFilter: "Running\u2026",
    screenerSearchPlaceholder: "Search symbol (e.g. VHM, BVS\u2026)",
    screenerCount: (n: number) => `${n} symbols`,
    screenerLoadingData: "Loading EOD data\u2026",
    screenerNoData: "No EOD data \u2014 run EOD update (after 15:00) or check data/market.db.",
    screenerEodOk: "EOD updated successfully.",
    screenerEodFailed: "EOD update failed:",
    screenerEodProgress: (p: { pct: number; cur: number; total: number }) =>
      `${p.pct}% \u2014 ${p.cur}/${p.total} symbols`,
    screenerFilterReady: (p: { n: number; buy: number; sell: number; asOf: string }) =>
      `Filter run: ${p.n} recommendations (${p.buy} BUY \u00b7 ${p.sell} SELL) \u2014 date ${p.asOf}`,
    screenerFilterNoTrade: (p: { scanned: number }) =>
      `Filter run: no recommendation (scanned ${p.scanned} symbols)`,
    screenerColSymbol: "Symbol",
    screenerColExchange: "Exchange",
    screenerColOpen: "Open",
    screenerColHigh: "High",
    screenerColLow: "Low",
    screenerColClose: "Close",
    screenerColVolume: "Vol (m)",
    terminal: "Terminal",
    visibleSltp: "Visible SL/TP",
    magic: "Magic",
    sltpPair: "SL / TP",
    copyRole: "Copy role",
    yes: "yes",
    no: "no",
    loadingProfiles: "Loading profiles\u2026",
    addProfile: "Add Profile",
    profileName: "Profile name",
    terminalPath: "Terminal path",
    createProfile: "Create profile",
    profileAdded: "Profile added.",
    profileNameRequired: "Profile name required.",
    profileDuplicate: "This profile already exists.",
    profileAddError: "Cannot add profile:",
    magicInvalid: "Magic number must be an integer; leave empty for -1.",
    profileMap: "PROFILE MAP",
    profileStoredHint: "Non-secret fields are stored through oak-core.",
    profileSavedHint: "Changes are saved to profiles.json",
    profileSaved: "Profile saved.",
    profileDuplicated: "Profile duplicated.",
    profileDeleted: "Profile deleted.",
    deleteConfirm: "Click Delete again to remove",
    deleteAgain: "Delete again",
    addNew: "Add new",
    duplicate: "Duplicate",
    delete: "Delete",
    selected: "Selected",
    use: "Use",
    noProfileSelected: "No profile selected",
    unsavedChanges: "Unsaved changes — discard them?",
    maskedSecrets: "MASKED SECRETS",
    secretBoundary: "Telegram tokens and credentials stay inside oak-core and are never sent to React.",
    telegramSection: "Telegram",
    teleChat: "Chat ID",
    teleAdmin: "Admin chat ID",
    teleToken: "Bot token",
    teleTokenPlaceholder: "Paste a new bot token",
    teleTokenSave: "Save token",
    teleTokenClear: "Clear token",
    teleTokenSaved: "Token saved to the Windows keyring.",
    teleTokenCleared: "Token removed from the Windows keyring.",
    teleTokenClearFailed: "Could not remove the token from the Windows keyring.",
    teleTokenConfigured: "Token configured",
    teleTokenMissing: "No token configured",
    teleTokenRequired: "Enter a bot token first.",
    teleTokenClearConfirm: "Remove the Telegram bot token for this profile?",
    teleTokenWriteOnly: "Write-only: the stored token is never read back into this window.",
    keyringAvailable: "Windows keyring available",
    keyringUnavailable: "Windows keyring unavailable — the token cannot be stored securely.",
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
    screenerTitle: "Bộ lọc Cổ phiếu",
    screenerSubtitle: "Dữ liệu EOD nội bộ · data/market.db · đọc qua sidecar (chỉ đọc)",
    screenerLoadEod: "Tải EOD (15:00+)",
    screenerAutoEodHint: "Tự động cập nhật một lần mỗi ngày, sau 15:00 giờ máy.",
    screenerLoadingEod: "Đang tải EOD…",
    screenerRunFilter: "Chạy bộ lọc",
    screenerRunningFilter: "Đang chạy…",
    screenerSearchPlaceholder: "Tra cứu mã (VD: VHM, BVS…)",
    screenerCount: (n: number) => `${n} mã`,
    screenerLoadingData: "Đang tải dữ liệu EOD…",
    screenerNoData: "Chưa có dữ liệu EOD — chạy cập nhật EOD (sau 15:00) hoặc kiểm tra data/market.db.",
    screenerEodOk: "Đã cập nhật EOD thành công.",
    screenerEodFailed: "Cập nhật EOD thất bại:",
    screenerEodProgress: (p: { pct: number; cur: number; total: number }) =>
      `${p.pct}% \u2014 ${p.cur}/${p.total} mã`,
    screenerFilterReady: (p: { n: number; buy: number; sell: number; asOf: string }) =>
      `Đã chạy bộ lọc: ${p.n} khuyến nghị (${p.buy} BUY · ${p.sell} SELL) — ngày ${p.asOf}`,
    screenerFilterNoTrade: (p: { scanned: number }) =>
      `Đã chạy bộ lọc: không có khuyến nghị (đã quét ${p.scanned} mã)`,
    screenerColSymbol: "Mã",
    screenerColExchange: "Sàn",
    screenerColOpen: "Mở",
    screenerColHigh: "Cao",
    screenerColLow: "Thấp",
    screenerColClose: "Đóng",
    screenerColVolume: "KL (tr)",
    terminal: "Terminal",
    visibleSltp: "SL/TP hiển thị",
    magic: "Magic",
    sltpPair: "SL / TP",
    copyRole: "Vai trò Copy",
    yes: "có",
    no: "không",
    loadingProfiles: "Đang tải hồ sơ…",
    addProfile: "Thêm hồ sơ",
    profileName: "Tên hồ sơ",
    terminalPath: "Đường dẫn terminal",
    createProfile: "Tạo hồ sơ",
    profileAdded: "Đã thêm hồ sơ.",
    profileNameRequired: "Cần nhập tên hồ sơ.",
    profileDuplicate: "Hồ sơ này đã tồn tại.",
    profileAddError: "Không thể thêm hồ sơ:",
    magicInvalid: "Magic number phải là số nguyên; để trống nếu muốn -1.",
    profileMap: "DANH SÁCH HỒ SƠ",
    profileStoredHint: "Trường không nhạy cảm được lưu qua oak-core.",
    profileSavedHint: "Thay đổi được lưu vào profiles.json",
    profileSaved: "Đã lưu hồ sơ.",
    profileDuplicated: "Đã nhân bản hồ sơ.",
    profileDeleted: "Đã xóa hồ sơ.",
    deleteConfirm: "Nhấn Xóa lần nữa để xóa",
    deleteAgain: "Xóa lần nữa",
    addNew: "Thêm mới",
    duplicate: "Nhân bản",
    delete: "Xóa",
    selected: "Đang chọn",
    use: "Chọn",
    noProfileSelected: "Chưa chọn hồ sơ",
    unsavedChanges: "Thay đổi chưa lưu — bỏ thay đổi?",
    maskedSecrets: "THÔNG TIN ĐÃ CHE",
    secretBoundary: "Token Telegram và thông tin xác thực chỉ ở trong oak-core, không gửi sang React.",
    telegramSection: "Telegram",
    teleChat: "ID chat",
    teleAdmin: "ID chat quản trị",
    teleToken: "Token bot",
    teleTokenPlaceholder: "Dán token bot mới",
    teleTokenSave: "Lưu token",
    teleTokenClear: "Xóa token",
    teleTokenSaved: "Đã lưu token vào keyring Windows.",
    teleTokenCleared: "Đã xóa token khỏi keyring Windows.",
    teleTokenClearFailed: "Không xóa được token khỏi keyring Windows.",
    teleTokenConfigured: "Đã cấu hình token",
    teleTokenMissing: "Chưa cấu hình token",
    teleTokenRequired: "Hãy nhập token bot trước.",
    teleTokenClearConfirm: "Xóa token bot Telegram của hồ sơ này?",
    teleTokenWriteOnly: "Chỉ ghi: token đã lưu không bao giờ được đọc ngược về cửa sổ này.",
    keyringAvailable: "Keyring Windows khả dụng",
    keyringUnavailable: "Keyring Windows không khả dụng — không thể lưu token an toàn.",
  },
};
