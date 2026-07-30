// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = 79;
export const PUBLIC_SIGNAL_SLOTS = [3, 7, 9, 12, 14, 16];
export const INTERNAL_SIGNAL_SLOTS = [];

export const RULES_BY_LOCALE = {
  "VN": [
    "Tầng 1 tạo native Signal độc lập cho GBPUSD và GBPAUD từ ba nến M30 mở trước H:00; GBPJPY và GBPCAD tạm Tắt (OFF).",
    "Tầng 2 XAUUSD M30 chọn Entry H:11 ngay lập tức nếu BT; nếu SW chuyển sang Tầng 3 chờ nến M30 mở H:00 đóng lúc H:30.",
    "Tầng 3 XAUUSD tại H:30: SW chọn H:49; BT chọn (H+1):25; riêng H3 BT chọn 04:25.",
    "Riêng H16 không dùng Layer 2/Layer 3 để chọn Entry. H16 quét H14, H12, H9, H7 và H3, lấy mốc gần nhất có nhánh H:11 hoặc (H+1):25. Nhánh H:49 bị bỏ qua. H16 chuyển nhánh H:11 thành 16:11 và nhánh (H+1):25 thành 17:25.",
    "Mọi timestamp M30 là giờ MỞ nến M30.",
    "Entry của nhóm GBP luôn là giờ tròn H+1:00 sau mốc phát signal, độc lập với Entry của XAUUSD.",
    "Suy chéo Signal: XAUUSD lấy native GBPAUD và GBPAUD lấy native GBPUSD; cả hai được đảo tại H3, H14 và H16. Tại H3, H7 và H9, final GBPUSD bằng final XAUUSD. Tại H12, H14 và H16, final GBPUSD dùng native GBPUSD của chính nó.",
    "Thiếu dữ liệu hoặc DOJI làm riêng dependency đó WAIT, fail-closed từng phần.",
    "Classifier ba nến M30 có tám trường hợp SW/BT phủ toàn bộ tổ hợp Tăng/Giảm; không dùng cây C4."
  ],
  "EN": [
    "Layer 1 derives independent native signals for GBPUSD and GBPAUD from three M30 candles opening before H:00; GBPJPY and GBPCAD are OFF.",
    "XAUUSD Layer 2 selects Entry H:11 immediately if BT; if SW, moves to Layer 3 awaiting the M30 candle opening at H:00 to close at H:30.",
    "XAUUSD Layer 3 at H:30: SW selects H:49; BT selects (H+1):25; H3 BT selects 04:25.",
    "H16 does not use Layer 2/Layer 3 for entry selection. H16 scans H14, H12, H9, H7, and H3, inheriting the nearest eligible prior entry with branch H:11 or (H+1):25. Branch H:49 is skipped. H16 maps branch H:11 to 16:11 and branch (H+1):25 to 17:25.",
    "All M30 timestamps represent M30 candle OPEN times.",
    "GBP entry time is always the next full hour H+1:00 after the signal slot, independent of XAUUSD entry timing.",
    "Signal cross-mapping: XAUUSD uses native GBPAUD and GBPAUD uses native GBPUSD; both are inverted at H3, H14, and H16. At H3, H7, and H9, final GBPUSD equals final XAUUSD. At H12, H14, and H16, final GBPUSD uses its own native GBPUSD signal.",
    "Missing data or DOJI results in WAIT only for affected dependencies (fail-closed).",
    "Three-candle M30 classifier has eight SW/BT cases covering all Up/Down combinations; no C4 tree."
  ]
};

export const STARTUP_SUMMARY_BY_LOCALE = "v79: three-candle M30 core, Layer 3 grace period at H:30, D-Direction from previous broker session, H3 BT entry 04:25, H16 inherits nearest eligible prior entry";
