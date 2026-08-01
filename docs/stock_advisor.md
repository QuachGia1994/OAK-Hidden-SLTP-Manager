# Bộ lọc Cổ phiếu Toàn sàn (Local EOD)

Module này quét toàn bộ các mã cổ phiếu trên 3 sàn (HOSE, HNX, UPCoM) với tiêu chí **vốn hoá / quy mô ≥ 100 tỷ VND** và xếp hạng các mã tối ưu dựa trên dữ liệu EOD Local (không cần API Key). Module hoạt động ở chế độ bộ lọc thuần túy (Read-only Filter), không tự động gửi lệnh giao dịch.

## Mô hình & Quy tắc quét

- **Signal**: Tín hiệu D1 độc lập từ chuỗi Local EOD đã hoàn tất; không đọc logical slot Forex, D-Direction, MT4 Feed hay XAUUSD.
- **Vũ trụ cổ phiếu**: Bao phủ 3 sàn HOSE, HNX, UPCoM với các doanh nghiệp niêm yết có vốn hóa ≥ 100 tỷ VND.
- **Điểm vào tham chiếu**: Giá EOD / phiên chiều của ngày giao dịch.
- **Kỳ nắm giữ**: Từ ngày signal tới phiên giao dịch kế tiếp.
- **Cửa sổ active**: 25 phiên hoàn tất trước ngày quyết định.
- **Điều kiện bộ lọc (ScannerPolicy)**: Đủ ít nhất 8 mẫu cùng hướng, hit-rate toàn kỳ ≥ 55% (hiệu chỉnh cho thị trường Việt Nam), hit-rate cùng hướng ≥ 60%, beta dương và edge cùng hướng vượt hurdle.
- **Hiển thị bảng xếp hạng**: Bao gồm Xếp hạng (`#`), Mã cổ phiếu (`MÃ`), Tên công ty đầy đủ (`TÊN CÔNG TY`), Tỷ trọng (`TỶ TRỌNG`), Độ khớp (`KHỚP D1`) và `EDGE`.

## Quản lý dữ liệu Local EOD (`eod_collector`)

Hệ thống sử dụng bộ thu thập dữ liệu EOD tự động qua VPS TradingView Public API lưu trữ trong SQLite (`data/market.db`), hoàn toàn không yêu cầu API Key hay tài khoản chứng khoán:

```powershell
# Cập nhật dữ liệu EOD cuối ngày (15h00+)
python -m eod_collector update

# Xem trạng thái dữ liệu lưu trữ
python -m eod_collector status

# Backfill dữ liệu lịch sử
python -m eod_collector backfill --days 30
```

## Khởi chạy Bộ lọc Cổ phiếu

Chạy trực tiếp từ giao diện Desktop app (nút **Chạy bộ lọc Cổ phiếu**) hoặc bằng dòng lệnh:

```powershell
python vn_stock_advisor.py --capital 90000000 --allow-stale --output stock_recommendation.json
```

## Đọc kết quả

JSON khuyến nghị xuất ra `stock_recommendation.json` và đồng bộ lên Web Dashboard (`/stock-advisor`):

- `READY`: Chọn lọc danh sách mã tối ưu vượt qua các tiêu chuẩn định lượng.
- `PARTIAL`: Tìm thấy mã đạt chuẩn nhưng chưa lấp đầy số slot kỳ vọng.
- `NO_TRADE`: Không có mã nào vượt qua toàn bộ tiêu chí lọc trong phiên.
