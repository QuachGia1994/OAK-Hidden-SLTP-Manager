// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = 88;
export const PUBLIC_SIGNAL_SLOTS = [3, 7, 9, 12, 14, 16];
export const INTERNAL_SIGNAL_SLOTS = [];

export const RULES_BY_LOCALE = {
  "VN": [
    "Nguồn market-data và đồng hồ Broker duy nhất của Signal Engine là MT5 Python API (đọc trực tiếp từ terminal).",
    "Tất cả năm cặp dùng chung Entry Time do XAUUSD xác định.",
    "Layer 2 và Layer 3 là Entry Plan: H3, H7, H9, H12 và H14 dùng hai cụm ba nến M30 XAUUSD.",
    "Layer 2 và Layer 3 của H16 dùng H1 XAUUSD: Layer 2 dùng 05:00, 04:00, 03:00; Layer 3 dùng 10:00, 09:00, 08:00.",
    "Entry Plan: Layer 2 BT chọn H:11. Layer 2 SW chuyển Layer 3; Layer 3 SW chọn H:49 và Layer 3 BT chọn (H+1):25; riêng H3 chọn 04:25.",
    "Entry Plan H16: Layer 2 BT chọn 16:11; Layer 2 SW và Layer 3 BT chọn 16:49; Layer 2 SW và Layer 3 SW chọn 17:25.",
    "D-Direction được tính độc lập bằng H4 20:00 của từng symbol; GBPUSD là D tham chiếu.",
    "Day Mode là một trạng thái chung, neo bởi Entry H:11 hoặc (H+1):25 đầu tiên trong ngày; H:49 không neo.",
    "Layer 1 (Reference Signal): nhánh H:11/(H+1):25 ghép GBPUSD D với Entry branch/Day Mode — cùng nhánh giữ D, khác nhánh đảo D. Riêng nhánh H:49 lấy H1 XAUUSD hoàn tất ngay trước slot rồi đảo chiều.",
    "Sau Layer 1, XAUUSD và GBPUSD dùng cùng Reference Signal; GBPAUD same D follow/opposite reverse; GBPJPY và GBPCAD same D reverse/opposite follow.",
    "Layer 4 (Final Reverse) chạy sau core Signal và đảo TẤT CẢ các cặp đang áp dụng (applicable) đúng một lần, XAUUSD trước rồi các cặp khác theo cùng bước; Final Reverse KHÔNG bao giờ chạy cuối tuần (WEEKEND_NO_REVERSE).",
    "Final Inversion: H3 Thứ Tư và Thứ Năm bình thường đảo Signal; H3 Thứ Năm có Thứ Tư hôm trước rơi ngày 30 hoặc 1 KHÔNG đảo; H3 Thứ Sáu ngày 3, 4 hoặc 7 đảo.",
    "Final Inversion: H14 Thứ Ba và Thứ Tư luôn đảo Final Signal một lần.",
    "Final Inversion: H16 Thứ Ba, Thứ Tư đảo; H16 Thứ Sáu bình thường đảo; H16 Thứ Sáu ngày 3, 4 hoặc 7 KHÔNG đảo; H16 Thứ Năm có Thứ Tư hôm trước rơi ngày 30 hoặc 1 đảo.",
    "Từng slot chỉ đánh giá các cặp thuộc phạm vi riêng (slot-scoped): H3 gồm XAUUSD, GBPUSD, GBPAUD, GBPJPY; H7 gồm XAUUSD, GBPUSD, GBPJPY; H9 gồm XAUUSD, GBPUSD, GBPCAD; H12 gồm XAUUSD, GBPUSD, GBPAUD; H14 gồm XAUUSD, GBPUSD, GBPCAD; H16 gồm cả 5 cặp. XAUUSD và GBPUSD luôn được đánh giá ở mọi slot và LUÔN bằng nhau (bất biến XAUUSD==GBPUSD, vi phạm thì record không publish). Cặp không thuộc slot là NOT_APPLICABLE: không suy D, không có evidence, không có order intent.",
    "Signal Bot không tạo hay sở hữu lịch Auto-Close. Copy Trade Close All thủ công và Auto Closed Opposite hiện có giữ nguyên, độc lập ngoài core Signal.",
    "Live execution chạy Thứ Hai đến Thứ Sáu; cuối tuần chỉ chạy live khi profile đặt signal_live_weekends=true. Rebuild/backtest chạy 24/7: slot cuối tuần được đánh giá từ bar market-data đã lưu (READY) hoặc báo WAIT_MT5_DATA/thiếu dữ liệu — không bỏ qua ngày, không mượn nến Thứ Sáu.",
    "D-Direction được tính và công bố độc lập lúc 06:00 GMT+7 mỗi ngày, mỗi ngày history độc lập.",
    "Snapshot D MISSING không được đánh dấu là đã publish; bot retry cho đến khi READY.",
    "Nguồn market-data dùng để tính Signal là MT5 Python API, đọc completed bars (M30/H1/H4) trực tiếp từ terminal.",
    "Time Authority và Scheduler phụ thuộc đồng hồ market-data; Heartbeat phân tách kênh Data và Execution.",
    "Cài đặt: bật MT5 terminal và cài 'pip install MetaTrader5'. Bot tự kết nối terminal, resolve symbol (gồm cả tiền tố/hậu tố broker: +, .a, .i, m, #, ...), preload lịch sử M30/H1/H4, chuẩn hóa timestamp từ UTC sang Broker time. Core Signal v88 vẫn cần XAUUSD/GOLD, GBPUSD, GBPAUD, GBPJPY, GBPCAD.",
    "Không còn hỗ trợ endpoint feeder HTTP hoặc EA market-data legacy; Signal Engine chỉ đọc market-data trực tiếp từ MT5 Python API."
  ],
  "EN": [
    "The sole Signal Engine market-data and Broker-clock source is the MT5 Python API, read directly from the terminal.",
    "All five pairs share the single XAUUSD Entry Plan.",
    "Layers 2 and 3 are the Entry Plan: H3, H7, H9, H12 and H14 use two three-candle XAUUSD M30 groups.",
    "Layers 2 and 3 for H16 use XAUUSD H1: Layer 2 uses 05:00, 04:00, 03:00 and Layer 3 uses 10:00, 09:00, 08:00.",
    "Entry Plan: Layer 2 BT selects H:11; Layer 2 SW moves to Layer 3; Layer 3 SW selects H:49 and BT selects (H+1):25; H3 uses 04:25.",
    "H16 Entry Plan: Layer 2 BT selects 16:11; Layer 2 SW + Layer 3 BT selects 16:49; Layer 2 SW + Layer 3 SW selects 17:25.",
    "D-Direction is independent per symbol from H4 20:00; GBPUSD is the reference D.",
    "Day Mode is one shared state anchored by the first H:11 or (H+1):25 Entry; H:49 never anchors.",
    "Layer 1 (Reference Signal): H:11/(H+1):25 combines GBPUSD D with the resolved Entry branch/Day Mode — the same branch keeps D and a different branch reverses it. H:49 is the exception: reverse the immediately prior completed XAUUSD H1 candle.",
    "After Layer 1, XAUUSD and GBPUSD share the Reference Signal; GBPAUD follows on same D and reverses on opposite D; GBPJPY/GBPCAD do the inverse.",
    "Layer 4 (Final Reverse) runs after pair derivation and is applied exactly once to EVERY applicable pair, XAUUSD first then the others in the same step; Final Reverse NEVER runs on weekends (WEEKEND_NO_REVERSE).",
    "Final Inversion: H3 Wednesday and normal Thursday invert Signal; H3 Thursday with previous Wed on day 30 or 1 does NOT invert; H3 Friday on day 3, 4, or 7 inverts.",
    "Final Inversion: H14 Tuesday and Wednesday always invert Final Signal once.",
    "Final Inversion: H16 Tuesday, Wednesday invert; normal H16 Friday inverts; H16 Friday on day 3, 4, or 7 does NOT invert; H16 Thursday with previous Wed on day 30 or 1 inverts.",
    "Each slot evaluates only its slot-scoped applicable pairs: H3 = XAUUSD, GBPUSD, GBPAUD, GBPJPY; H7 = XAUUSD, GBPUSD, GBPJPY; H9 = XAUUSD, GBPUSD, GBPCAD; H12 = XAUUSD, GBPUSD, GBPAUD; H14 = XAUUSD, GBPUSD, GBPCAD; H16 = all 5 pairs. XAUUSD and GBPUSD are evaluated every slot and ALWAYS equal (XAUUSD==GBPUSD invariant; a violation blocks publication). A pair outside the slot is NOT_APPLICABLE: no D derivation, no evidence, no order intent.",
    "Signal Bot does not create or own an Auto-Close schedule. The existing manual Copy Trade Close All path and existing Auto Closed Opposite path remain unchanged and outside Signal core.",
    "Live execution runs Monday through Friday; weekend live slots require signal_live_weekends=true in the active profile. Rebuild/backtest runs 24/7: weekend slots are evaluated from the persisted market-data bars (READY) or report WAIT_MT5_DATA/missing data — never silently skipped, never filled with Friday candles.",
    "D-Direction is calculated and published independently at 06:00 GMT+7 daily with per-date history isolation.",
    "MISSING D snapshot is never marked as published; bot retries until READY.",
    "The sole market-data source for Signal is the MT5 Python API (completed M30/H1/H4 candles read directly from the terminal).",
    "Time Authority and Scheduler depend on the market-data clock; Heartbeat separates Data and Execution channels.",
    "Setup: have the MT5 terminal running and 'pip install MetaTrader5'. The bot connects to the terminal, auto-resolves symbols (including broker prefixes/suffixes), preloads M30/H1/H4 history, and normalises timestamps from UTC to Broker time. The Signal core still requires XAUUSD/GOLD, GBPUSD, GBPAUD, GBPJPY, and GBPCAD.",
    "Legacy HTTP feeder endpoints and EA market-data inputs are no longer supported; Signal Engine reads market data directly from the MT5 Python API."
  ]
};

export const STARTUP_SUMMARY_BY_LOCALE = "v88: weekend-capable 24/7 rebuild, slot-scoped active pairs, Final Reverse on every applicable pair, XAUUSD==GBPUSD invariant";
