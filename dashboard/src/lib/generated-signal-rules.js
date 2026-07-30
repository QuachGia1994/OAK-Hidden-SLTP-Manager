// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = 74;
export const PUBLIC_SIGNAL_SLOTS = [3, 7, 9, 12, 14, 16];
export const INTERNAL_SIGNAL_SLOTS = [];

export const RULES_BY_LOCALE = {
  "VN": [
    "Tầng 1 tạo native Signal độc lập cho GBPUSD và GBPAUD từ bốn nến M30 mở trước H:00; GBPJPY và GBPCAD tạm Tắt (OFF).",
    "Tầng 2 XAUUSD M30 chọn Entry H:11 ngay lập tức nếu BT; nếu SW chuyển sang Tầng 3 chờ nến M30 mở H:00 đóng lúc H:30.",
    "Tầng 3 XAUUSD tại H:30: SW chọn H:49; BT chọn (H+1):25; riêng H3 BT chọn 04:49.",
    "Mọi timestamp M30 là giờ MỞ nến M30.",
    "Entry của nhóm GBP luôn là giờ tròn H+1:00 sau mốc phát signal, độc lập với Entry của XAUUSD.",
    "Suy chéo Signal: XAUUSD = native GBPAUD; GBPAUD = native GBPUSD (cả hai đảo tại H3, H14, H16). GBPUSD = final XAUUSD tại H12, H14, H16 và native GBPUSD tại H3, H7, H9.",
    "Thiếu dữ liệu hoặc DOJI làm riêng dependency đó WAIT, fail-closed từng phần."
  ],
  "EN": [
    "Layer 1 derives independent native signals for GBPUSD and GBPAUD from four M30 candles opening before H:00; GBPJPY and GBPCAD are OFF.",
    "XAUUSD Layer 2 selects Entry H:11 immediately if BT; if SW, moves to Layer 3 awaiting the M30 candle opening at H:00 to close at H:30.",
    "XAUUSD Layer 3 at H:30: SW selects H:49; BT selects (H+1):25; H3 BT selects 04:49.",
    "All M30 timestamps represent M30 candle OPEN times.",
    "GBP entry time is always the next full hour H+1:00 after the signal slot, independent of XAUUSD entry timing.",
    "Signal cross-mapping: XAUUSD = native GBPAUD; GBPAUD = native GBPUSD (both inverted at H3, H14, H16). GBPUSD = final XAUUSD at H12, H14, H16 and native GBPUSD at H3, H7, H9.",
    "Missing data or DOJI results in WAIT only for affected dependencies (fail-closed)."
  ]
};

export const STARTUP_SUMMARY_BY_LOCALE = "v74: normalize MT5 rate rows at boundary, three-layer M30 engine, 5 symbols (GBP USD/AUD active, JPY/CAD OFF), H+1:00 GBP entry schedule";
