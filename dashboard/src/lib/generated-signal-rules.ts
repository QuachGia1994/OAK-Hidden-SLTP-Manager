// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = 72;
export const PUBLIC_SIGNAL_SLOTS = [3, 7, 9, 12, 14, 16] as const;
export const INTERNAL_SIGNAL_SLOTS = [] as const;

export const RULES_BY_LOCALE = {
  "VN": [
    "GBPUSD, GBPAUD, GBPJPY và GBPCAD tạo Signal độc lập từ bốn nến M30 của chính từng symbol; nhóm SW đảo Base và nhóm BT giữ Base.",
    "Thứ tự xử lý là Signal GBP trước, tiếp theo Layer 1 XAUUSD tạo hai ứng viên Entry, rồi Layer 2 XAUUSD chọn Entry cuối.",
    "Các mốc Layer XAUUSD là giờ đóng nến. H3 Layer 1 dùng ba mốc 02:30, 02:00, 01:30; Layer 2 dùng 03:00, 02:30, 02:00, 01:30. Các slot khác dùng hai cửa sổ bốn nến cách nhau 30 phút.",
    "Nếu Layer 1 SW: Layer 2 SW chọn H:49; Layer 2 BT chọn (H+1):25, riêng H3 chọn 04:49. Nếu Layer 1 BT: Layer 2 SW chọn H:11; Layer 2 BT chọn H:49.",
    "Entry của bốn cặp GBP là giờ Broker tròn kế tiếp sau Entry XAUUSD; ví dụ XAU 03:11/03:49 thì GBP 04:00, còn XAU 04:25/04:49 thì GBP 05:00.",
    "Hướng XAUUSD follow GBPAUD: H7, H9 và H12 đảo chiều; H3, H14 và H16 cùng chiều.",
    "Thiếu dữ liệu, nến không hợp lệ hoặc DOJI làm riêng Signal hoặc Layer liên quan WAIT; không dùng H1, M15 hay symbol khác làm fallback."
  ],
  "EN": [
    "GBPUSD, GBPAUD, GBPJPY, and GBPCAD independently derive their Signal from four M30 candles of the same symbol; SW reverses Base and BT keeps Base.",
    "The processing order is GBP Signal first, XAUUSD Layer 1 second to create two Entry candidates, and XAUUSD Layer 2 last to select the final Entry.",
    "XAUUSD layer timestamps are candle close times. H3 Layer 1 uses 02:30, 02:00, and 01:30; Layer 2 uses 03:00, 02:30, 02:00, and 01:30. Other slots use two four-candle windows separated by 30 minutes.",
    "For Layer 1 SW, Layer 2 SW selects H:49 and Layer 2 BT selects (H+1):25, except H3 selects 04:49. For Layer 1 BT, Layer 2 SW selects H:11 and Layer 2 BT selects H:49.",
    "All four GBP pairs enter at the next full Broker hour after the XAUUSD Entry; for example XAU 03:11/03:49 maps to GBP 04:00, while XAU 04:25/04:49 maps to GBP 05:00.",
    "XAUUSD follows GBPAUD direction: H7, H9, and H12 are opposite; H3, H14, and H16 match.",
    "Missing data, an invalid candle, or a DOJI makes only the affected Signal or Layer WAIT; H1, M15, and other symbols are never used as fallbacks."
  ]
} as const;

export const STARTUP_SUMMARY_BY_LOCALE = "v72: GBP M30 Signals -> XAU Layer 1 -> XAU Layer 2; GBP Entry at next full hour" as const;
